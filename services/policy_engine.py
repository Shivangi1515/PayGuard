import logging
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

import models
from schemas import VerificationCheck, VerificationResponse
from services.audit_service import audit_service

logger = logging.getLogger("payguard.policy_engine")

# Fallback default merchant policy in case none is seeded in DB
DEFAULT_MAX_TX = 100000.0
DEFAULT_HIGH_VAL = 80000.0
DEFAULT_DUP_BLOCK = True


class PolicyEngine:
    """Deterministic Python Policy Engine for PayGuard financial authorization."""

    def evaluate_policy(
        self,
        db: Session,
        intent: models.IntentContract,
        product: models.Product,
        verification_checks: List[VerificationCheck],
        all_verification_passed: bool,
        final_amount: float,
        quantity: int,
    ) -> VerificationResponse:
        """Determines whether to APPROVE, ASK_USER, or BLOCK a proposed transaction.

        This engine is 100% deterministic Python logic. LLMs are NOT involved in this decision.

        Args:
            db: Database session.
            intent: User IntentContract.
            product: Candidate Product.
            verification_checks: List of results from VerificationAgent.
            all_verification_passed: Boolean indicating all 5 checks passed.
            final_amount: Calculated total amount in INR.
            quantity: Quantity requested.

        Returns:
            VerificationResponse: Containing final decision, reason, and check details.
        """
        # Fetch active Merchant Policy from PostgreSQL
        policy = db.query(models.MerchantPolicy).first()
        max_tx_amount = policy.max_transaction_amount if policy else DEFAULT_MAX_TX
        high_value_threshold = policy.high_value_threshold if policy else DEFAULT_HIGH_VAL
        duplicate_block_enabled = policy.duplicate_purchase_block if policy else DEFAULT_DUP_BLOCK

        logger.info(
            f"Policy Engine evaluating: Final Amount=INR {final_amount:.2f}, "
            f"User Budget=INR {intent.max_budget:.2f}, High-Value Threshold=INR {high_value_threshold:.2f}, "
            f"Max Tx Limit=INR {max_tx_amount:.2f}, Auth={intent.payment_authorized}"
        )

        decision = "APPROVE"
        reason = "All verification checks passed, payment is authorized, and transaction amount is within budget and policy limits."

        # -------------------------------------------------------------
        # 1. Deterministic BLOCK Rules
        # -------------------------------------------------------------

        # Rule 1.1: Verification failure
        if not all_verification_passed:
            failed_checks = [c.check_name for c in verification_checks if c.status == "FAIL"]
            decision = "BLOCK"
            reason = f"Transaction blocked: verification check(s) failed: {', '.join(failed_checks)}."

        # Rule 1.2: Payment not authorized
        elif not intent.payment_authorized:
            decision = "BLOCK"
            reason = "Transaction blocked: payment authorization was not provided by user in the intent request."

        # Rule 1.3: Quantity exceeds requested
        elif quantity > intent.quantity:
            decision = "BLOCK"
            reason = f"Transaction blocked: proposed quantity ({quantity}) exceeds authorized quantity ({intent.quantity})."

        # Rule 1.4: Out of stock
        elif product.stock < quantity:
            decision = "BLOCK"
            reason = f"Transaction blocked: product '{product.name}' is out of stock ({product.stock} available, {quantity} requested)."

        # Rule 1.5: Final amount exceeds user max budget
        elif final_amount > intent.max_budget:
            decision = "BLOCK"
            reason = f"Transaction blocked: final amount (INR {final_amount:.2f}) exceeds user max budget (INR {intent.max_budget:.2f})."

        # Rule 1.6: Final amount exceeds merchant maximum transaction limit
        elif final_amount > max_tx_amount:
            decision = "BLOCK"
            reason = f"Transaction blocked: final amount (INR {final_amount:.2f}) exceeds merchant maximum transaction limit (INR {max_tx_amount:.2f})."

        # Rule 1.7: Duplicate purchase detection
        elif duplicate_block_enabled:
            existing_tx = (
                db.query(models.Transaction)
                .filter(
                    models.Transaction.intent_contract_id == intent.id,
                    models.Transaction.product_id == product.id,
                    models.Transaction.status.in_(["APPROVED", "COMPLETED"]),
                )
                .first()
            )
            if existing_tx:
                decision = "BLOCK"
                reason = f"Transaction blocked: duplicate purchase detected for IntentContract #{intent.id} and Product #{product.id}."

        # -------------------------------------------------------------
        # 2. Deterministic ASK_USER Rule (High Value Threshold)
        # -------------------------------------------------------------
        if decision != "BLOCK" and final_amount >= high_value_threshold:
            decision = "ASK_USER"
            reason = (
                f"Transaction requires user confirmation: final amount (INR {final_amount:.2f}) "
                f"reaches or exceeds merchant high-value threshold (INR {high_value_threshold:.2f})."
            )

        # -------------------------------------------------------------
        # 3. Audit Logging
        # -------------------------------------------------------------
        audit_service.log(
            db=db,
            agent="Policy Engine",
            action="Policy Decision",
            decision=decision,
            reason=f"Policy decision '{decision}' for Product #{product.id} (INR {final_amount:.2f}): {reason}",
        )

        return VerificationResponse(
            decision=decision,
            reason=reason,
            checks=verification_checks,
        )


policy_engine = PolicyEngine()
