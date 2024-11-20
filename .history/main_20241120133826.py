import sys
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import base64
from termcolor import colored
import os
from typing import Dict
import json
from openai import AsyncOpenAI
from datetime import datetime
import asyncio
import aiofiles
import re
import termcolor
from typing_extensions import List, Literal, Optional, Union, Annotated, Self, Set
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field, Tag, ValidationInfo, field_validator, model_validator, EmailStr
from pydantic.types import Discriminator
from langsmith import traceable
from langsmith.wrappers import wrap_openai
import instructor
from pathlib import Path
from difflib import SequenceMatcher
import decimal  # Add this import to handle Decimal exceptions



# Wrap the OpenAI client with LangSmith and patch with instructor
client = wrap_openai(AsyncOpenAI())
client = instructor.from_openai(client)

# Semaphore to limit concurrent tasks
sem = asyncio.Semaphore(500)

# Load template files
with open('./prompt_templates/user_info.txt', 'r') as file:
    user_info = file.read()

with open('./prompt_templates/emballage_info.txt', 'r') as file:
    emballage_info = file.read()

# Initialize the FastAPI application instance
app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@traceable(name="demo", project_name="ai-builders-demo")
async def get_invoice_detail(data: str, file: str):
    doc_text = data

    #class to capture the financial details for each supplier on the invoice.
    class SupplierFinancialDetails(BaseModel):
        """
        This class captures financial details for each supplier on the invoice. Usually, invoices come from a single supplier, but for aggregated invoices contain multiple suppliers, each sub-supplier's details need to be captured individually. 
        """

        supplier: str = Field(
            ...,
            description="Provide the name of the supplier or sub-suppliers listed on the invoice. Capture legal entity extensions like B.V.  and V.O.F. without any dots.",
            example="Sligro Food Group Nederland BV"
        )
        observation: Optional[str] = Field(
            default=None,
            description=(
                "Perform a step-by-step analysis of the base amounts, tax, and total payable amounts specified per supplier as stated in the invoice.\n"
                "Determine if the base amounts are explicitly mentioned, or if only partial information, for example the total amount payable and the tax part(s), are specified. Assess if missing information can be inferred with confidence.\n"
                "If the invoice has multiple suppliers, provide the analysis for each supplier that billed, ignore sun suppliers that did not. Be mindful of any discounts, or credits applied that could affect the amount payable. The provided examples are a guide, not a strict rule. Handle invoices that deviate from the examples. Be precise and careful in your analysis, especially for complex invoices with multiple suppliers, deductions, discounts, emballage, statiegeld or tax rates."
            ),
            examples=[
                """
                "Invoice Review: The invoice has one supplier.\n"
                "Explicitly mentioned: Total Amount Payable: €97.55\n"
                "Explicitly mentioned: Tax Details: VAT tax is €8.05.\n"
                "Inferred: Tax Tariff: Not explicitly mentioned, but given this is a Dutch invoice for food products (low tax rate), and €8.05 is '9%' of €97.55, we can confidently infer the missing tax values.\n"
                "Conclusion: The base amount is €89.55, the tax amount is €8.05, and the total payable amount is €97.55.\n"
                "I will meticulously process the data and make no stupid mistakes.\n"
                """,
                """
                "Invoice Review: The invoice mentions two suppliers, Sligro Food Group Nederland BV and Heineken Nederland BV.\n"
                "Both suppliers are actually billed, but the invoice is for a umbrella company that is a 'Stichting' and not a 'BV'.\n"
                "The issuer of the invoice is 'Heineken Sligro Stichting Derdengelden'.\n"
                "Explicitly mentioned: Total Amount Payable: €1298.78\n"
                "Subtotaal exclusief BTW en emballage Heineken Nederland B.V. € 457.22\n"
                "Sligro Food Group Nederland B.V. € 497.24\n"
                "Subtotaal BTW € 181.50\n"
                "Heineken Nederland B.V. 21% over € 457.22 is € 96.01\n"
                "Sligro Food Group Nederland B.V. 9% over € 157.81 is € 14.20\n"
                "Sligro Food Group Nederland B.V. 21% over € 339.43 is € 71.28\n"
                "Subtotaal emballage is the relevant metric for packaging deposits, it's € 162,80\n"
                "Emballage does NOT qualify as 'null_tax_base', 'low_tax_base' or 'high_tax'.\n"
                "Conclusion: Given the complexity I should be carefull and precise in my analysis.\n"
                "The amount payable is includes the VAT tax and subtotaal emballage.\n"
                "Emballage is not subject to VAT (BTW). It is treated as VAT-exempt. Meaning neither count for 'null_tax_base', 'low_tax_base' or 'high_tax'.\n"
                "I will take extreme caution given the complexity of the invoice, and process the data correctly per individual supplier.\n"
                """,
                """
                "Invoice Review: The invoice has one supplier.\nExplicitly mentioned: Total Amount Payable: €1,527.87\nExplicitly mentioned: Tax Details: VAT tax is €0.00.\n This makes sense as the invoice is Dutch, and rent is often tax exempt for B2B in the Netherlands. Explicitly mentioned: Huur: €1,954.05\nExplicitly mentioned: Huurkorting: -€426.18\nConclusion: The base amount is €1,527.87, the tax amount is €0.00, and the total payable amount is €1,527.87.\nI will meticulously process the data and make no stupid mistakes.\n"
                """,
                """
                "Invoice Review: The invoice mentions two suppliers and a issuer of the invoice.\n"
                "It's clear that the issuer is a umbrella company that does the billing, not a supplier."
                "Only one supplier is actually charging on this invoice, the other supplier can be ignored.\n"
                "Explicitly mentioned: Total Amount Payable: €100.00\n"
                "Explicitly mentioned: Tax Details: VAT tax is 0%, the tax amount is €0.00. Which makes sense given that the invoice is billed in Dollars by a USA based company, and therefore tax is not charged.\n"
                "There is no mentioning of packaging costs, which makes sense given that the line items are related to SaaS subscription.\n"
                "Conclusion: The base amount is €100.00, the tax amount is €0.00, and the total payable amount is €100.00.\n"
                "I will take extreme care to ensure that the data is processed correctly, and that the amount payable is 100.00, and that the tax amount is 0.00."
                """
            ]
        )

        null_tax_base: Optional[Decimal] = Field(
            default=None, 
            description="Emballage / Packaging / statiegeld do NOT qualify as 'null_tax_base'. Given the document and guided by your thoughts and analysis above. Provide the invoice amount specified for the supplier that qualifies for 0% VAT."
        ) 
        low_tax_base: Optional[Decimal] = Field(
            default=None,
            description="Given the document and guided by your thoughts and analysis above. Provide the invoice amount specified for the supplier that qualifies for a low VAT rate of 9%."
        )
        high_tax_base: Optional[Decimal] = Field(
            default=None, 
            description="Given the document and guided by your thoughts and analysis above. Provide the invoice amount specified for the supplier that qualifies for a high VAT rate of 21%."
        )
        low_tax: Optional[Decimal] = Field(
            default=None, 
            description="Given the document and guided by your thoughts and analysis above. Provide the amount specified for this supplier of low VAT (9%) charged."
        )

        high_tax: Optional[Decimal] = Field(
            default=None, 
            description="Given the document and guided by your thoughts and analysis above. Provide the amount specified for this supplier of high VAT (21%) charged."
        )


        @field_validator('supplier', mode='before')
        @classmethod
        def clean_and_format_supplier_name(cls, v: str) -> str:
            # Handle legal entity extensions
            v = re.sub(r'\b(b\.?\s*v\.?|ltd\.?|v\.?\s*o\.?\s*f\.?)\b', 
                    lambda m: m.group(1).replace('.', '').replace(' ', '').upper(), 
                    v, 
                    flags=re.IGNORECASE)
            
            # Split the name into parts
            parts = v.split()
            
            # Capitalize each part unless it's a legal entity extension
            return ' '.join([part if part in ['BV', 'LTD', 'VOF'] else part.capitalize() for part in parts])


        

        # Validate that high and low base tax are logically sound given the provided high and low tax

        @model_validator(mode='after')
        def validate_taxes(self) -> Self:
            """Validate and calculate the tax bases and amounts if necessary."""
            tolerance = Decimal('0.01')  # 1% tolerance for minor rounding differences
            low_rate = Decimal('0.09')
            high_rate = Decimal('0.21')

            def quantize_decimal(value: Decimal) -> Decimal:
                return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            def validate_tax_pair(tax: Optional[Decimal], base: Optional[Decimal], rate: Decimal, tax_name: str):
                if tax is None and base is None:
                    return  # Both are None, no validation needed

                if tax is not None and base is not None:
                    calculated_tax = quantize_decimal(base * rate)
                    
                    if tax == Decimal('0') and calculated_tax == Decimal('0'):
                        return  # Both are zero, no need to calculate difference
                    
                    if tax == Decimal('0'):
                        tax_diff = Decimal('1')  # 100% difference if actual tax is zero but calculated is not
                    else:
                        tax_diff = abs((tax - calculated_tax) / tax)
                    
                    if base == Decimal('0'):
                        base_diff = Decimal('1')  # 100% difference if base is zero but tax is not
                    else:
                        calculated_base = quantize_decimal(tax / rate)
                        base_diff = abs((base - calculated_base) / base)
                    
                    if tax_diff > tolerance and base_diff > tolerance:
                        inconsistency_message = (
                            f"WARNING: Possible error on invoice. "
                            f"{tax_name}_tax ({tax}) and {tax_name}_tax_base ({base}) are inconsistent with the {rate*100}% rate. "
                            f"Expected tax: {calculated_tax} or expected base: {calculated_base}. "
                            f"Please verify these values in the invoice."
                        )
                        
                        # Print to terminal
                        print(termcolor.colored(f"\n{inconsistency_message}", "red"), file=sys.stderr)
                        
                        # Add to observation field
                        if self.observation:
                            self.observation += "\n" + inconsistency_message
                        else:
                            self.observation = inconsistency_message

                elif tax is not None:
                    # Only tax is provided, calculate the base
                    self.__dict__[f"{tax_name}_tax_base"] = quantize_decimal(tax / rate)

                elif base is not None:
                    # Only base is provided, calculate the tax
                    self.__dict__[f"{tax_name}_tax"] = quantize_decimal(base * rate)

            validate_tax_pair(self.low_tax, self.low_tax_base, low_rate, "low")
            validate_tax_pair(self.high_tax, self.high_tax_base, high_rate, "high")

            return self

        def is_all_fields_null(self) -> bool:
            """Check if all fields except 'supplier', and 'observation' are null."""
            return all(
                getattr(self, field) is None
                for field in self.model_fields
                if field not in ['supplier', 'observation']
            )

        @model_validator(mode='before')
        @classmethod
        def convert_decimals(cls, values):
            decimal_fields = ['null_tax_base', 'low_tax_base', 'high_tax_base', 'low_tax', 'high_tax']
            for field in decimal_fields:
                if field in values and values[field] is not None:
                    try:
                        values[field] = Decimal(str(values[field]))
                    except decimal.InvalidOperation:
                        raise ValueError(f"Invalid decimal value for field '{field}': {values[field]}")
            return values


    class SupplierDetails(BaseModel):
        """This class captures the business details of the issuer of the invoice"""

        email: Optional[EmailStr] = Field(
            default=None,
            description="The email address of the issuer."
        )
        address: Optional[str] = Field(
            default=None,
            description="The physical address of the issuer."
        )

        iban: Optional[str] = Field(
            ..., 
            description="Provide the IBAN number of the issuer of the invoice.", example= "NL123456789B01"
        )

        vat_id: Optional[str] = Field(
            default=None,
            description="The VAT (BTW) id of the issuer.",
            example="NL123456789B01"
        )

        kvk: Optional[str] = Field(
            default=None,
            description="Extract the Chamber of Commerce registration number (KVK) for the issuer of the invoice."
        )
        @field_validator('iban')
        @classmethod
        def validate_iban(cls, v: Optional[str]) -> Optional[str]:
            if v == 'NL85INGB0006814971':
                raise ValueError(
                    "#####ValueError#####\n"
                    "value_error_id: 'incorrect_iban'\n"
                    f"Luca! Pay Attention! The iban you extracted with your last attempt to process the invoice for this supplier was {v}. This is incorrect, as it is the iban of the recipient, not the supplier. Please check your extraction and provide a valid iban, or None if it is not applicable.\n"
                    "#####END_VALUE_ERROR_MESSAGE#####\n"
                    "ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                )
            return v
        
        @field_validator('vat_id', mode='after')
        @classmethod
        def validate_vat_id(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
            if not v:
                return v
            
            # Dutch VAT ID validation
            if v[:2].lower() == 'nl':
                pattern = r'^NL\d{9}B\d{2}$'
                if not re.match(pattern, v, re.IGNORECASE):
                    raise ValueError(f'#####ValueError#####\n'
                        f"value_error_id: 'invalid_dutch_vat_id'\n"
                        f"Luca, pay attention! The VAT ID '{v}' is not a valid Dutch VAT ID. Expected format: NLxxxxxxxxBxx.\n"
                        f"#####END_VALUE_ERROR_MESSAGE#####\n"
                        f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                    )
            
            # General VAT ID format check (for other countries)
            elif not re.match(r'^[A-Z]{2}[A-Z0-9]{2,}$', v, re.IGNORECASE):
                raise ValueError(f'#####ValueError#####\n'
                    f"value_error_id: 'invalid_vat_id_format'\n"
                    f"Luca, pay attention! The VAT ID '{v}' does not appear to be in a valid format. VAT IDs typically start with two letters followed by numbers or letters.\n"
                    f"#####END_VALUE_ERROR_MESSAGE#####\n"
                    f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                )
            
            return v


    



    class DiscountBase(BaseModel):
        """
        This class captures the details of the total applied discount, credit, or deduction, that is deducted from the amount payable. 
        """
        discount_amount: Decimal = Field(
            ...,
            description="The total amount of discount, credit, or deduction. Must be a negative decimal value.",
            lt=Decimal('0')
        )

        @model_validator(mode='before')
        @classmethod
        def convert_decimals(cls, values):
            if 'discount_amount' in values and values['discount_amount'] is not None:
                try:
                    values['discount_amount'] = Decimal(str(values['discount_amount']))
                except decimal.InvalidOperation:
                    raise ValueError(f"Invalid decimal value for discount_amount: {values['discount_amount']}")
            return values

    class DetailedDiscount(DiscountBase):
        """
        This class captures the type of discount and the reason for the discount.
        """
        type: Literal['discount', 'credit', 'deduction'] = Field(...)
        reason: str = Field(..., description="The reason for the discount, credit, or deduction.")

    class SimpleDiscount(DiscountBase):
        """
        This class captures the type of discount if it's packaging or statiegeld.
        """
        type: Literal['emballage', 'statiegeld'] = Field(...)

    def discount_discriminator(v):
        return v.get('type')

    Discount = Annotated[
        Union[
            Annotated[DetailedDiscount, Tag('discount')],
            Annotated[DetailedDiscount, Tag('credit')],
            Annotated[DetailedDiscount, Tag('deduction')],
            Annotated[SimpleDiscount, Tag('emballage')],
            Annotated[SimpleDiscount, Tag('statiegeld')]
        ],
        Discriminator(discount_discriminator)
    ]

    # Define the Discount type using Union
    Discount = Union[DetailedDiscount, SimpleDiscount]



  
    class CaptureError(BaseModel):
        """Class to capture all value errors."""
        id: str = Field(
            ..., 
            description="Unique identifier for the error.", 
        )
        message: str = Field(
            ..., 
            description="The entire, and exact Value error message."
        )
        analysis: str = Field(
            ..., 
            description="Step-by-step analysis, mindful of the context of the error, of what went wrong and how to improve given the entire context of the invoice, error, your task, and instructions."
        )


    class ErrorHandling(BaseModel):
        """Class to capture all error handling information."""
        has_errors: bool = Field(
            default=False, 
            description="Flag indicating whether any value errors were raised"
        )
        errors: list[CaptureError] = Field(
            default_factory=list, 
            description="List of value errors, their messages, and analysis."
        )

    

    class InvoiceDetail(BaseModel):
        """
        This class captures all invoice details. Every extracted value must be explicitly stated. It's critical you extract the data with the greatest rigor and precision possible.
        """
        error_handling: ErrorHandling = Field(
            default_factory=ErrorHandling,
            description="Error handling information for the invoice processing"
        )

        invoice_date: str = Field(
            ..., 
            description="Provide the issuance date of the invoice in ISO 8601 format."
        )
        due_date: Optional[str] = Field(
            description="Provide the due date of the invoice in ISO 8601 format."
        )
        invoice_number: str = Field(
            ..., 
            description="Provide the unique identifier of the invoice."
        )

        currency: str = Field(
            default="EUR", 
            description="Provide the currency used in the invoice."
        )
        suppliers: List[SupplierFinancialDetails] = Field(
            ...,
            description="List the suppliers with their financial details. Capture each sub-supplier's details for aggregated invoices, or the main supplier if only one."
        )
        recipient: str = Field(
            ..., 
            description="Provide the name of the invoice recipient. The business (or person) that was billed to."
        )

        method_of_payment: Literal['Diversen', 'Ideal', 'Incasso', 'Online Bankieren', 'Betaalautomaat', 'Paypal', 'Credit Card'] = Field(
            ..., 
            description="Specify the method of payment used for the invoice. If not explicitly mentioned, infer from context (e.g., 'Online Bankieren' for 'pay within 30 days', 'Credit Card' for invoices with a non Euro currency like most SaaS, 'Incasso' for automatic deduction from bank account)."
        )
        primary_supplier: str = Field(
            ..., 
            description="Provide the name of the issuer of the invoice. This may differ from the sub-suppliers listed in 'suppliers' for aggregated invoices. Capture legal entity extensions like B.V. and V.O.F. without any dots.",
            examples=["Finqle BV", "Heineken Sligro Stichting Derdengelden"]
        )
        
        details_supplier: SupplierDetails = Field(
            ...,
            description="Key information about the issuer, the sender of the invoice."
        )

        total_emballage: Optional[Decimal] = Field(
            default=None, 
            description="The packaging costs (emballage, statiegeld). This is the netto amount of packaging costs that gets added, or deducted from the amount payable."
        )

        null_tax_base: Optional[Decimal] = Field(
            default=None, 
            description="The total amount that is not eligible for any VAT, i.e. 'null_tax_base'."
        )

        low_tax_base: Optional[Decimal] = Field(
            default=None,
            description="Provide the total amount eligible for low VAT (9%)."
        )
        high_tax_base: Optional[Decimal] = Field(
            default=None, 
            description="Provide the total amount eligible for high VAT (21%)."
        )
        low_tax: Optional[Decimal] = Field(
            default=None, 
            description="Provide the amount of low VAT (9%) charged."
        )
        high_tax: Optional[Decimal] = Field(
            default=None, 
            description="Provide the amount of high VAT (21%) charged."
        )
        amount_excl_tax: Optional[Decimal] = Field(
            default=None,
            description="The total base amount excluding taxes."
        )


        discount: Optional[Discount] = Field(
            default=None,
            description="Details about any discounts, credits, deductions, emballage, or statiegeld applied to the invoice."
        )

    # ... rest of the class ...

 

        amount_payable_citation: str = Field(
            ...,
            description=(
                "Act as a citation extraction tool. Your task is to identify and extract the exact text that contains the total amount payable (or incase the invoice is already paid, and the amount payable is zero, cite the total invoice amount). "
                "The citation must include a numerical value, possibly a currency symbol and any relevant context "
                "that clearly shows that the amount is the total amount payable. "
                "Relevant contexts include phrases such as 'Amount Due', 'Totaalbedrag,' 'Te Betalen Bedrag,' 'Totaal Te Betalen,' or 'Totaal.'"
                "If the citation spans multiple lines, include both lines in the citation including the all the text on the lines, separated new lines by a newline character "
            ),
            json_schema_extra={
                "examples": [
                    "Totaal €    -11.715,18",
                    "Due: 200.00 USD",
                    "Saldo verschuldigt: €15000",
                    "Totaal Te Betalen: 100.50",
                    "Totaal EUR incl. btw\n39,70",
                    "                                              Subtotal         VAT 21%                                         Total incl. VAT \n\n                                           € 4.331,25          € 909,56 \n                                                                                                    € 5.240,81"
                ]
            }
        )
        @model_validator(mode='before')
        def initialize_error_handling(cls, values):
            if 'error_handling' not in values:
                values['error_handling'] = ErrorHandling()
            return values

        @model_validator(mode='after')
        def validate_error_handling(self):
            if self.error_handling.has_errors and not self.error_handling.errors:
                raise ValueError(
                    f"#####START_VALUE_ERROR_MESSAGE#####\n"
                    f"value_error_id: '..'\n"
                    "This information is extracted from your last attempt to process the invoice."
                    "The following errors were found:"
                    "When 'has_errors' is True, at least one error must be provided.\n"
                    "#####END_VALUE_ERROR_MESSAGE#####\n"
                    "ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                )
            return self

        def add_error(self, id: str, message: str, analysis: str):
            if not self.error_handling.has_errors:
                self.error_handling.has_errors = True
            self.error_handling.errors.append(CaptureError(id=id, message=message, analysis=analysis))

        @model_validator(mode='after')
        def validate_discount(self) -> 'InvoiceDetail':
            if self.discount:
                if self.discount.type in ['emballage', 'statiegeld']:
                    self.discount = None
            return self

        @field_validator('amount_payable_citation', mode='after')
        @classmethod
        def check_amount_payable_citation(cls, v: str) -> str:
            def normalize_text(text):
                # Normalize whitespace, remove newlines, and extra spaces
                return ' '.join(text.replace('\n', ' ').split())

            normalized_citation = normalize_text(v)
            normalized_doc_text = normalize_text(doc_text)

            # Check for normalized match
            if normalized_citation in normalized_doc_text:
                return v  # Return original citation if normalized version is found

            # If no exact match, look for close matches
            best_match = ""
            best_ratio = 0
            for i in range(len(normalized_doc_text.split())):
                window = ' '.join(normalized_doc_text.split()[i:i+10])  # Check 10-word windows for more context
                ratio = SequenceMatcher(None, normalized_citation.lower(), window.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = window

            # Define a threshold for similarity (e.g., 0.8 for 80% similarity)
            similarity_threshold = 0.8

            if best_ratio >= similarity_threshold:
                return v  # Return original citation if a close match is found
            else:
                raise ValueError(
                    f"#####START_VALUE_ERROR_MESSAGE#####\n"
                    f"value_error_id: 'invalid_amount_payable_citation'\n"
                    f"Luca! Pay Attention! The information in the following message is extracted from your last attempt to process the invoice.\n"
                    f"You extracted '{v}' as the amount payable citation.\n"
                    f"This is not a direct quote from the document.\n"
                    f"The citation must be an exact, direct quote from the document that clearly shows the total amount payable.\n"
                    f"If the citation spans multiple lines, include both lines in the citation.\n"
                    f"The closest match found was: '{best_match}'\n"
                    f"Make sure to follow the citation instructions.\n"
                    f"Try a different approach, for example only extract the amount due (or invoiced) without context.\n"
                    f"If that does not work try to extract a citation with more context.\n"
                    f"#####END_VALUE_ERROR_MESSAGE#####\n"
                    f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                )
            
        amount_payable: Decimal = Field(
            ..., 
            description="The amount payable, this value must be present in the invoice and in the 'amount_payable_citation' field."
        )

        @model_validator(mode='after')
        def check_amount_payable_in_citation(self) -> 'InvoiceDetail':
            if self.amount_payable is not None and self.amount_payable_citation:
                # Convert Decimal to string and float
                amount_str = str(self.amount_payable)
                amount_float = float(amount_str)

                # Create patterns for different number formats
                patterns = [
                    re.escape(amount_str),  # Exact match (e.g., 1527.87)
                    re.escape(amount_str).replace(r'\.', r'[,.]'),  # Flexible decimal separator (e.g., 1527,87)
                    r'\b' + re.escape(f"{amount_float:,.2f}".replace(',', '')).replace(r'\.', r'[,.]').replace(r'\d+', r'\d{1,3}(?:[.,\s]\d{3})*') + r'\b',  # With thousands separator (e.g., 1.527,87 or 1,527.87 or 1 527,87)
                    r'\b' + re.escape(f"{amount_float:,.2f}".replace(',', '')).replace(r'\.', r'[,.]').replace(r'\d+', r'\d{1,3}(?:[\s]\d{3})*') + r'\b',  # Space as thousand separator (e.g., 1 527.87)
                    r'\b' + re.escape(f"{amount_float:.0f}") + r'[-.,]?-?\b',  # Whole number with optional decimal point or comma (e.g., 1527.- or 1527,-)
                    r'\b' + re.escape(f"{amount_float:.0f}".replace(r'\d+', r'\d{1,3}(?:[.,\s]\d{3})*')) + r'[-.,]?-?\b',  # Whole number with thousands separators and optional decimal point or comma (e.g., 1.527.- or 1,527,-)
                ]

                # Combine patterns
                combined_pattern = '|'.join(patterns)

                if not re.search(combined_pattern, self.amount_payable_citation, re.IGNORECASE):
                    # If not found, try to extract the number from the citation and compare
                    citation_numbers = re.findall(r'\b\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{2})?\b', self.amount_payable_citation)
                    for citation_number in citation_numbers:
                        cleaned_number = citation_number.replace('.', '').replace(',', '.').replace(' ', '')
                        if abs(float(cleaned_number) - float(amount_str)) < 0.01:  # Allow for small rounding differences
                            return self  # The numbers match, so we're good

                    raise ValueError(
                        f"#####START_VALUE_ERROR_MESSAGE#####\n"
                        f"value_error_id: 'amount_payable_not_found'\n"
                        f"This information is extracted from your last attempt to process the invoice.\n"
                        f"The amount payable '{self.amount_payable}' was not found in the citation '{self.amount_payable_citation}'. Please ensure the amount matches the citation exactly.\n"
                        f"#####END_VALUE_ERROR_MESSAGE#####\n"
                        )

            return self
    
        @field_validator('invoice_date', 'due_date', mode='before')
        @classmethod
        def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
            if v is None:
                return v
            try:
                # Attempt to parse the date to ensure it's in ISO 8601 format
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError as e:
                raise ValueError(
                    f"#####START_VALUE_ERROR_MESSAGE#####\n"
                    f"value_error_id: 'invalid_date_format'\n"
                    f"This information is extracted from your last attempt to process the invoice.\n"
                    f"Date {v} is not in ISO 8601 format (YYYY-MM-DD).\n"
                    f"#####END_VALUE_ERROR_MESSAGE#####\n"
                    ) from e
            return v

        @field_validator('currency', mode='before')
        @classmethod
        def convert_currency(cls, v: str) -> str:
            return v.replace('EURO', 'EUR')
        
        @field_validator('primary_supplier', mode='before')
        @classmethod
        def clean_and_format_primary_supplier_name(cls, v: str) -> str:
            # Handle legal entity extensions
            v = re.sub(r'\b(b\.?\s*v\.?|ltd\.?|v\.?\s*o\.?\s*f\.?)\b', 
                    lambda m: m.group(1).replace('.', '').replace(' ', '').upper(), 
                    v, 
                    flags=re.IGNORECASE)
            
            # Overwrite if 'sligro' is in the value
            if v and 'sligro' in v.lower() and v != "Heineken Sligro Stichting Derdengelden":
                v = "Heineken Sligro Stichting Derdengelden"
            
            # Split the name into parts
            parts = v.split()
            
            # Capitalize each part unless it's a legal entity extension
            return ' '.join([part if part in ['BV', 'LTD', 'VOF'] else part.capitalize() for part in parts])

        @field_validator('recipient', mode='after')
        @classmethod
        def normalize_recipient(cls, v: str) -> str:
            recipient_map = {
                'louisiana': 'Louisiana Lobstershack BV',
                'lobstershack': 'Louisiana Lobstershack BV',
                'step': 'Step into Liquid BV',
                'fausto': 'Fausto Albers',
                'albers': 'Fausto Albers',
                'benedek': 'Louisiana Lobstershack BV',
                'gaal': 'Louisiana Lobstershack BV',
                'waitler': 'Bar Bonds BV',
                'barbonds': 'Bar Bonds BV',
                'bar bonds': 'Bar Bonds BV'
            }
            key = v.lower()
            for k, normalized in recipient_map.items():
                if k in key:
                    return normalized
            return v

        @model_validator(mode='after')
        def validate_amount_excl_tax(self) -> Self:
            """Validate that the amount_excl_tax matches the sum of the tax bases for all suppliers."""
            if self.amount_excl_tax is not None:
                suppliers = self.suppliers
                total_low_tax_base = sum(supplier.low_tax_base or Decimal('0') for supplier in suppliers)
                total_high_tax_base = sum(supplier.high_tax_base or Decimal('0') for supplier in suppliers)
                total_null_tax_base = sum(supplier.null_tax_base or Decimal('0') for supplier in suppliers)
                expected_amount_excl_tax = total_low_tax_base + total_high_tax_base + total_null_tax_base

                # Define a small tolerance for rounding errors (e.g., 0.05)
                tolerance = Decimal('0.05')

                if abs(self.amount_excl_tax - expected_amount_excl_tax) > tolerance:
                    raise ValueError(
                        f"#####START_VALUE_ERROR_MESSAGE#####\n"
                        f"value_error_id: 'amount_excl_tax_mismatch'\n"
                        f"This information is extracted from your last attempt to process the invoice.\n"
                        f"The amount_excl_tax ({self.amount_excl_tax}) does not match the expected value ({expected_amount_excl_tax}).\n"
                        f"This was calculated by summing up the low_tax_base {total_low_tax_base}, high_tax_base {total_high_tax_base} and null_tax_base {total_null_tax_base} for the supplier(s)\n"
                        f"The total amount_excl_tax {expected_amount_excl_tax} as captured by you is {self.amount_excl_tax}.\n"
                        f"The difference ({abs(self.amount_excl_tax - expected_amount_excl_tax)}) exceeds the allowed tolerance of {tolerance}.\n"
                        f"Common mistakes include mistakes with mixing up packaging costs, null_tax_base or discounts.\n"
                        f"But you might have made another mistake. Check your data and make sure you have the correct amount_excl_tax.\n"
                        f"#####END_VALUE_ERROR_MESSAGE#####\n"
                        f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                    )
            return self
        
        @model_validator(mode='after')
        def validate_tax_bases_and_taxes(self) -> Self:
            """Validate that tax bases and taxes are non-negative and match expected totals."""
            
            # Ensure tax bases and taxes are non-negative
            for supplier in self.suppliers:
                if (supplier.low_tax_base or Decimal('0')) < 0:
                    raise ValueError(f"low_tax_base for supplier '{supplier.supplier}' cannot be negative.")
                if (supplier.high_tax_base or Decimal('0')) < 0:
                    raise ValueError(f"high_tax_base for supplier '{supplier.supplier}' cannot be negative.")
                if (supplier.null_tax_base or Decimal('0')) < 0:
                    raise ValueError(f"null_tax_base for supplier '{supplier.supplier}' cannot be negative.")
                if (supplier.low_tax or Decimal('0')) < 0:
                    raise ValueError(f"low_tax for supplier '{supplier.supplier}' cannot be negative.")
                if (supplier.high_tax or Decimal('0')) < 0:
                    raise ValueError(f"high_tax for supplier '{supplier.supplier}' cannot be negative.")
            
            tolerance = Decimal('0.05')

            total_null_tax_base = sum(supplier.null_tax_base or Decimal('0') for supplier in self.suppliers)
            total_low_tax_base = sum(supplier.low_tax_base or Decimal('0') for supplier in self.suppliers)
            total_high_tax_base = sum(supplier.high_tax_base or Decimal('0') for supplier in self.suppliers)
            total_low_tax = sum(supplier.low_tax or Decimal('0') for supplier in self.suppliers)
            total_high_tax = sum(supplier.high_tax or Decimal('0') for supplier in self.suppliers)

            expected_amount_excl_tax = total_low_tax_base + total_high_tax_base + total_null_tax_base

            if self.amount_excl_tax is not None:
                if abs(self.amount_excl_tax - expected_amount_excl_tax) > tolerance:
                    raise ValueError(
                        f"Amount excluding tax ({self.amount_excl_tax}) does not match the expected total ({expected_amount_excl_tax}). "
                        f"Difference of {abs(self.amount_excl_tax - expected_amount_excl_tax)} exceeds tolerance of {tolerance}."
                    )
            
            # Additional validations can be added here as needed

            return self


  
        @model_validator(mode='before')
        @classmethod
        def convert_to_decimal(cls, values):
            decimal_fields = [
                'high_tax_base', 'high_tax', 'amount_excl_tax', 'amount_payable',
                'low_tax_base', 'low_tax', 'null_tax_base', 'total_emballage'
            ]
            
            for field in decimal_fields:
                if field in values and values[field] is not None:
                    try:
                        values[field] = Decimal(str(values[field]))
                    except decimal.InvalidOperation:
                        raise ValueError(f"Invalid decimal value for field '{field}': {values[field]}")
            
            if 'suppliers' in values and isinstance(values['suppliers'], list):
                for supplier in values['suppliers']:
                    for field in decimal_fields:
                        if field in supplier and supplier[field] is not None:
                            try:
                                supplier[field] = Decimal(str(supplier[field]))
                            except decimal.InvalidOperation:
                                raise ValueError(f"Invalid decimal value for supplier field '{field}': {supplier[field]}")
            
            if 'discount' in values and values['discount'] is not None:
                if 'discount_amount' in values['discount']:
                    try:
                        values['discount']['discount_amount'] = Decimal(str(values['discount']['discount_amount']))
                    except decimal.InvalidOperation:
                        raise ValueError(f"Invalid decimal value for discount_amount: {values['discount']['discount_amount']}")
            
            return values

          # Detailed documentation of the validator. This validator is the most complex one, and it's responsible for ensuring that the sum of tax bases, taxes, and emballage for each supplier equals amount_payable. This is how it works: First, it sums up the tax bases and taxes for each supplier. Then, it rounds these totals to the nearest cent. It then checks if the sum of these totals is within the tolerance of 0.05 of the amount_payable. If it is, the validator returns the invoice as is. If it isn't, it falls back to a second check, which checks if the sum of the tax bases and taxes plus the emballage is within the tolerance of 0.05 of the amount_payable. If it is, the validator returns the invoice as is. If it isn't, it falls back to a third check, which checks if the sum of the tax bases and taxes plus the discount is within the tolerance of 0.05 of the amount_payable. If it is, the validator returns the invoice as is. If it isn't, it falls back to a fourth check, which checks if the sum of the tax bases and taxes plus the emballage plus the discount is within the tolerance of 0.05 of the amount_payable. If it is, the validator returns the invoice as is. If it isn't, it raises a ValueError with a detailed message explaining the problem and providing an analysis of the error.

        @model_validator(mode='after')
        def validate_total_amount_payable(self) -> Self:
            """Ensure the sum of tax bases, taxes, and emballage for each supplier equals amount_payable."""
            def round_decimal(value: Decimal) -> Decimal:
                return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            total_tax_bases = sum(
                (supplier.low_tax_base or Decimal('0')) +
                (supplier.high_tax_base or Decimal('0')) +
                (supplier.null_tax_base or Decimal('0'))
                for supplier in self.suppliers
            )
            total_taxes = sum(
                (supplier.low_tax or Decimal('0')) +
                (supplier.high_tax or Decimal('0'))
                for supplier in self.suppliers
            )
            base_amount = round_decimal(total_tax_bases + total_taxes)

            tolerance = Decimal('0.05')

            if self.amount_payable is None:
                raise ValueError("amount_payable cannot be None")

            # Check 1: Base amount (without emballage and discount)
            if abs(base_amount - self.amount_payable) <= tolerance:
                return self

            # Check 2: Base amount + emballage
            amount_with_emballage = base_amount
            if self.total_emballage is not None:
                amount_with_emballage = round_decimal(amount_with_emballage + self.total_emballage)
            if abs(amount_with_emballage - self.amount_payable) <= tolerance:
                return self

            # Check 3: Base amount + discount (if present)
            amount_with_discount = base_amount
            if self.discount and self.discount.discount_amount is not None:
                amount_with_discount = round_decimal(amount_with_discount + self.discount.discount_amount)
            if abs(amount_with_discount - self.amount_payable) <= tolerance:
                return self

            # Check 4: Base amount + emballage + discount (if present)
            total_amount = amount_with_emballage
            if self.discount and self.discount.discount_amount is not None:
                total_amount = round_decimal(total_amount + self.discount.discount_amount)
            if abs(total_amount - self.amount_payable) <= tolerance:
                return self

            # If all checks fail, raise the error
            raise ValueError(
                f"#####START_VALUE_ERROR_MESSAGE#####\n"
                f"value_error_id: '..'\n"
                f"Luca! Pay Attention! The information and data in the following message were extracted from your last attempt to process the invoice for {self.primary_supplier}. Brilliant you are, but as an AI, you are stateless and have no persistent memory of previous attempts. The ValueError that was raised can thus serve as a digital memory to avoid making the same mistakes in the current attempt.\n"
                f"The amount payable you found last time was {self.amount_payable}, and this did not match at least one of the requirements of the required matching logic.\n"
                f"Validation_A 'sum tax base + sum taxes' got: {base_amount}, difference: {abs(base_amount - self.amount_payable)}.\n"
                f"Validation_B 'sum tax base + sum taxes + emballage' got: {amount_with_emballage}, difference: {abs(amount_with_emballage - self.amount_payable)}.\n"
                f"Validation_C 'sum tax base + sum taxes + discount' got: {amount_with_discount}, difference: {abs(amount_with_discount - self.amount_payable)}.\n"
                f"Validation_D 'sum tax base + sum taxes + emballage + discount' got: {total_amount}, difference: {abs(total_amount - self.amount_payable)}.\n"
                f"At least one of the differences has to be within the tolerance of {tolerance} to pass the validation.\n"
                f"The following historic data from your last call is helpful to understand what went wrong: You found:\n"
                f"  - amount_payable: {self.amount_payable}\n"
                f"  - null_tax_base: {self.null_tax_base}\n"
                f"  - low_tax_base: {self.low_tax_base}\n"
                f"  - high_tax_base: {self.high_tax_base}\n"
                f"  - amount_excl_tax: {self.amount_excl_tax}\n"
                f"  - low_tax: {self.low_tax}\n"
                f"  - high_tax: {self.high_tax}\n"
                f"  - Emballage amount: {self.total_emballage or 'Not specified'}.\n"
                f"  - Discount: {self.discount.discount_amount if self.discount else 'Not specified'}.\n"
                f"#####END_VALUE_ERROR_MESSAGE#####\n"
                f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
            )

        @model_validator(mode='after')
        def filter_null_suppliers(self) -> Self:
            """Filter out suppliers with all null fields except supplier_name, and observation."""
            self.suppliers = [supplier for supplier in self.suppliers if not all(
                getattr(supplier, field) is None
                for field in supplier.model_fields
                if field not in ['supplier', 'observation']
            )]
            return self
    
    async with sem:
        if re.search(r'statiegeld|emballage', data, re.IGNORECASE):
            additional_info = emballage_info
        else:
            additional_info = ""

        messages = [
            {
                "role": "system",
                "content": f"""Your name is Luca, you are a sophisticated extraction and classification algorithm. You are tasked with processing invoices for user.
                
                    **User Profile**: Take the context of the user into consideration when making decisions.
                    {user_info}

                    ###
                    {additional_info}

                    ###Critical Instructions for Data Extraction:
                    You are tasked with extracting data from invoices and must adhere to the following guidelines strictly:

                    1. Truthfulness and Accuracy:
                    - Extreme accuracy and precision is a matter of life and death.
                    - Great pain will be caused if you make mistakes.
                    - You must not make mistakes.
                    2. Error Handling:
                    - If you encounter the phrase "Luca! Pay Attention!", it indicates a failure in your last attempt, you only get one chance to correct the mistake.
                    - After the phrase "Luca! Pay Attention!", an error message will follow, providing specific instructions to correct the mistake.
                    - If you see the phrase again, apply the instructions from the latest error message to rectify the issue with great rigor.

                    By following these instructions, you ensure the integrity and accuracy of the extracted data, minimizing errors and maintaining compliance with validation requirements. 
                """
            },
            {
                "role": "user",
                "content": f"Here is the invoice:\n{data}"
            }
        ]

        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                top_p=0.9,
                response_model=InvoiceDetail,
                max_retries=2,
                messages=messages
            )
            # Convert the Pydantic model to a dictionary using model_dump()
            return JSONResponse(content=response.model_dump(mode='json'))
        except Exception as e:
            print(colored(f"Error processing text file: {str(e)}", "red"))
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def home(request: Request):
    try:
        print(colored("Serving home page...", "yellow"))
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "AI Invoice Processor"
        })
    except Exception as e:
        print(colored(f"Error serving home page: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_receipt(file: UploadFile = File(...)):
    try:
        print(colored(f"Processing uploaded file: {file.filename}", "yellow"))
        
        # Read and decode the text file
        contents = await file.read()
        text_content = contents.decode('utf-8')
        
        # Process with GPT-4 using the defined get_invoice_detail function
        result = await get_invoice_detail(text_content, file.filename)
        
        return result  # Now result is already a JSONResponse
        
    except Exception as e:
        print(colored(f"Error processing text file: {str(e)}", "red"))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

