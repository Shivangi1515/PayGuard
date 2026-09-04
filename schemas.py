from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class HealthResponse(BaseModel):
    status: str
    database: Optional[str] = None


class PurchaseIntentRequest(BaseModel):
    request: str = Field(
        ...,
        min_length=1,
        description="Natural language purchase request",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request": "Buy me a laptop for coding under 80000, quantity 1"
            }
        }
    )


class IntentContractResponse(BaseModel):
    intent_contract_id: int = Field(
        ...,
        gt=0,
        description="Actual generated PostgreSQL database ID for the IntentContract",
    )
    product_type: str = Field(
        ...,
        description="Category or product type extracted by Intent Agent (e.g. Laptop)",
    )
    purpose: str = Field(
        ...,
        description="Extracted purpose for the purchase (e.g. coding)",
    )
    max_budget: float = Field(
        ...,
        gt=0,
        description="Maximum budget extracted in INR",
    )
    quantity: int = Field(
        ...,
        ge=1,
        description="Extracted quantity requested",
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="List of specific feature preferences",
    )
    payment_authorized: bool = Field(
        ...,
        description="Whether user explicitly intended payment authorization in raw request",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_contract_id": 1,
                "product_type": "Laptop",
                "purpose": "coding",
                "max_budget": 80000.0,
                "quantity": 1,
                "preferences": [],
                "payment_authorized": True,
            }
        }
    )


class IntentContract(BaseModel):
    """Internal model returned by IntentAgent after LLM extraction."""
    product_type: str = Field(
        ...,
        min_length=1,
        description="Target category or product type",
    )
    purpose: str = Field(
        default="general purchase",
        description="Intended usage/purpose extracted from the request",
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
        description="Indicates whether payment authorization was declared by user",
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


class BuyRequest(BaseModel):
    intent_contract_id: int = Field(
        ...,
        gt=0,
        description="ID of an existing IntentContract from PostgreSQL",
        json_schema_extra={"example": 1},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_contract_id": 1
            }
        }
    )


class PurchaseProposal(BaseModel):
    product_id: int = Field(..., description="ID of the selected product")
    product_name: str = Field(..., description="Name of the selected product")
    quantity: int = Field(default=1, ge=1, description="Quantity proposed for purchase")
    base_price: float = Field(..., description="Base price in INR")
    shipping_charge: float = Field(..., description="Shipping charge in INR")
    tax: float = Field(..., description="Applicable tax in INR")
    final_amount: float = Field(..., description="Final calculated amount (base_price + shipping + tax)")
    reason: str = Field(..., description="Explanation from Buyer Agent why this candidate was selected")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": 6,
                "product_name": "Acer Swift Go 14",
                "quantity": 1,
                "base_price": 59990.0,
                "shipping_charge": 250.0,
                "tax": 10798.2,
                "final_amount": 71038.2,
                "reason": "Acer Swift Go 14 is the optimal laptop for coding under 80000 INR with 16GB RAM and OLED display."
            }
        }
    )
