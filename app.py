import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import engine, Base, check_db_connection, get_db
import models  # Ensure all SQLAlchemy models are registered
from schemas import HealthResponse, IntentContract, PurchaseIntentRequest
from agents.intent_agent import intent_agent, IntentExtractionError
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


@app.post("/agent/intent", response_model=IntentContract, status_code=status.HTTP_201_CREATED)
def extract_purchase_intent(
    payload: PurchaseIntentRequest,
    db: Session = Depends(get_db),
):
    """Intent Extraction Agent endpoint.

    Extracts structured purchase intent from natural language requests,
    persists the IntentContract to PostgreSQL, and records audit logs.
    """
    try:
        # 1. Extract intent using Groq LLM through IntentAgent
        contract = intent_agent.extract_intent(payload.request)

        # 2. Save the extracted IntentContract in PostgreSQL intent_contracts table
        db_intent = models.IntentContract(
            raw_request=payload.request,
            product_type=contract.product_type,
            purpose=contract.purpose,
            max_budget=contract.max_budget,
            quantity=contract.quantity,
            payment_authorized=contract.payment_authorized,
        )
        db.add(db_intent)
        db.commit()
        db.refresh(db_intent)

        # 3. Record successful audit log
        audit_service.log(
            db=db,
            agent="Intent Agent",
            action="Intent extraction",
            decision="SUCCESS",
            reason=f"Saved IntentContract #{db_intent.id} for '{contract.product_type}' with budget INR {contract.max_budget:.2f}",
        )

        return contract

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


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
