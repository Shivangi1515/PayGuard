from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    database: Optional[str] = None


class IntentContract(BaseModel):
    raw_request: Optional[str] = Field(
        default=None,
        description="Original user natural language purchase request"
    )
    product_type: str = Field(
        ...,
        min_length=1,
        description="Target category or product type (e.g., 'Laptop', 'Smartphone', 'Headphones')",
    )
    purpose: str = Field(
        default="General Purchase",
        description="Intended usage/purpose extracted from the request (e.g., 'Coding', 'Gaming', 'Travel')",
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
        description="List of specific feature preferences (e.g., ['16GB RAM', 'Active Noise Cancellation'])",
    )
    payment_authorized: bool = Field(
        default=False,
        description="Indicates whether the user explicitly stated payment authorization intent in their request. NOTE: LLM does not grant financial authorization.",
    )

    @field_validator("max_budget", mode="before")
    @classmethod
    def validate_budget(cls, v):
        if isinstance(v, (int, float)):
            if v <= 0:
                raise ValueError("max_budget must be greater than 0.")
            return float(v)
        if isinstance(v, str):
            # Clean possible currency symbols or commas e.g. "₹1,50,000" or "150000 INR"
            cleaned = v.replace("₹", "").replace("INR", "").replace("Rs", "").replace("rs", "").replace(",", "").strip()
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
        min_length=3,
        description="Natural language purchase request",
        example="I need a high-performance laptop for coding and video editing under 150000 rupees. Need at least 16GB RAM.",
    )
