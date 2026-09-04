import logging
from typing import Optional
from sqlalchemy.orm import Session
from models import AuditLog

logger = logging.getLogger("payguard.audit")


class AuditService:
    """Service responsible for recording immutable audit logs to database and logs."""

    @staticmethod
    def log(
        db: Optional[Session],
        agent: str,
        action: str,
        decision: str,
        reason: Optional[str] = None,
        transaction_id: Optional[int] = None,
    ) -> Optional[AuditLog]:
        """Creates and commits an audit log entry in PostgreSQL."""
        log_msg = f"[{agent}] - Action: '{action}' | Result/Decision: '{decision}' | Reason: {reason or 'N/A'}"
        if decision.upper() in ("SUCCESS", "APPROVED"):
            logger.info(log_msg)
        else:
            logger.warning(log_msg)

        if db is not None:
            try:
                entry = AuditLog(
                    transaction_id=transaction_id,
                    agent=agent,
                    action=action,
                    decision=decision,
                    reason=reason,
                )
                db.add(entry)
                db.commit()
                db.refresh(entry)
                return entry
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to persist audit log entry to database: {e}")
                return None
        return None


audit_service = AuditService()
