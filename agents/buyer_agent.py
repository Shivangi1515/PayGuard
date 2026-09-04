import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

import models
from schemas import PurchaseProposal, AlternativeAttempt
from services.groq_service import groq_service, GroqService
from services.audit_service import audit_service
from services.drift_detector import drift_detector

logger = logging.getLogger("payguard.buyer_agent")

BUYER_SYSTEM_PROMPT = """You are the autonomous Buyer Agent for PayGuard.

Your task is to analyze a list of candidate products retrieved from PostgreSQL and select the single best product matching the user's purchase intent.

CRITICAL RULES:
1. Compare candidates based on:
   - Match to requested product type
   - Purpose and description relevance (e.g. software development, high performance, portability)
   - Final calculated amount vs user budget
   - Stock availability
2. You must ONLY select from the provided candidate list.
3. You must NOT authorize payments or create financial orders. You are only generating a purchase proposal.
4. Respond ONLY with a valid JSON object matching this schema:
{
  "selected_product_id": <int>,
  "reason": "<clear explanation why this product was selected as the optimal candidate>"
}
"""

MAX_ALTERNATIVE_ATTEMPTS = 3


class BuyerAgentError(Exception):
    """Base exception for Buyer Agent operations."""
    pass


class IntentContractNotFoundError(BuyerAgentError):
    """Raised when the specified intent contract does not exist."""
    pass


class AvailabilityFailureError(BuyerAgentError):
    """Structured exception for product availability and budget constraint failures."""

    def __init__(
        self,
        failure_type: str,  # "NO_PRODUCT_UNDER_BUDGET", "PRODUCT_NOT_AVAILABLE", "PRODUCT_OUT_OF_STOCK", "SPEC_NOT_AVAILABLE"
        message: str,
        product_type: str,
        user_budget: float,
        lowest_available_price: Optional[float] = None,
        lowest_product_name: Optional[str] = None,
        difference: Optional[float] = None,
        products_found_count: int = 0,
        unmet_specs: Optional[List[str]] = None,
        attempts_history: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.failure_type = failure_type
        self.message = message
        self.product_type = product_type
        self.user_budget = user_budget
        self.lowest_available_price = lowest_available_price
        self.lowest_product_name = lowest_product_name
        self.difference = difference
        self.products_found_count = products_found_count
        self.unmet_specs = unmet_specs or []
        self.attempts_history = attempts_history or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.failure_type,
            "message": self.message,
            "product_type": self.product_type,
            "user_budget": self.user_budget,
            "lowest_available_price": self.lowest_available_price,
            "lowest_product_name": self.lowest_product_name,
            "difference": self.difference,
            "products_found_count": self.products_found_count,
            "unmet_specs": self.unmet_specs,
            "attempts_history": self.attempts_history,
        }


class NoMatchingProductError(BuyerAgentError):
    """Legacy compatibility exception."""
    pass


class BuyerAgent:
    """Agent responsible for selecting and proposing compliant product candidates based on intent contract,
    incorporating availability classification, intent drift detection, and up to 3 alternative finder attempts.
    """

    def __init__(self, service: Optional[GroqService] = None):
        self.service = service or groq_service

    def _clean_json(self, raw_content: str) -> str:
        content = raw_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        return content.strip()

    def _find_catalog_products(
        self,
        db: Session,
        intent: models.IntentContract,
    ) -> List[models.Product]:
        """Finds all catalog products matching requested category/product type."""
        raw_type = (intent.product_type or "").lower().strip()
        base_type = raw_type[:-1] if raw_type.endswith("s") and len(raw_type) > 3 else raw_type

        # Query all products matching type keywords
        category_filter = or_(
            models.Product.category.ilike(f"%{base_type}%"),
            models.Product.category.ilike(f"%{raw_type}%"),
            models.Product.name.ilike(f"%{base_type}%"),
            models.Product.name.ilike(f"%{raw_type}%"),
            models.Product.description.ilike(f"%{base_type}%"),
        )
        return db.query(models.Product).filter(category_filter).all()

    def _select_best_candidate(
        self,
        candidates: List[models.Product],
        intent: models.IntentContract,
        timeout: float = 20.0,
    ) -> Tuple[models.Product, str]:
        """Selects the best product candidate using Groq LLM or deterministic fallback ranking."""
        candidates_data: List[Dict[str, Any]] = []
        candidate_map: Dict[int, models.Product] = {}

        for p in candidates:
            calc_final = round((p.base_price + p.shipping_charge + p.tax) * intent.quantity, 2)
            candidate_map[p.id] = p
            candidates_data.append({
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "base_price": p.base_price,
                "shipping_charge": p.shipping_charge,
                "tax": p.tax,
                "final_amount": calc_final,
                "stock": p.stock,
            })

        messages = [
            {"role": "system", "content": BUYER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User Intent Contract Details:\n"
                    f"- Requested Product Type: {intent.product_type}\n"
                    f"- Purpose: {intent.purpose}\n"
                    f"- Max Budget: INR {intent.max_budget:.2f}\n"
                    f"- Quantity: {intent.quantity}\n"
                    f"- Raw Request: \"{intent.raw_request}\"\n\n"
                    f"Available Candidates in PostgreSQL:\n"
                    f"{json.dumps(candidates_data, indent=2)}\n\n"
                    f"Select the best candidate matching budget and intent, and provide the reason."
                ),
            },
        ]

        selected_id = None
        selection_reason = ""

        try:
            raw_response = self.service.chat_completion(
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            cleaned = self._clean_json(raw_response)
            parsed = json.loads(cleaned)
            selected_id = parsed.get("selected_product_id")
            selection_reason = parsed.get("reason", "Selected by Buyer Agent based on specifications and budget.")
        except Exception as e:
            logger.warning(f"Groq evaluation fallback: {e}")
            # Deterministic best match: lowest final amount matching intent
            sorted_candidates = sorted(candidates_data, key=lambda c: c["final_amount"])
            fallback_prod = sorted_candidates[0]
            selected_id = fallback_prod["product_id"]
            selection_reason = (
                f"Selected '{fallback_prod['name']}' based on budget fit "
                f"(Base: INR {fallback_prod['base_price']:.2f}, Final: INR {fallback_prod['final_amount']:.2f}) "
                f"and available stock ({fallback_prod['stock']})."
            )

        if selected_id not in candidate_map:
            selected_id = candidates[0].id
            selection_reason = f"Selected candidate '{candidates[0].name}' matching criteria."

        return candidate_map[selected_id], selection_reason

    def propose_purchase(
        self,
        db: Session,
        intent_contract_id: int,
        timeout: float = 20.0,
    ) -> PurchaseProposal:
        """Executes candidate evaluation with product availability handling, Intent Drift Detection,
        and up to 3 Alternative Finder attempts.
        """
        # 1. Fetch Intent Contract from PostgreSQL
        intent = db.query(models.IntentContract).filter(models.IntentContract.id == intent_contract_id).first()
        if not intent:
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Intent Retrieval",
                decision="FAILURE",
                reason=f"IntentContract ID {intent_contract_id} not found in database.",
            )
            raise IntentContractNotFoundError(f"IntentContract with ID {intent_contract_id} not found.")

        logger.info(
            f"Buyer Agent starting workflow for IntentContract #{intent.id}: "
            f"Type='{intent.product_type}', Purpose='{intent.purpose}', Max Budget=INR {intent.max_budget:.2f}, Qty={intent.quantity}"
        )

        # 2. Check Catalog Availability
        matching_products = self._find_catalog_products(db=db, intent=intent)

        # Case 2: PRODUCT NOT AVAILABLE
        if not matching_products:
            msg = f"We couldn't find any {intent.product_type or 'product'} matching your request in the merchant catalog."
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Catalog Search",
                decision="PRODUCT_NOT_AVAILABLE",
                reason=msg,
            )
            raise AvailabilityFailureError(
                failure_type="PRODUCT_NOT_AVAILABLE",
                message=msg,
                product_type=intent.product_type or "product",
                user_budget=intent.max_budget,
                products_found_count=0,
            )

        # Case 3: PRODUCT OUT OF STOCK
        in_stock_products = [p for p in matching_products if p.stock >= intent.quantity]
        if not in_stock_products:
            out_of_stock_name = matching_products[0].name
            msg = f"{out_of_stock_name} is currently out of stock ({matching_products[0].stock} available, {intent.quantity} requested)."
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Stock Check",
                decision="OUT_OF_STOCK",
                reason=msg,
            )
            raise AvailabilityFailureError(
                failure_type="PRODUCT_OUT_OF_STOCK",
                message=msg,
                product_type=intent.product_type or "product",
                user_budget=intent.max_budget,
                lowest_product_name=out_of_stock_name,
                products_found_count=len(matching_products),
            )

        # Case 1: Check if ALL in-stock products exceed user's authorized budget
        priced_products = []
        for p in in_stock_products:
            final_p = round((p.base_price + p.shipping_charge + p.tax) * intent.quantity, 2)
            priced_products.append((p, final_p))

        priced_products.sort(key=lambda x: x[1])
        lowest_product, lowest_price = priced_products[0]

        if lowest_price > intent.max_budget:
            diff = round(lowest_price - intent.max_budget, 2)
            msg = (
                f"Couldn't find a {intent.product_type or 'product'} within your ₹{intent.max_budget:,.0f} budget.\n"
                f"The lowest available {intent.product_type or 'product'} ({lowest_product.name}) costs ₹{lowest_price:,.2f}, "
                f"which is ₹{diff:,.2f} above your budget."
            )
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Budget Check",
                decision="NO_PRODUCT_UNDER_BUDGET",
                reason=msg,
            )
            raise AvailabilityFailureError(
                failure_type="NO_PRODUCT_UNDER_BUDGET",
                message=msg,
                product_type=intent.product_type or "product",
                user_budget=intent.max_budget,
                lowest_available_price=lowest_price,
                lowest_product_name=lowest_product.name,
                difference=diff,
                products_found_count=len(in_stock_products),
            )

        # 3. Alternative Search Loop (Up to 3 attempts, preserving hard constraints)
        excluded_ids: List[int] = []
        attempts_history: List[AlternativeAttempt] = []
        last_drift_reasons: List[str] = []

        # Available candidates within budget and in stock
        eligible_candidates = [p for p, price in priced_products if price <= intent.max_budget]

        for attempt in range(1, MAX_ALTERNATIVE_ATTEMPTS + 1):
            remaining_candidates = [p for p in eligible_candidates if p.id not in excluded_ids]
            if not remaining_candidates:
                logger.warning(f"No remaining eligible candidates at attempt {attempt}.")
                break

            logger.info(f"Buyer Agent candidate evaluation attempt {attempt}/{MAX_ALTERNATIVE_ATTEMPTS} (Candidates: {len(remaining_candidates)})")

            # Select best candidate from remaining pool
            candidate_product, selection_reason = self._select_best_candidate(
                candidates=remaining_candidates,
                intent=intent,
                timeout=timeout,
            )

            final_amount = round(
                (candidate_product.base_price + candidate_product.shipping_charge + candidate_product.tax) * intent.quantity,
                2,
            )

            # Audit log proposal
            if attempt == 1:
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Original Proposal",
                    decision="PROPOSED",
                    reason=f"Selected candidate '{candidate_product.name}' (ID: {candidate_product.id}) | Amount: INR {final_amount:.2f}",
                )
            else:
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Alternative Selected",
                    decision="ALTERNATIVE_PROPOSED",
                    reason=f"Attempt #{attempt}: Selected alternative '{candidate_product.name}' (ID: {candidate_product.id}) | Amount: INR {final_amount:.2f}",
                )

            # Run Intent Drift Detection
            drift_report = drift_detector.detect_drift(
                intent=intent,
                product=candidate_product,
                quantity=intent.quantity,
                final_amount=final_amount,
            )

            if drift_report.has_drift:
                logger.warning(f"Attempt #{attempt} drift on #{candidate_product.id}: {', '.join(drift_report.drift_types)}")
                last_drift_reasons = drift_report.drift_types

                rejected_reason = f"Candidate #{candidate_product.id} rejected: {' | '.join(drift_report.explanations)}"
                audit_service.log(
                    db=db,
                    agent="Drift Detector",
                    action="Drift Detected",
                    decision="REJECTED",
                    reason=rejected_reason,
                )

                attempts_history.append(
                    AlternativeAttempt(
                        attempt_number=attempt,
                        product_id=candidate_product.id,
                        product_name=candidate_product.name,
                        final_amount=final_amount,
                        drift_detected=True,
                        drift_types=drift_report.drift_types,
                        rejected_reason=rejected_reason,
                    )
                )

                excluded_ids.append(candidate_product.id)
                continue

            # Candidate is compliant
            logger.info(f"Attempt #{attempt} compliant candidate found: '{candidate_product.name}'")
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Final Decision",
                decision="SUCCESS",
                reason=f"Compliant proposal confirmed for '{candidate_product.name}' (ID: {candidate_product.id}).",
            )

            attempts_history.append(
                AlternativeAttempt(
                    attempt_number=attempt,
                    product_id=candidate_product.id,
                    product_name=candidate_product.name,
                    final_amount=final_amount,
                    drift_detected=False,
                    drift_types=[],
                    rejected_reason=None,
                )
            )

            return PurchaseProposal(
                product_id=candidate_product.id,
                product_name=candidate_product.name,
                quantity=intent.quantity,
                base_price=candidate_product.base_price,
                shipping_charge=candidate_product.shipping_charge,
                tax=candidate_product.tax,
                final_amount=final_amount,
                reason=selection_reason,
                drift_detected=False,
                drift_reasons=[],
                attempts_count=attempt,
                alternative_selected=(attempt > 1),
                attempts_history=attempts_history,
            )

        # Case 4: SPECIFICATION NOT AVAILABLE (If candidates existed in budget but none passed specific criteria)
        unmet_msg = f"No available product matches all your requirements: {', '.join(last_drift_reasons) or 'specifications'} could not be satisfied by the current catalog."
        audit_service.log(
            db=db,
            agent="Buyer Agent",
            action="Specification Check",
            decision="SPEC_NOT_AVAILABLE",
            reason=unmet_msg,
        )
        raise AvailabilityFailureError(
            failure_type="SPEC_NOT_AVAILABLE",
            message=unmet_msg,
            product_type=intent.product_type or "product",
            user_budget=intent.max_budget,
            unmet_specs=last_drift_reasons,
            attempts_history=[a.model_dump() for a in attempts_history],
        )


buyer_agent = BuyerAgent()
