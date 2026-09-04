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


class DriftCheck(BaseModel):
    drift_type: str = Field(..., description="Type of drift detected (e.g. budget drift, quantity drift, preference drift)")
    detected: bool = Field(..., description="True if this specific drift is present")
    explanation: str = Field(..., description="Explanation of the drift check outcome")


class DriftReport(BaseModel):
    has_drift: bool = Field(..., description="True if any drift was detected")
    drift_types: List[str] = Field(default_factory=list, description="List of detected drift types")
    explanations: List[str] = Field(default_factory=list, description="List of drift descriptions")
    summary: str = Field(..., description="Summary of drift analysis")
    checks: List[DriftCheck] = Field(default_factory=list, description="Individual drift checks")


class AlternativeAttempt(BaseModel):
    attempt_number: int = Field(..., description="Attempt number (1 to 3)")
    product_id: int = Field(..., description="Candidate product ID")
    product_name: str = Field(..., description="Candidate product name")
    final_amount: float = Field(..., description="Candidate final calculated amount in INR")
    drift_detected: bool = Field(..., description="Whether this candidate exhibited drift")
    drift_types: List[str] = Field(default_factory=list, description="Types of drift detected if any")
    rejected_reason: Optional[str] = Field(default=None, description="Reason for rejection if candidate drifted")


class PurchaseProposal(BaseModel):
    product_id: int = Field(..., description="ID of the selected product")
    product_name: str = Field(..., description="Name of the selected product")
    quantity: int = Field(default=1, ge=1, description="Quantity proposed for purchase")
    base_price: float = Field(..., description="Base price in INR")
    shipping_charge: float = Field(..., description="Shipping charge in INR")
    tax: float = Field(..., description="Applicable tax in INR")
    final_amount: float = Field(..., description="Final calculated amount (base_price + shipping + tax)")
    reason: str = Field(..., description="Explanation from Buyer Agent why this candidate was selected")
    drift_detected: bool = Field(default=False, description="Whether the selected proposal has drift")
    drift_reasons: List[str] = Field(default_factory=list, description="Detected drift reasons if any")
    attempts_count: int = Field(default=1, description="Total candidate search attempts made (up to 3)")
    alternative_selected: bool = Field(default=False, description="True if an alternative was chosen after initial drift")
    attempts_history: List[AlternativeAttempt] = Field(default_factory=list, description="Audit trail of candidate attempts")

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
                "reason": "Acer Swift Go 14 is the optimal laptop for coding under 80000 INR with 16GB RAM and OLED display.",
                "drift_detected": False,
                "drift_reasons": [],
                "attempts_count": 1,
                "alternative_selected": False,
                "attempts_history": [
                    {
                        "attempt_number": 1,
                        "product_id": 6,
                        "product_name": "Acer Swift Go 14",
                        "final_amount": 71038.2,
                        "drift_detected": False,
                        "drift_types": [],
                        "rejected_reason": None
                    }
                ]
            }
        }
    )


class VerifyRequest(BaseModel):
    intent_contract_id: int = Field(..., gt=0, description="ID of IntentContract from PostgreSQL")
    product_id: int = Field(..., gt=0, description="ID of Product to verify")
    quantity: int = Field(default=1, ge=1, description="Quantity proposed for purchase")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_contract_id": 1,
                "product_id": 6,
                "quantity": 1
            }
        }
    )


class VerificationCheck(BaseModel):
    check_name: str = Field(..., description="Identifier for the check")
    status: str = Field(..., description="'PASS' or 'FAIL'")
    explanation: str = Field(..., description="Detailed explanation of the check outcome")


class VerificationResponse(BaseModel):
    decision: str = Field(..., description="Final policy decision: 'APPROVE', 'ASK_USER', or 'BLOCK'")
    reason: str = Field(..., description="Detailed rationale for the final decision")
    checks: List[VerificationCheck] = Field(..., description="Individual verification check outcomes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "decision": "APPROVE",
                "reason": "All verification checks passed, payment authorized, and transaction within budget and policy limits.",
                "checks": [
                    {
                        "check_name": "category_match",
                        "status": "PASS",
                        "explanation": "Product category 'Laptops' matches requested type 'Laptop'."
                    },
                    {
                        "check_name": "purpose_relevance",
                        "status": "PASS",
                        "explanation": "Product description matches purpose 'coding'."
                    },
                    {
                        "check_name": "quantity_limit",
                        "status": "PASS",
                        "explanation": "Proposed quantity (1) does not exceed requested quantity (1)."
                    },
                    {
                        "check_name": "stock_availability",
                        "status": "PASS",
                        "explanation": "Product is in stock (20 available, 1 requested)."
                    },
                    {
                        "check_name": "pricing_calculation",
                        "status": "PASS",
                        "explanation": "Final amount (INR 71038.20) equals base price (INR 59990.00) + shipping (INR 250.00) + tax (INR 10798.20)."
                    }
                ]
            }
        }
    )


class CreatePaymentRequest(BaseModel):
    intent_contract_id: int = Field(..., gt=0, description="ID of IntentContract from PostgreSQL")
    product_id: int = Field(..., gt=0, description="ID of Product to purchase")
    quantity: int = Field(default=1, ge=1, description="Quantity proposed for purchase")
    user_confirmed: bool = Field(default=False, description="Set true if user has confirmed high-value transaction")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent_contract_id": 1,
                "product_id": 6,
                "quantity": 1,
                "user_confirmed": False
            }
        }
    )


class PaymentOrderResponse(BaseModel):
    transaction_id: int = Field(..., description="Internal PostgreSQL transaction record ID")
    razorpay_order_id: str = Field(..., description="Razorpay order ID (e.g. order_OPsXz...)")
    razorpay_key_id: str = Field(..., description="Public Razorpay key ID for client-side checkout")
    amount: float = Field(..., description="Validated total amount in INR")
    amount_in_paise: int = Field(..., description="Total amount in smallest currency sub-unit (paise)")
    currency: str = Field(default="INR", description="Currency code")
    status: str = Field(..., description="Transaction status (e.g. ORDER_CREATED)")
    policy_decision: str = Field(..., description="Policy Engine evaluation decision (e.g. APPROVE)")
    policy_reason: str = Field(..., description="Policy Engine rationale")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transaction_id": 1,
                "razorpay_order_id": "order_TY4GJflFcXR9IP",
                "razorpay_key_id": "rzp_test_...",
                "amount": 71038.2,
                "amount_in_paise": 7103820,
                "currency": "INR",
                "status": "ORDER_CREATED",
                "policy_decision": "APPROVE",
                "policy_reason": "All verification checks passed, payment is authorized, and transaction amount is within budget and policy limits."
            }
        }
    )


class VerifyPaymentRequest(BaseModel):
    transaction_id: int = Field(..., gt=0, description="Internal transaction record ID")
    razorpay_order_id: str = Field(..., description="Razorpay order ID returned during order creation")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID received after payment attempt")
    razorpay_signature: str = Field(..., description="Cryptographic HMAC SHA256 signature from Razorpay")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transaction_id": 1,
                "razorpay_order_id": "order_OPsXzAbc12345",
                "razorpay_payment_id": "pay_OPsYwDef67890",
                "razorpay_signature": "9ef5426da7d673f8a42f5c7de0b35b..."
            }
        }
    )


class PaymentVerificationResponse(BaseModel):
    transaction_id: int = Field(..., description="Internal PostgreSQL transaction record ID")
    status: str = Field(..., description="Final transaction status: 'COMPLETED' or 'FAILED'")
    verified: bool = Field(..., description="True if signature was cryptographically verified")
    razorpay_order_id: str = Field(..., description="Razorpay order ID")
    razorpay_payment_id: Optional[str] = Field(default=None, description="Razorpay payment ID")
    message: str = Field(..., description="Verification summary explanation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transaction_id": 1,
                "status": "COMPLETED",
                "verified": True,
                "razorpay_order_id": "order_OPsXzAbc12345",
                "razorpay_payment_id": "pay_OPsYwDef67890",
                "message": "Payment verified and transaction completed successfully."
            }
        }
    )

