import logging
import models
from database import SessionLocal
from services.drift_detector import drift_detector
from agents.buyer_agent import buyer_agent
from services.audit_service import audit_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("payguard.test")

def run_tests():
    db = SessionLocal()
    try:
        logger.info("--- TEST 1: Unit Testing 5 Drift Dimensions ---")
        
        # Candidate product: Acer Swift Go 14 (Base: 59990, Final: 71038.2, OLED display, 16GB RAM)
        acer_prod = db.query(models.Product).filter(models.Product.name.ilike("%Acer Swift%")).first()
        assert acer_prod is not None, "Acer Swift Go 14 should exist in DB"

        # 1.1 Budget Drift: Budget 50000 < 71038.2
        intent_budget = models.IntentContract(
            raw_request="Buy me a laptop under 50000",
            product_type="Laptop",
            purpose="coding",
            max_budget=50000.0,
            quantity=1,
            payment_authorized=True,
        )
        report = drift_detector.detect_drift(intent_budget, acer_prod, quantity=1, final_amount=71038.2)
        assert report.has_drift and "budget drift" in report.drift_types
        logger.info("✓ Budget drift correctly detected.")

        # 1.2 Quantity Drift: requested 2, proposed 1
        intent_qty = models.IntentContract(
            raw_request="Buy 2 laptops for office",
            product_type="Laptop",
            purpose="office",
            max_budget=200000.0,
            quantity=2,
            payment_authorized=True,
        )
        report = drift_detector.detect_drift(intent_qty, acer_prod, quantity=1, final_amount=71038.2)
        assert report.has_drift and "quantity drift" in report.drift_types
        logger.info("✓ Quantity drift correctly detected.")

        # 1.3 Product/Category Drift: requested Headphones, proposed Laptop
        intent_cat = models.IntentContract(
            raw_request="Buy noise cancelling headphones",
            product_type="Headphones",
            purpose="music",
            max_budget=80000.0,
            quantity=1,
            payment_authorized=True,
        )
        report = drift_detector.detect_drift(intent_cat, acer_prod, quantity=1, final_amount=71038.2)
        assert report.has_drift and "product/category drift" in report.drift_types
        logger.info("✓ Product/category drift correctly detected.")

        # 1.4 Preference Drift: requested Apple MacBook with M3, proposed Acer
        intent_pref = models.IntentContract(
            raw_request="Buy me an Apple MacBook with M3 chip for coding",
            product_type="Laptop",
            purpose="coding",
            max_budget=200000.0,
            quantity=1,
            payment_authorized=True,
        )
        report = drift_detector.detect_drift(intent_pref, acer_prod, quantity=1, final_amount=71038.2)
        assert report.has_drift and "preference drift" in report.drift_types
        logger.info("✓ Preference drift correctly detected.")

        # 1.5 Compliant Case
        intent_ok = models.IntentContract(
            raw_request="Buy me a laptop for coding under 80000",
            product_type="Laptop",
            purpose="coding",
            max_budget=80000.0,
            quantity=1,
            payment_authorized=True,
        )
        report = drift_detector.detect_drift(intent_ok, acer_prod, quantity=1, final_amount=71038.2)
        assert not report.has_drift
        logger.info("✓ Compliant product passed drift detection with 0 drift.")

        logger.info("\n--- TEST 2: End-to-End Buyer Agent Workflow with Alternative Finder ---")
        
        # Create a test IntentContract in DB for an affordable laptop under 80,000
        test_intent = models.IntentContract(
            raw_request="Buy me a productivity laptop under 80000, quantity 1",
            product_type="Laptop",
            purpose="productivity",
            max_budget=80000.0,
            quantity=1,
            payment_authorized=True,
        )
        db.add(test_intent)
        db.commit()
        db.refresh(test_intent)
        logger.info(f"Created Test IntentContract #{test_intent.id}")

        proposal = buyer_agent.propose_purchase(db=db, intent_contract_id=test_intent.id)
        logger.info(f"Buyer Agent Proposal: {proposal.product_name} (ID: {proposal.product_id})")
        logger.info(f"Final Amount: INR {proposal.final_amount:.2f}")
        logger.info(f"Attempts Count: {proposal.attempts_count}")
        logger.info(f"Alternative Selected: {proposal.alternative_selected}")
        assert proposal.drift_detected is False
        assert proposal.final_amount <= test_intent.max_budget

        logger.info("\n--- TEST 3: Verifying Audit Logs ---")
        logs = (
            db.query(models.AuditLog)
            .order_by(models.AuditLog.id.desc())
            .limit(10)
            .all()
        )
        logger.info(f"Retrieved {len(logs)} recent audit log entries:")
        for entry in reversed(logs):
            logger.info(f"  [{entry.agent}] Action: '{entry.action}' | Decision: '{entry.decision}' | Reason: {entry.reason[:80]}...")

        logger.info("\n--- TEST 4: Multi-Attempt Alternative Search Test ---")
        # User wants headphones with ANC under 30000
        # Products in DB:
        # - Audio-Technica ATH-M50xBT2: Base 17490, Shipping 200, Tax 3148.2 -> Total: 20838.2, but does NOT have ANC! (Preference drift)
        # - Sennheiser Momentum 4 Wireless: Base 26990, Shipping 150, Tax 4858.2 -> Total: 32000 > 30000 (Budget drift)
        # - Sony WH-1000XM5: Base 29990, Shipping 0, Tax 5398.2 -> Total: 35388.2 > 30000 (Budget drift)
        # - Bose QuietComfort Ultra: Base 34900 -> > 30000 (Budget drift)
        
        # Test Intent: "Buy headphones for music under 25000"
        # Audio-Technica (Total 20838.20) will be compliant!
        test_intent_alt = models.IntentContract(
            raw_request="Buy headphones for music under 25000, quantity 1",
            product_type="Headphones",
            purpose="music",
            max_budget=25000.0,
            quantity=1,
            payment_authorized=True,
        )
        db.add(test_intent_alt)
        db.commit()
        db.refresh(test_intent_alt)
        
        proposal_alt = buyer_agent.propose_purchase(db=db, intent_contract_id=test_intent_alt.id)
        logger.info(f"Selected: {proposal_alt.product_name} (Final: INR {proposal_alt.final_amount:.2f})")
        logger.info(f"Attempts: {proposal_alt.attempts_count}, Drift Detected: {proposal_alt.drift_detected}")
        assert proposal_alt.product_name == "Audio-Technica ATH-M50xBT2"
        assert proposal_alt.final_amount <= test_intent_alt.max_budget

        logger.info("\n--- TEST 5: Forcing Candidate 1 Drift & Selecting Compliant Alternative ---")
        # Let's create an intent where user specifically asks for "Apple MacBook" or "Dell XPS" under 150000.
        # Apple MacBook Pro 14 costs ~200,482 INR -> Budget drift on Apple MacBook!
        # Alternative Dell XPS 15 is ~171,600 INR -> Budget drift!
        # Or let's test: user wants "touchscreen laptop under 120000"
        # In DB:
        # HP Spectre x360 14 (Touch): Base 115000 + Shipping 0 + Tax 20700 = 135,700 INR (> 120,000 -> Budget drift!)
        # Next candidate: Acer Swift Go 14 (Productivity): Base 59990 + Shipping 250 + Tax 10798.2 = 71,038.20 INR (<= 120,000 -> Compliant alternative!)
        
        test_intent_force_alt = models.IntentContract(
            raw_request="Buy me a laptop for programming under 120000, quantity 1",
            product_type="Laptop",
            purpose="programming",
            max_budget=120000.0,
            quantity=1,
            payment_authorized=True,
        )
        db.add(test_intent_force_alt)
        db.commit()
        db.refresh(test_intent_force_alt)
        
        proposal_force = buyer_agent.propose_purchase(db=db, intent_contract_id=test_intent_force_alt.id)
        logger.info(f"Selected Product: {proposal_force.product_name} (ID: {proposal_force.product_id})")
        logger.info(f"Final Amount: INR {proposal_force.final_amount:.2f}")
        logger.info(f"Attempts Count: {proposal_force.attempts_count}")
        logger.info(f"Attempts History: {proposal_force.attempts_history}")
        assert proposal_force.final_amount <= test_intent_force_alt.max_budget
        assert proposal_force.drift_detected is False

        logger.info("\nALL TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
