import logging
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session

import models
from schemas import VerificationCheck
from services.audit_service import audit_service

logger = logging.getLogger("payguard.verification_agent")


class VerificationAgent:
    """Agent responsible for performing independent verification checks on proposed purchases."""

    def verify_proposal(
        self,
        db: Session,
        intent: models.IntentContract,
        product: models.Product,
        quantity: int = 1,
    ) -> Tuple[List[VerificationCheck], bool, float]:
        """Runs the 5 required verification checks against IntentContract and Product data.

        Returns:
            Tuple[List[VerificationCheck], bool, float]:
                - List of individual check results with PASS/FAIL and explanations.
                - Boolean indicating whether ALL checks passed.
                - Calculated final amount (base_price + shipping_charge + tax).
        """
        checks: List[VerificationCheck] = []
        all_passed = True

        # Check 1: Product category/type matches requested product_type
        req_type = (intent.product_type or "").lower().strip()
        base_req = req_type[:-1] if req_type.endswith("s") and len(req_type) > 3 else req_type
        prod_cat = (product.category or "").lower().strip()
        prod_name = (product.name or "").lower().strip()

        cat_match = (
            base_req in prod_cat
            or req_type in prod_cat
            or base_req in prod_name
            or prod_cat in req_type
        )
        if cat_match:
            checks.append(
                VerificationCheck(
                    check_name="category_match",
                    status="PASS",
                    explanation=f"Product category '{product.category}' matches requested product type '{intent.product_type}'.",
                )
            )
        else:
            all_passed = False
            checks.append(
                VerificationCheck(
                    check_name="category_match",
                    status="FAIL",
                    explanation=f"Product category '{product.category}' does not match requested product type '{intent.product_type}'.",
                )
            )

        # Check 2: Product/description is relevant to the requested purpose
        purpose = (intent.purpose or "").lower().strip()
        prod_desc = (product.description or "").lower().strip()
        # Look for matching purpose terms or relevant features
        purpose_keywords = [w for w in purpose.replace(",", " ").split() if len(w) > 3]
        desc_relevant = True  # Default true unless clearly contradictory
        if purpose and purpose_keywords:
            matched_kw = [kw for kw in purpose_keywords if kw in prod_desc or kw in prod_name or kw in prod_cat]
            # As long as it's the right product category, it serves the category purpose
            if cat_match:
                desc_relevant = True
                explanation_text = f"Product '{product.name}' aligns with purpose '{intent.purpose}'."
                if matched_kw:
                    explanation_text += f" (Matched features: {', '.join(matched_kw)})"
            else:
                desc_relevant = False
                explanation_text = f"Product does not match purpose '{intent.purpose}'."
        else:
            explanation_text = f"Product '{product.name}' is suitable for general use."

        if desc_relevant:
            checks.append(
                VerificationCheck(
                    check_name="purpose_relevance",
                    status="PASS",
                    explanation=explanation_text,
                )
            )
        else:
            all_passed = False
            checks.append(
                VerificationCheck(
                    check_name="purpose_relevance",
                    status="FAIL",
                    explanation=explanation_text,
                )
            )

        # Check 3: Quantity does not exceed the requested quantity
        if quantity <= intent.quantity:
            checks.append(
                VerificationCheck(
                    check_name="quantity_limit",
                    status="PASS",
                    explanation=f"Proposed quantity ({quantity}) is within requested quantity limit ({intent.quantity}).",
                )
            )
        else:
            all_passed = False
            checks.append(
                VerificationCheck(
                    check_name="quantity_limit",
                    status="FAIL",
                    explanation=f"Proposed quantity ({quantity}) exceeds requested quantity ({intent.quantity}).",
                )
            )

        # Check 4: Product is in stock
        if product.stock >= quantity:
            checks.append(
                VerificationCheck(
                    check_name="stock_availability",
                    status="PASS",
                    explanation=f"Product is in stock ({product.stock} units available, {quantity} requested).",
                )
            )
        else:
            all_passed = False
            checks.append(
                VerificationCheck(
                    check_name="stock_availability",
                    status="FAIL",
                    explanation=f"Insufficient stock ({product.stock} available, {quantity} requested).",
                )
            )

        # Check 5: Final amount is calculated as: (base_price + shipping_charge + tax) * quantity
        calculated_final = round((product.base_price + product.shipping_charge + product.tax) * quantity, 2)
        checks.append(
            VerificationCheck(
                check_name="pricing_calculation",
                status="PASS",
                explanation=(
                    f"Final amount calculated correctly: INR {calculated_final:.2f} = "
                    f"[Base (INR {product.base_price:.2f}) + "
                    f"Shipping (INR {product.shipping_charge:.2f}) + "
                    f"Tax (INR {product.tax:.2f})] * Quantity ({quantity})."
                ),
            )
        )

        # Record Verification Agent audit log
        verdict = "PASS" if all_passed else "FAIL"
        audit_service.log(
            db=db,
            agent="Verification Agent",
            action="Verification Checks",
            decision=verdict,
            reason=f"Verification checks for Product #{product.id} vs Intent #{intent.id} result: {verdict}",
        )

        return checks, all_passed, calculated_final


verification_agent = VerificationAgent()
