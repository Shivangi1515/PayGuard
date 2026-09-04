import logging
import hmac
import hashlib
import os
from unittest.mock import patch, MagicMock
import models
from database import SessionLocal
from agents.payment_agent import (
    payment_agent,
    PolicyBlockedError,
    UserConfirmationRequiredError,
)
from services.payment_service import payment_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("payguard.test_payment")


def run_payment_tests():
    db = SessionLocal()
    try:
        logger.info("=== 1. TESTING PAYMENT AGENT: POLICY 'APPROVE' WORKFLOW ===")
        
        # Audio-Technica: base 17490 + ship 200 + tax 3148.2 = 20838.20 INR (< 50,000 threshold -> APPROVE)
        prod_ath = db.query(models.Product).filter(models.Product.name.ilike("%Audio-Technica%")).first()
        assert prod_ath is not None
        
        intent_ath = models.IntentContract(
            raw_request="Buy me Audio-Technica headphones for music under 30000, quantity 1",
            product_type="Headphones",
            purpose="music",
            max_budget=30000.0,
            quantity=1,
            payment_authorized=True,
        )
        db.add(intent_ath)
        db.commit()
        db.refresh(intent_ath)
        logger.info(f"Created IntentContract #{intent_ath.id} for Audio-Technica (INR 30,000 budget)")

        # Mock Razorpay order creation for unit test if live test credentials are not present
        mock_order_response = {
            "id": "order_Test1234567890",
            "amount": 2083820,
            "currency": "INR",
            "status": "created",
            "receipt": f"rcpt_ic{intent_ath.id}_p{prod_ath.id}",
        }

        with patch.object(payment_service.client.order, "create", return_value=mock_order_response):
            order_resp = payment_agent.initiate_payment(
                db=db,
                intent_contract_id=intent_ath.id,
                product_id=prod_ath.id,
                quantity=1,
                user_confirmed=False,
            )
            logger.info(f"✓ Razorpay Order Created: ID={order_resp.razorpay_order_id}")
            logger.info(f"✓ Public Key: {order_resp.razorpay_key_id}")
            logger.info(f"✓ Validated Final Amount: INR {order_resp.amount:.2f} ({order_resp.amount_in_paise} paise)")
            logger.info(f"✓ Transaction ID: {order_resp.transaction_id}, Status: {order_resp.status}")
            
            assert order_resp.policy_decision == "APPROVE"
            assert order_resp.status == "ORDER_CREATED"
            assert order_resp.razorpay_order_id == "order_Test1234567890"
            assert order_resp.amount == 20838.20

        logger.info("\n=== 2. TESTING SIGNATURE VERIFICATION ===")
        # Test authentic HMAC signature verification
        test_payment_id = "pay_TestPayment123456"
        secret = payment_service.key_secret or "rzp_test_secret_key"
        payment_service.key_secret = secret
        
        valid_sig = hmac.new(
            secret.encode("utf-8"),
            f"{order_resp.razorpay_order_id}|{test_payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        verify_resp_valid = payment_agent.verify_payment(
            db=db,
            transaction_id=order_resp.transaction_id,
            razorpay_order_id=order_resp.razorpay_order_id,
            razorpay_payment_id=test_payment_id,
            razorpay_signature=valid_sig,
        )
        logger.info(f"✓ Valid signature outcome: status={verify_resp_valid.status}, verified={verify_resp_valid.verified}")
        assert verify_resp_valid.status == "COMPLETED"
        assert verify_resp_valid.verified is True

        # Test invalid signature
        fake_sig = "invalid_tampered_signature_99999"
        verify_resp_invalid = payment_agent.verify_payment(
            db=db,
            transaction_id=order_resp.transaction_id,
            razorpay_order_id=order_resp.razorpay_order_id,
            razorpay_payment_id=test_payment_id,
            razorpay_signature=fake_sig,
        )
        logger.info(f"✓ Invalid signature outcome: status={verify_resp_invalid.status}, verified={verify_resp_invalid.verified}")
        assert verify_resp_invalid.status == "FAILED"
        assert verify_resp_invalid.verified is False

        logger.info("\n=== 3. TESTING POLICY 'ASK_USER' WORKFLOW ===")
        # Acer Swift Go 14: Final amount 71038.20 INR (>= 50,000 high-value threshold -> ASK_USER)
        prod_acer = db.query(models.Product).filter(models.Product.name.ilike("%Acer Swift%")).first()
        intent_acer = models.IntentContract(
            raw_request="Buy me a laptop under 80000, quantity 1",
            product_type="Laptop",
            purpose="coding",
            max_budget=80000.0,
            quantity=1,
            payment_authorized=True,
        )
        db.add(intent_acer)
        db.commit()
        db.refresh(intent_acer)

        # 3.1 Without user_confirmed -> should raise UserConfirmationRequiredError
        try:
            payment_agent.initiate_payment(
                db=db,
                intent_contract_id=intent_acer.id,
                product_id=prod_acer.id,
                quantity=1,
                user_confirmed=False,
            )
            assert False, "Should have raised UserConfirmationRequiredError"
        except UserConfirmationRequiredError as e:
            logger.info(f"✓ Correctly paused for user confirmation: {e}")

        # 3.2 With user_confirmed=True -> should successfully create Razorpay order
        mock_high_order = {
            "id": "order_HighVal123456",
            "amount": 7103820,
            "currency": "INR",
            "status": "created",
            "receipt": f"rcpt_ic{intent_acer.id}_p{prod_acer.id}",
        }
        with patch.object(payment_service.client.order, "create", return_value=mock_high_order):
            order_resp_high = payment_agent.initiate_payment(
                db=db,
                intent_contract_id=intent_acer.id,
                product_id=prod_acer.id,
                quantity=1,
                user_confirmed=True,
            )
            logger.info(f"✓ Razorpay Order Created after user confirmation: ID={order_resp_high.razorpay_order_id}")
            assert order_resp_high.status == "ORDER_CREATED"
            assert order_resp_high.policy_decision == "ASK_USER"

        logger.info("\n=== 4. TESTING POLICY 'BLOCK' WORKFLOW ===")
        # Final amount exceeds budget -> BLOCK
        intent_block = models.IntentContract(
            raw_request="Buy me a laptop under 40000",
            product_type="Laptop",
            purpose="coding",
            max_budget=40000.0,  # 40,000 < 71038.20 -> Policy BLOCK!
            quantity=1,
            payment_authorized=True,
        )
        db.add(intent_block)
        db.commit()
        db.refresh(intent_block)

        try:
            payment_agent.initiate_payment(
                db=db,
                intent_contract_id=intent_block.id,
                product_id=prod_acer.id,
                quantity=1,
                user_confirmed=True,
            )
            assert False, "Should have raised PolicyBlockedError"
        except PolicyBlockedError as e:
            logger.info(f"✓ Correctly blocked payment creation: {e}")

        logger.info("\n=== 5. VERIFYING AUDIT LOGS FOR PAYMENT WORKFLOW ===")
        logs = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.agent == "Payment Agent")
            .order_by(models.AuditLog.id.desc())
            .limit(10)
            .all()
        )
        logger.info(f"Found {len(logs)} Payment Agent audit log entries:")
        for log in reversed(logs):
            logger.info(f"  [Payment Agent] Action: '{log.action}' | Decision: '{log.decision}' | Reason: {log.reason[:80]}...")

        logger.info("\nALL PAYMENT AGENT INTEGRATION TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()


if __name__ == "__main__":
    run_payment_tests()
