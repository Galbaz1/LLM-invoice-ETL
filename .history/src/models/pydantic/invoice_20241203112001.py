from typing import List, Literal, Optional, Union, Annotated, Self, Set
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, ValidationInfo, field_validator, model_validator
from datetime import datetime
import re
from termcolor import colored

def quantize_decimal(value: Decimal) -> Decimal:
    """Helper function to quantize decimal values to 2 decimal places"""
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal('0.01'))

class SupplierFinancialDetails(BaseModel):
    """Financial details for each supplier on the invoice."""
    high_tax_base: Optional[Decimal] = Field(
        default=None,
        description="The base amount for the high tax rate (21%)."
    )
    high_tax: Optional[Decimal] = Field(
        default=None,
        description="The tax amount for the high tax rate (21%)."
    )
    low_tax_base: Optional[Decimal] = Field(
        default=None,
        description="The base amount for the low tax rate (9%)."
    )
    low_tax: Optional[Decimal] = Field(
        default=None,
        description="The tax amount for the low tax rate (9%)."
    )
    null_tax_base: Optional[Decimal] = Field(
        default=None,
        description="The base amount for the null tax rate (0%)."
    )
    amount_excl_tax: Optional[Decimal] = Field(
        default=None,
        description="The total amount excluding tax."
    )

    @model_validator(mode='after')
    def validate_taxes(self) -> Self:
        """Validate that high and low base tax are logically sound given the provided high and low tax"""
        def validate_tax_pair(tax: Optional[Decimal], base: Optional[Decimal], rate: Decimal, tax_name: str):
            if tax is not None and base is not None:
                # Both tax and base are provided, validate their relationship
                expected_tax = quantize_decimal(base * rate)
                if abs(tax - expected_tax) > Decimal('0.02'):
                    raise ValueError(
                        f"#####ValueError#####\n"
                        f"value_error_id: 'invalid_{tax_name}_tax_calculation'\n"
                        f"The {tax_name} tax amount ({tax}) does not match the expected amount ({expected_tax}) "
                        f"calculated from the {tax_name} tax base ({base}) at rate {rate}.\n"
                        f"#####END_VALUE_ERROR_MESSAGE#####\n"
                        f"ValueError (ID) was raised, you must set 'flag_value_error' to TRUE and provide the exact error message, and an analysis of the error."
                    )
            elif tax is not None:
                # Only tax is provided, calculate the base
                self.__dict__[f"{tax_name}_tax_base"] = quantize_decimal(tax / rate)
            elif base is not None:
                # Only base is provided, calculate the tax
                self.__dict__[f"{tax_name}_tax"] = quantize_decimal(base * rate)

        # Validate high tax (21%)
        validate_tax_pair(self.high_tax, self.high_tax_base, Decimal('0.21'), 'high')
        
        # Validate low tax (9%)
        validate_tax_pair(self.low_tax, self.low_tax_base, Decimal('0.09'), 'low')

        # Calculate amount_excl_tax if not provided
        if self.amount_excl_tax is None:
            total = Decimal('0')
            if self.high_tax_base is not None:
                total += self.high_tax_base
            if self.low_tax_base is not None:
                total += self.low_tax_base
            if self.null_tax_base is not None:
                total += self.null_tax_base
            if total > 0:
                self.amount_excl_tax = quantize_decimal(total)

        return self

class SupplierDetails(BaseModel):
    """Business details of the issuer of the invoice"""
    email: Optional[EmailStr] = Field(
        default=None,
        description="The email address of the issuer."
    )
    address: Optional[str] = Field(
        default=None,
        description="The physical address of the issuer."
    )
    iban: Optional[str] = Field(
        default=None,
        description="The IBAN number of the issuer.",
        example="NL123456789B01"
    )
    vat_id: Optional[str] = Field(
        default=None,
        description="The VAT (BTW) id of the issuer.",
        example="NL123456789B01"
    )
    kvk: Optional[str] = Field(
        default=None,
        description="The Chamber of Commerce registration number (KVK)."
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
    """Base class for discounts, credits, or deductions."""
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
    """Detailed discount information including type and reason."""
    type: Literal['discount', 'credit', 'deduction'] = Field(...)
    reason: str = Field(..., description="The reason for the discount, credit, or deduction.")

class SimpleDiscount(DiscountBase):
    """Simple discount for packaging or statiegeld."""
    type: Literal['emballage', 'statiegeld'] = Field(...)

# Define the Discount type using Union
Discount = Union[DetailedDiscount, SimpleDiscount]

class CaptureError(BaseModel):
    """Class to capture all value errors."""
    id: str = Field(
        ..., 
        description="Unique identifier for the error."
    )
    message: str = Field(
        ..., 
        description="The entire, and exact Value error message."
    )
    analysis: str = Field(
        ..., 
        description="Step-by-step analysis of what went wrong and how to improve."
    )

class ErrorHandling(BaseModel):
    """Class to capture all error handling information."""
    has_errors: bool = Field(
        default=False, 
        description="Flag indicating whether any value errors were raised"
    )
    errors: List[CaptureError] = Field(
        default_factory=list, 
        description="List of value errors, their messages, and analysis."
    ) 