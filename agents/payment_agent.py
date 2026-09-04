import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

import models
from schemas import (
    PaymentOrderResponse,
    PaymentVerificationResponse,
    VerificationResponse,
)
from services.payment_service import payment_service, PaymentService, PaymentServiceError
from services.policy_engine import policy_engine
from agents.verification_agent import verification_agent
from services.audit_service import audit_service

logger = logging.getLogger("payguard.payment_agent")


class PaymentAgentError(Exception):
    """Base exception for Payment Agent operations."""
    pass


class PolicyBlockedError(PaymentAgentError):
    """Raised when policy engine blocks transaction from payment."""
    pass


class UserConfirmationRequiredError(PaymentAgentError):
    """Raised when policy engine requires explicit user approval."""
    pass


class PaymentAgent:
    """Agent responsible for policy-guarded payment authorization, Razorpay order creation,
    and cryptographic payment verification.
    """

    def __init__(self, payment_svc: Optional[PaymentService] = None):
        self.payment_svc = payment_svc or payment_service

    def initiate_payment(
        self,
        db: Session,
        intent_contract_id: int,
        product_id: int,
        quantity: int = 1,
        user_confirmed: bool = False,
    ) -> PaymentOrderResponse:
        """Evaluates policy and initiates a Razorpay test order ONLY if authorized.

        Rules:
        1. APPROVE -> Automatically creates Razorpay order.
        2. ASK_USER -> Waits for explicit user confirmation (user_confirmed=True).
        3. BLOCK -> Strictly forbidden from creating Razorpay order.
        """
        # 1. Fetch IntentContract
        intent = db.query(models.IntentContract).filter(models.IntentContract.id == intent_contract_id).first()
        if not intent:
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Attempt",
                decision="FAILURE",
                reason=f"IntentContract ID {intent_contract_id} not found.",
            )
            raise PaymentAgentError(f"IntentContract ID {intent_contract_id} not found.")

        # 2. Fetch Product
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Attempt",
                decision="FAILURE",
                reason=f"Product ID {product_id} not found.",
            )
            raise PaymentAgentError(f"Product ID {product_id} not found.")

        # 3. Verification Agent Checks
        checks, all_passed, final_amount = verification_agent.verify_proposal(
            db=db,
            intent=intent,
            product=product,
            quantity=quantity,
        )

        # 4. Deterministic Policy Engine Evaluation
        policy_result = policy_engine.evaluate_policy(
            db=db,
            intent=intent,
            product=product,
            verification_checks=checks,
            all_verification_passed=all_passed,
            final_amount=final_amount,
            quantity=quantity,
        )

        # Log payment attempt
        audit_service.log(
            db=db,
            agent="Payment Agent",
            action="Payment Attempt",
            decision="PENDING",
            reason=(
                f"Payment requested for Product '{product.name}' (#{product.id}) "
                f"under Intent #{intent.id} | Amount: INR {final_amount:.2f} | Policy Decision: {policy_result.decision}"
            ),
        )

        # 5. Enforce Policy Rules
        if policy_result.decision == "BLOCK":
            # Rule 3: BLOCK transactions must never create a Razorpay order
            tx = models.Transaction(
                intent_contract_id=intent.id,
                product_id=product.id,
                quantity=quantity,
                product_price=product.base_price,
                shipping=product.shipping_charge,
                tax=product.tax,
                final_amount=final_amount,
                status="BLOCKED",
            )
            db.add(tx)
            db.commit()
            db.refresh(tx)

            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Order Creation",
                decision="BLOCKED",
                reason=f"Order creation denied by Policy Engine: {policy_result.reason}",
                transaction_id=tx.id,
            )
            raise PolicyBlockedError(f"Payment blocked by policy: {policy_result.reason}")

        if policy_result.decision == "ASK_USER" and not user_confirmed:
            # Rule 2: ASK_USER transactions must wait for explicit user confirmation
            tx = models.Transaction(
                intent_contract_id=intent.id,
                product_id=product.id,
                quantity=quantity,
                product_price=product.base_price,
                shipping=product.shipping_charge,
                tax=product.tax,
                final_amount=final_amount,
                status="WAITING_USER_CONFIRMATION",
            )
            db.add(tx)
            db.commit()
            db.refresh(tx)

            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Order Creation",
                decision="WAITING_USER_CONFIRMATION",
                reason=f"High-value policy rule triggered. Awaiting explicit user confirmation: {policy_result.reason}",
                transaction_id=tx.id,
            )
            raise UserConfirmationRequiredError(
                f"User confirmation required: {policy_result.reason}. Resend with user_confirmed=true to proceed."
            )

        # 6. Policy is APPROVE or ASK_USER with user_confirmed=True -> Create Razorpay order
        receipt_id = f"rcpt_ic{intent.id}_p{product.id}"
        notes = {
            "intent_contract_id": intent.id,
            "product_id": product.id,
            "product_name": product.name,
            "quantity": quantity,
        }

        try:
            rzp_order = self.payment_svc.create_order(
                amount=final_amount,
                currency="INR",
                receipt=receipt_id,
                notes=notes,
            )
        except PaymentServiceError as e:
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Order Creation",
                decision="FAILURE",
                reason=f"Razorpay API error: {str(e)}",
            )
            raise PaymentAgentError(f"Payment order creation failed: {str(e)}")

        # 7. Persist Transaction in Database
        tx = models.Transaction(
            intent_contract_id=intent.id,
            product_id=product.id,
            quantity=quantity,
            product_price=product.base_price,
            shipping=product.shipping_charge,
            tax=product.tax,
            final_amount=final_amount,
            status="ORDER_CREATED",
            razorpay_order_id=rzp_order.get("id"),
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        # 8. Log Order Creation in Audit Logs
        audit_service.log(
            db=db,
            agent="Payment Agent",
            action="Payment Order Creation",
            decision="SUCCESS",
            reason=(
                f"Razorpay test order '{rzp_order.get('id')}' created for Transaction #{tx.id} | "
                f"Amount: INR {final_amount:.2f} | Key: {self.payment_svc.get_public_key()}"
            ),
            transaction_id=tx.id,
        )

        return PaymentOrderResponse(
            transaction_id=tx.id,
            razorpay_order_id=rzp_order.get("id"),
            razorpay_key_id=self.payment_svc.get_public_key(),
            amount=final_amount,
            amount_in_paise=rzp_order.get("amount", int(round(final_amount * 100))),
            currency=rzp_order.get("currency", "INR"),
            status=tx.status,
            policy_decision=policy_result.decision,
            policy_reason=policy_result.reason,
        )

    def verify_payment(
        self,
        db: Session,
        transaction_id: int,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> PaymentVerificationResponse:
        """Verifies the cryptographic payment signature received from Razorpay."""
        # 1. Fetch Transaction
        tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
        if not tx:
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Verification",
                decision="FAILURE",
                reason=f"Transaction ID {transaction_id} not found.",
            )
            raise PaymentAgentError(f"Transaction ID {transaction_id} not found.")

        # Log verification check
        audit_service.log(
            db=db,
            agent="Payment Agent",
            action="Payment Verification",
            decision="PENDING",
            reason=f"Verifying signature for Transaction #{tx.id} (Order: {razorpay_order_id}, Payment: {razorpay_payment_id})",
            transaction_id=tx.id,
        )

        # 2. Verify Cryptographic Signature
        is_valid = self.payment_svc.verify_payment_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

        if is_valid:
            # Payment Success
            tx.razorpay_payment_id = razorpay_payment_id
            tx.status = "COMPLETED"
            db.commit()
            db.refresh(tx)

            # Audit log payment success
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Success",
                decision="COMPLETED",
                reason=(
                    f"Payment verified successfully for Transaction #{tx.id} | "
                    f"Order: {razorpay_order_id} | Payment ID: {razorpay_payment_id} | "
                    f"Amount: INR {tx.final_amount:.2f}"
                ),
                transaction_id=tx.id,
            )

            return PaymentVerificationResponse(
                transaction_id=tx.id,
                status="COMPLETED",
                verified=True,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                message="Payment verified and transaction completed successfully.",
            )
        else:
            # Payment Failure
            tx.status = "FAILED"
            db.commit()
            db.refresh(tx)

            # Audit log payment failure
            audit_service.log(
                db=db,
                agent="Payment Agent",
                action="Payment Failure",
                decision="FAILED",
                reason=(
                    f"Invalid cryptographic signature for Transaction #{tx.id} | "
                    f"Order: {razorpay_order_id} | Payment ID: {razorpay_payment_id}"
                ),
                transaction_id=tx.id,
            )

            return PaymentVerificationResponse(
                transaction_id=tx.id,
                status="FAILED",
                verified=False,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                message="Signature verification failed. Payment was not authentic.",
            )


payment_agent = PaymentAgent()
