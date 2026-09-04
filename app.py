import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from database import engine, Base, check_db_connection
import models  # Ensure all SQLAlchemy models are registered
from schemas import HealthResponse

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


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
