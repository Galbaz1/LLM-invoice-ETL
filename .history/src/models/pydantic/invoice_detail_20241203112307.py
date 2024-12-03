from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator, field_validator
from datetime import datetime
import re
from difflib import SequenceMatcher
from .invoice import (
    SupplierFinancialDetails,
    SupplierDetails,
    Discount,
    ErrorHandling,
    quantize_decimal
)

class InvoiceDetail(BaseModel):
    """
    Main class that captures all invoice details. Every extracted value must be explicitly stated.
    It's critical to extract the data with the greatest rigor and precision possible.
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
        description="List the suppliers with their financial details."
    )
    recipient: str = Field(
        ..., 
        description="Provide the name of the invoice recipient."
    )

    method_of_payment: Literal['Diversen', 'Ideal', 'Incasso', 'Online Bankieren', 'Betaalautomaat', 'Paypal', 'Credit Card'] = Field(
        ..., 
        description="Specify the method of payment used for the invoice."
    )
    primary_supplier: str = Field(
        ..., 
        description="Provide the name of the issuer of the invoice.",
        examples=["Finqle BV", "Heineken Sligro Stichting Derdengelden"]
    )
    
    details_supplier: SupplierDetails = Field(
        ...,
        description="Key information about the issuer."
    )

    total_emballage: Optional[Decimal] = Field(
        default=None, 
        description="The packaging costs (emballage, statiegeld)."
    )

    discount: Optional[Discount] = Field(
        default=None,
        description="Any discounts, credits, or deductions applied."
    )

    amount_payable_citation: str = Field(
        ...,
        description="Direct quote from the document showing the total amount payable."
    )

    amount_payable: Decimal = Field(
        ..., 
        description="The amount payable, must be present in amount_payable_citation."
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
        # Remove common currency symbols and whitespace
        cleaned_citation = re.sub(r'[€$£¥]|\s+', '', v)
        
        # Find all potential amounts in the citation
        amount_pattern = r'\d+(?:[.,]\d{2})?'
        amounts_in_citation = re.findall(amount_pattern, cleaned_citation)
        
        if not amounts_in_citation:
            raise ValueError(
                f"#####START_VALUE_ERROR_MESSAGE#####\n"
                f"value_error_id: 'no_amount_in_citation'\n"
                f"Luca! Pay Attention! The citation '{v}' does not contain any recognizable amounts.\n"
                f"The citation must include the total amount payable.\n"
                f"#####END_VALUE_ERROR_MESSAGE#####\n"
                f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
            )
        
        # Find the best matching amount using string similarity
        similarity_threshold = 0.7
        best_ratio = 0
        best_match = None
        
        for amount in amounts_in_citation:
            ratio = SequenceMatcher(None, v, amount).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = amount

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

            # Check if any pattern matches the citation
            citation_matches = False
            for pattern in patterns:
                if re.search(pattern, self.amount_payable_citation):
                    citation_matches = True
                    break

            if not citation_matches:
                raise ValueError(
                    f"#####START_VALUE_ERROR_MESSAGE#####\n"
                    f"value_error_id: 'amount_payable_mismatch'\n"
                    f"Luca! Pay Attention! The information in the following message is extracted from your last attempt to process the invoice.\n"
                    f"The amount payable ({self.amount_payable}) does not appear in the citation: '{self.amount_payable_citation}'.\n"
                    f"The amount payable must be present in the citation.\n"
                    f"Make sure to extract a citation that includes the exact amount payable.\n"
                    f"#####END_VALUE_ERROR_MESSAGE#####\n"
                    f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
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
        """Validate that the amount excluding tax matches the sum of tax bases"""
        total_tax_base = Decimal('0')
        
        for supplier in self.suppliers:
            if supplier.amount_excl_tax is not None:
                # If supplier has amount_excl_tax, validate against tax bases
                total_bases = Decimal('0')
                if supplier.high_tax_base is not None:
                    total_bases += supplier.high_tax_base
                if supplier.low_tax_base is not None:
                    total_bases += supplier.low_tax_base
                if supplier.null_tax_base is not None:
                    total_bases += supplier.null_tax_base
                
                if total_bases > 0 and abs(supplier.amount_excl_tax - total_bases) > Decimal('0.02'):
                    raise ValueError(
                        f"#####ValueError#####\n"
                        f"value_error_id: 'invalid_amount_excl_tax'\n"
                        f"The amount excluding tax ({supplier.amount_excl_tax}) does not match "
                        f"the sum of tax bases ({total_bases}).\n"
                        f"#####END_VALUE_ERROR_MESSAGE#####\n"
                        f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                    )
            
            # Add to total for all suppliers
            if supplier.amount_excl_tax is not None:
                total_tax_base += supplier.amount_excl_tax
        
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