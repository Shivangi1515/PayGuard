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
        Evaluates conditions in strict priority order:

        STEP 1 — HARD BLOCK CONDITIONS (Evaluated in order A to H):
          A. payment_authorized == false
          B. final_amount > intent.max_budget
          C. final_amount > merchant.maximum_transaction_amount
          D. requested quantity is exceeded (quantity > intent.quantity)
          E. product is out of stock (product.stock < quantity)
          F. required verification check fails
          G. intent drift violates a hard user constraint
          H. duplicate purchase protection is triggered

        STEP 2 — ASK_USER CONDITIONS:
          If no hard block condition is met and final_amount >= merchant.high_value_threshold (₹80,000).

        STEP 3 — APPROVE CONDITIONS:
          If all hard block conditions pass and final_amount < merchant.high_value_threshold.

        Returns:
            VerificationResponse: Containing final decision (APPROVE | ASK_USER | BLOCK), reason, and check details.
        """
        # Fetch active Merchant Policy from PostgreSQL
        policy = db.query(models.MerchantPolicy).first()
        max_tx_amount = policy.max_transaction_amount if policy else DEFAULT_MAX_TX
        high_value_threshold = policy.high_value_threshold if policy else DEFAULT_HIGH_VAL
        duplicate_block_enabled = policy.duplicate_purchase_block if policy else DEFAULT_DUP_BLOCK

        logger.info(
            f"Policy Engine evaluating: Final Amount=INR {final_amount:.2f}, "
            f"User Budget=INR {intent.max_budget:.2f}, Autonomous Limit=INR {high_value_threshold:.2f}, "
            f"Max Tx Limit=INR {max_tx_amount:.2f}, Auth={intent.payment_authorized}"
        )

        decision = "APPROVE"
        reason = "All verification checks passed, payment is authorized, and transaction amount is within budget and policy limits."

        # -------------------------------------------------------------
        # STEP 1 — HARD BLOCK CONDITIONS (Strict Priority Evaluation)
        # -------------------------------------------------------------

        # Condition A: payment_authorized == false
        if not intent.payment_authorized:
            decision = "BLOCK"
            reason = "Transaction blocked: payment authorization was not provided by user in the intent contract."

        # Condition B: final_amount > intent.max_budget (HARD USER BUDGET CAP)
        elif final_amount > intent.max_budget:
            decision = "BLOCK"
            reason = f"Transaction blocked: final amount (INR {final_amount:.2f}) exceeds user authorized max budget (INR {intent.max_budget:.2f})."

        # Condition C: final_amount > merchant.maximum_transaction_amount (HARD MERCHANT MAX CAP)
        elif final_amount > max_tx_amount:
            decision = "BLOCK"
            reason = f"Transaction blocked: final amount (INR {final_amount:.2f}) exceeds merchant maximum transaction limit (INR {max_tx_amount:.2f})."

        # Condition D: requested quantity is exceeded
        elif quantity > intent.quantity:
            decision = "BLOCK"
            reason = f"Transaction blocked: proposed quantity ({quantity}) exceeds authorized quantity ({intent.quantity})."

        # Condition E: product is out of stock
        elif product.stock < quantity:
            decision = "BLOCK"
            reason = f"Transaction blocked: product '{product.name}' is out of stock ({product.stock} available, {quantity} requested)."

        # Condition F & G: required verification check fails / intent drift violates hard user constraint
        elif not all_verification_passed:
            failed_checks = [c.check_name for c in verification_checks if c.status == "FAIL"]
            failed_details = [f"{c.check_name}: {c.explanation}" for c in verification_checks if c.status == "FAIL"]
            decision = "BLOCK"
            reason = f"Transaction blocked: verification check(s) failed ({', '.join(failed_checks)}): {'; '.join(failed_details)}"

        # Condition H: duplicate purchase protection is triggered
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
                reason = f"Transaction blocked: duplicate purchase protection triggered for IntentContract #{intent.id} and Product #{product.id} (already completed in Transaction #{existing_tx.id})."

        # -------------------------------------------------------------
        # STEP 2 — ASK_USER (Autonomous Payment Limit / High-Value Guardrail)
        # -------------------------------------------------------------
        if decision != "BLOCK" and final_amount >= high_value_threshold:
            decision = "ASK_USER"
            reason = (
                f"Transaction requires user confirmation: final amount (INR {final_amount:.2f}) "
                f"reaches or exceeds merchant autonomous payment limit (INR {high_value_threshold:.2f})."
            )

        # -------------------------------------------------------------
        # STEP 3 — APPROVE
        # -------------------------------------------------------------
        if decision != "BLOCK" and decision != "ASK_USER":
            decision = "APPROVE"
            reason = (
                "All verification checks passed, payment is authorized, and transaction amount "
                f"(INR {final_amount:.2f}) is within user budget (INR {intent.max_budget:.2f}) "
                f"and autonomous payment limit (INR {high_value_threshold:.2f})."
            )

        # -------------------------------------------------------------
        # Audit Logging
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
