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


class NoMatchingProductError(BuyerAgentError):
    """Raised when no products match the intent criteria or budget."""
    pass


class BuyerAgent:
    """Agent responsible for selecting and proposing compliant product candidates based on intent contract,
    incorporating automatic Intent Drift Detection and up to 3 Alternative Finder attempts.
    """

    def __init__(self, service: Optional[GroqService] = None):
        self.service = service or groq_service

    def _clean_json(self, raw_content: str) -> str:
        content = raw_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        return content.strip()

    def _get_candidate_products(
        self,
        db: Session,
        intent: models.IntentContract,
        excluded_ids: List[int],
    ) -> List[models.Product]:
        """Queries candidate products from PostgreSQL, filtering out previously rejected candidates."""
        search_term = (intent.product_type or "").lower().strip()
        base_term = search_term[:-1] if search_term.endswith("s") and len(search_term) > 3 else search_term

        category_filter = or_(
            models.Product.category.ilike(f"%{base_term}%"),
            models.Product.category.ilike(f"%{search_term}%"),
            models.Product.name.ilike(f"%{base_term}%"),
            models.Product.description.ilike(f"%{base_term}%"),
        )

        query = (
            db.query(models.Product)
            .filter(category_filter)
            .filter(models.Product.stock >= intent.quantity)
        )
        if excluded_ids:
            query = query.filter(~models.Product.id.in_(excluded_ids))

        candidates = query.all()

        # Fallback search if strict category query returns empty
        if not candidates:
            query_all = (
                db.query(models.Product)
                .filter(models.Product.stock >= intent.quantity)
            )
            if excluded_ids:
                query_all = query_all.filter(~models.Product.id.in_(excluded_ids))
            candidates = query_all.all()

        return candidates

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
            calc_final = round(p.base_price + p.shipping_charge + p.tax, 2)
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
        """Executes candidate evaluation with Intent Drift Detection and up to 3 Alternative Finder attempts.

        Workflow:
        1. Fetch IntentContract from PostgreSQL.
        2. Propose candidate and run Intent Drift Detection.
        3. If drift is detected:
           - Explain exactly what drifted
           - Log: original proposal, drift detected, rejected reason
           - Send Buyer Agent back to search for compliant alternative (max 3 attempts)
        4. When compliant alternative is found:
           - Log: alternative selected, final decision
           - Return compliant PurchaseProposal
        """
        # 1. Read Intent Contract from PostgreSQL
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
            f"Type='{intent.product_type}', Purpose='{intent.purpose}', Max Budget=INR {intent.max_budget:.2f}"
        )

        excluded_ids: List[int] = []
        attempts_history: List[AlternativeAttempt] = []
        original_proposal_info: Optional[Dict[str, Any]] = None

        for attempt in range(1, MAX_ALTERNATIVE_ATTEMPTS + 1):
            logger.info(f"Buyer Agent search attempt {attempt}/{MAX_ALTERNATIVE_ATTEMPTS} (Excluded: {excluded_ids})")

            # Search available candidates in PostgreSQL
            candidates = self._get_candidate_products(db=db, intent=intent, excluded_ids=excluded_ids)
            if not candidates:
                logger.warning(f"No candidates remaining in PostgreSQL at attempt {attempt}.")
                break

            # Select best candidate from remaining pool
            candidate_product, selection_reason = self._select_best_candidate(
                candidates=candidates,
                intent=intent,
                timeout=timeout,
            )

            final_amount = round(
                (candidate_product.base_price + candidate_product.shipping_charge + candidate_product.tax) * intent.quantity,
                2,
            )

            # Record Proposal Logging (original vs alternative)
            if attempt == 1:
                original_proposal_info = {
                    "product_id": candidate_product.id,
                    "product_name": candidate_product.name,
                    "final_amount": final_amount,
                    "reason": selection_reason,
                }
                # Log: original proposal
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Original Proposal",
                    decision="PROPOSED",
                    reason=(
                        f"Original Proposal: '{candidate_product.name}' (ID: {candidate_product.id}) | "
                        f"Final Amount: INR {final_amount:.2f} | Reason: {selection_reason}"
                    ),
                )
            else:
                # Log: alternative selected
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Alternative Selected",
                    decision="ALTERNATIVE_PROPOSED",
                    reason=(
                        f"Alternative Attempt #{attempt}: Selected alternative '{candidate_product.name}' (ID: {candidate_product.id}) | "
                        f"Final Amount: INR {final_amount:.2f} | Reason: {selection_reason}"
                    ),
                )

            # Run Intent Drift Detection
            drift_report = drift_detector.detect_drift(
                intent=intent,
                product=candidate_product,
                quantity=intent.quantity,
                final_amount=final_amount,
            )

            if drift_report.has_drift:
                # Drift detected: do NOT create payment, log drift & rejection reason
                logger.warning(
                    f"Attempt #{attempt} - Drift detected on Product #{candidate_product.id} ('{candidate_product.name}'): "
                    f"{', '.join(drift_report.drift_types)}"
                )

                # Log: drift detected
                audit_service.log(
                    db=db,
                    agent="Drift Detector",
                    action="Drift Detected",
                    decision="DRIFT_DETECTED",
                    reason=(
                        f"Attempt #{attempt} Product '{candidate_product.name}' (ID: {candidate_product.id}) "
                        f"exhibited drift: {', '.join(drift_report.drift_types)} | Details: {drift_report.summary}"
                    ),
                )

                # Log: rejected reason
                rejected_reason = (
                    f"Candidate #{candidate_product.id} ('{candidate_product.name}') rejected due to drift: "
                    f"{' | '.join(drift_report.explanations)}"
                )
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Rejected Reason",
                    decision="REJECTED",
                    reason=rejected_reason,
                )

                # Record attempt history
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

                # Exclude product and trigger alternative search loop
                excluded_ids.append(candidate_product.id)
                continue

            else:
                # Candidate is fully compliant!
                logger.info(
                    f"Attempt #{attempt} - Compliant product found: '{candidate_product.name}' (ID: {candidate_product.id})"
                )

                # Log: final decision
                audit_service.log(
                    db=db,
                    agent="Buyer Agent",
                    action="Final Decision",
                    decision="SUCCESS",
                    reason=(
                        f"Compliant purchase proposal approved for '{candidate_product.name}' (ID: {candidate_product.id}) "
                        f"after {attempt} attempt(s). Final Amount: INR {final_amount:.2f}."
                    ),
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

        # If loop finishes without finding a compliant candidate
        final_rejected_msg = (
            f"Maximum alternative attempts ({MAX_ALTERNATIVE_ATTEMPTS}) reached for IntentContract #{intent.id}. "
            f"All {len(attempts_history)} evaluated candidate(s) failed intent drift verification."
        )
        audit_service.log(
            db=db,
            agent="Buyer Agent",
            action="Final Decision",
            decision="BLOCKED",
            reason=final_rejected_msg,
        )

        raise NoMatchingProductError(final_rejected_msg)


buyer_agent = BuyerAgent()
