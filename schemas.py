from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    database: Optional[str] = None


class IntentContract(BaseModel):
    product_type: str = Field(
        ...,
        min_length=1,
        description="Target category or product type (e.g., 'Laptop', 'Smartphone', 'Headphones')",
    )
    purpose: str = Field(
        default="general purchase",
        description="Intended usage/purpose extracted from the request (e.g., 'coding', 'gaming', 'office')",
    )
    max_budget: float = Field(
        ...,
        gt=0,
        description="Maximum budget allocated by the user in INR",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of units requested",
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="List of specific feature preferences",
    )
    payment_authorized: bool = Field(
        default=False,
        description="Indicates whether the user explicitly intended payment authorization in their request",
    )

    @field_validator("max_budget", mode="before")
    @classmethod
    def validate_budget(cls, v):
        if isinstance(v, (int, float)):
            if v <= 0:
                raise ValueError("max_budget must be greater than 0.")
            return float(v)
        if isinstance(v, str):
            cleaned = (
                v.replace("₹", "")
                .replace("INR", "")
                .replace("Rs", "")
                .replace("rs", "")
                .replace(",", "")
                .strip()
            )
            try:
                val = float(cleaned)
                if val <= 0:
                    raise ValueError("max_budget must be greater than 0.")
                return val
            except ValueError:
                raise ValueError(f"Invalid numeric budget value: '{v}'")
        raise ValueError("max_budget must be a valid positive number.")

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, v):
        try:
            qty = int(v)
            if qty < 1:
                return 1
            return qty
        except (ValueError, TypeError):
            return 1


class PurchaseIntentRequest(BaseModel):
    request: str = Field(
        ...,
        min_length=1,
        description="Natural language purchase request",
        example="Buy me a laptop for coding under 80000, quantity 1",
    )
