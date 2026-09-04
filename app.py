import logging
from pathlib import Path
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv

# Ensure .env is explicitly loaded from project root
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import engine, Base, check_db_connection, get_db
import models  # Ensure all SQLAlchemy models are registered
from schemas import (
    HealthResponse,
    PurchaseIntentRequest,
    IntentContractResponse,
    BuyRequest,
    PurchaseProposal,
    VerifyRequest,
    VerificationResponse,
    CreatePaymentRequest,
    PaymentOrderResponse,
    VerifyPaymentRequest,
    PaymentVerificationResponse,
)
from agents.intent_agent import intent_agent, IntentExtractionError
from agents.buyer_agent import (
    buyer_agent,
    BuyerAgentError,
    IntentContractNotFoundError,
    NoMatchingProductError,
)
from agents.verification_agent import verification_agent
from agents.payment_agent import (
    payment_agent,
    PaymentAgentError,
    PolicyBlockedError,
    UserConfirmationRequiredError,
)
from services.policy_engine import policy_engine
from services.audit_service import audit_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("payguard.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Check database connectivity and create tables
    logger.info("Initializing PayGuard Backend...")
    db_ok = check_db_connection()
    if db_ok:
        logger.info("PostgreSQL database connection verified.")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables verified/created successfully.")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
    else:
        logger.warning(
            "Could not connect to PostgreSQL. Please ensure your database server is running and DATABASE_URL in .env is configured correctly."
        )
    yield
    # Shutdown
    logger.info("Shutting down PayGuard Backend...")


app = FastAPI(
    title="PayGuard API",
    description="Backend API for PayGuard Autonomous Agent Payment & Policy System",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint checking PostgreSQL connection."""
    db_connected = check_db_connection()
    if db_connected:
        return {"status": "ok", "database": "connected"}
    return {"status": "error", "database": "disconnected"}


@app.post("/agent/intent", response_model=IntentContractResponse, status_code=status.HTTP_201_CREATED)
def extract_purchase_intent(
    payload: PurchaseIntentRequest,
    db: Session = Depends(get_db),
):
    """Intent Extraction Agent endpoint.

    Receives the real user purchase request, extracts intent via Groq LLM,
    persists the IntentContract to PostgreSQL, and returns the real generated database ID.
    """
    try:
        # 1. Extract real intent from user request using Groq LLM
        extracted = intent_agent.extract_intent(payload.request)

        # 2. Save the real extracted IntentContract in PostgreSQL intent_contracts table
        db_intent = models.IntentContract(
            raw_request=payload.request,
            product_type=extracted.product_type,
            purpose=extracted.purpose,
            max_budget=extracted.max_budget,
            quantity=extracted.quantity,
            payment_authorized=extracted.payment_authorized,
        )
        db.add(db_intent)
        db.commit()
        db.refresh(db_intent)

        # 3. Construct response with the ACTUAL generated PostgreSQL ID
        response = IntentContractResponse(
            intent_contract_id=db_intent.id,
            product_type=extracted.product_type,
            purpose=extracted.purpose,
            max_budget=extracted.max_budget,
            quantity=extracted.quantity,
            preferences=extracted.preferences,
            payment_authorized=extracted.payment_authorized,
        )

        # 4. Record successful audit log
        audit_service.log(
            db=db,
            agent="Intent Agent",
            action="Intent extraction",
            decision="SUCCESS",
            reason=f"Saved IntentContract #{db_intent.id} for '{response.product_type}' with budget INR {response.max_budget:.2f}",
        )

        return response

    except IntentExtractionError as e:
        # Log failure to audit logs
        audit_service.log(
            db=db,
            agent="Intent Agent",
            action="Intent extraction",
            decision="FAILURE",
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process purchase intent: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in /agent/intent: {e}")
        audit_service.log(
            db=db,
            agent="Intent Agent",
            action="Intent extraction",
            decision="FAILURE",
            reason=f"Internal server error: {str(e)}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your purchase intent.",
        )


@app.post("/agent/buy", response_model=PurchaseProposal)
def propose_purchase(
    payload: BuyRequest,
    db: Session = Depends(get_db),
):
    """Buyer Agent endpoint.

    Evaluates candidate products from PostgreSQL based on the IntentContract,
    uses Groq to select the best candidate, and returns a purchase proposal.
    """
    try:
        proposal = buyer_agent.propose_purchase(db, intent_contract_id=payload.intent_contract_id)
        return proposal
    except IntentContractNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except NoMatchingProductError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except BuyerAgentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in /agent/buy: {e}")
        audit_service.log(
            db=db,
            agent="Buyer Agent",
            action="Purchase Proposal",
            decision="FAILURE",
            reason=f"Internal server error: {str(e)}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the purchase proposal.",
        )


@app.post("/agent/verify", response_model=VerificationResponse)
def verify_purchase_proposal(
    payload: VerifyRequest,
    db: Session = Depends(get_db),
):
    """Verification Agent & Deterministic Policy Engine endpoint.

    Independently verifies Buyer Agent proposal against IntentContract and Product data,
    then executes the deterministic Python Policy Engine to return APPROVE, ASK_USER, or BLOCK.
    """
    # 1. Fetch Intent Contract
    intent = db.query(models.IntentContract).filter(models.IntentContract.id == payload.intent_contract_id).first()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IntentContract with ID {payload.intent_contract_id} not found.",
        )

    # 2. Fetch Product
    product = db.query(models.Product).filter(models.Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {payload.product_id} not found.",
        )

    # 3. Run independent Verification Agent checks
    checks, all_passed, final_amount = verification_agent.verify_proposal(
        db=db,
        intent=intent,
        product=product,
        quantity=payload.quantity,
    )

    # 4. Evaluate with deterministic Python Policy Engine
    response = policy_engine.evaluate_policy(
        db=db,
        intent=intent,
        product=product,
        verification_checks=checks,
        all_verification_passed=all_passed,
        final_amount=final_amount,
        quantity=payload.quantity,
    )

    return response


@app.post("/agent/payment/create", response_model=PaymentOrderResponse, status_code=status.HTTP_201_CREATED)
def create_payment_order(
    payload: CreatePaymentRequest,
    db: Session = Depends(get_db),
):
    """Payment Agent endpoint - Razorpay Test Mode Order Creation.

    Enforces deterministic policy rules:
    - APPROVE: Automatically creates a Razorpay test order using validated final amount.
    - ASK_USER: Returns 403 / requires explicit user_confirmed=True.
    - BLOCK: Strictly forbidden from creating payment orders (returns 400).

    Returns Razorpay order ID and public key (never exposes key secret).
    """
    try:
        order_response = payment_agent.initiate_payment(
            db=db,
            intent_contract_id=payload.intent_contract_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            user_confirmed=payload.user_confirmed,
        )
        return order_response

    except PolicyBlockedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except UserConfirmationRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except PaymentAgentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in /agent/payment/create: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the payment order.",
        )


@app.post("/agent/payment/verify", response_model=PaymentVerificationResponse)
def verify_payment_signature(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
):
    """Payment Agent endpoint - Razorpay Cryptographic Signature Verification.

    Verifies the authentic HMAC SHA256 payment signature from Razorpay.
    Updates the transaction status to COMPLETED (if valid) or FAILED (if invalid),
    and records immutable audit logs.
    """
    try:
        verification_response = payment_agent.verify_payment(
            db=db,
            transaction_id=payload.transaction_id,
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
        return verification_response

    except PaymentAgentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in /agent/payment/verify: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying the payment signature.",
        )


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)



