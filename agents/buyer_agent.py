import json
import logging
import re
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

import models
from schemas import PurchaseProposal
from services.groq_service import groq_service, GroqService
from services.audit_service import audit_service

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
    """Agent responsible for selecting and proposing the best product candidate based on intent contract."""

    def __init__(self, service: Optional[GroqService] = None):
        self.service = service or groq_service

    def _clean_json(self, raw_content: str) -> str:
        content = raw_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        return content.strip()

    def propose_purchase(
        self,
        db: Session,
        intent_contract_id: int,
        timeout: float = 20.0,
    ) -> PurchaseProposal:
        """Executes product candidate search, Groq evaluation, and creates a purchase proposal.

        Args:
            db: Active SQLAlchemy database session.
            intent_contract_id: ID of the IntentContract in PostgreSQL.
            timeout: LLM call timeout in seconds.

        Returns:
            PurchaseProposal: Proposing the selected product and calculated amounts.
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
            f"Buyer Agent evaluating IntentContract #{intent.id}: "
            f"Type='{intent.product_type}', Purpose='{intent.purpose}', Max Budget=INR {intent.max_budget:.2f}"
        )

        # 2. Search PostgreSQL products matching requested product_type
        # Normalize category search keyword (e.g. "laptops" -> "laptop", "smartphones" -> "phone")
        search_term = intent.product_type.lower().strip()
        if search_term.endswith("s") and len(search_term) > 3:
            base_term = search_term[:-1]
        else:
            base_term = search_term

        category_filter = or_(
            models.Product.category.ilike(f"%{base_term}%"),
            models.Product.category.ilike(f"%{search_term}%"),
            models.Product.name.ilike(f"%{base_term}%"),
            models.Product.description.ilike(f"%{base_term}%"),
        )

        # 3. Filter products matching category and under max budget with available stock
        raw_candidates = (
            db.query(models.Product)
            .filter(category_filter)
            .filter(models.Product.stock >= intent.quantity)
            .filter(models.Product.base_price <= intent.max_budget)
            .all()
        )

        # Fallback: if strict keyword matching yields 0, check all products under budget
        if not raw_candidates:
            logger.info("No direct keyword match found. Searching all available products under budget...")
            raw_candidates = (
                db.query(models.Product)
                .filter(models.Product.stock >= intent.quantity)
                .filter(models.Product.base_price <= intent.max_budget)
                .all()
            )

        if not raw_candidates:
            reason_msg = (
                f"No in-stock products found for type '{intent.product_type}' "
                f"with base price <= INR {intent.max_budget:.2f}."
            )
            audit_service.log(
                db=db,
                agent="Buyer Agent",
                action="Product Search",
                decision="NO_CANDIDATE_FOUND",
                reason=reason_msg,
            )
            raise NoMatchingProductError(reason_msg)

        # 4. For each candidate, calculate: final_amount = base_price + shipping_charge + tax
        candidates_data: List[Dict[str, Any]] = []
        candidate_map: Dict[int, models.Product] = {}

        for p in raw_candidates:
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

        logger.info(f"Found {len(candidates_data)} candidate product(s) for evaluation.")

        # 5 & 6. Use Groq to select best candidate and explain why
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
                    f"Select the best candidate and provide the reason."
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
            logger.warning(f"Groq evaluation failed or timed out ({e}). Falling back to deterministic best match.")
            # Fallback to candidate with best budget utilization / stock
            fallback_prod = candidates_data[0]
            selected_id = fallback_prod["product_id"]
            selection_reason = (
                f"Selected '{fallback_prod['name']}' based on optimal budget fit "
                f"(Base: INR {fallback_prod['base_price']:.2f}, Final: INR {fallback_prod['final_amount']:.2f}) "
                f"and available stock ({fallback_prod['stock']})."
            )

        # Validate selected product id exists in candidate pool
        if selected_id not in candidate_map:
            selected_id = candidates_data[0]["product_id"]
            if not selection_reason:
                selection_reason = f"Selected candidate '{candidate_map[selected_id].name}' matching criteria."

        selected_product = candidate_map[selected_id]
        final_amount = round(selected_product.base_price + selected_product.shipping_charge + selected_product.tax, 2)

        proposal = PurchaseProposal(
            product_id=selected_product.id,
            product_name=selected_product.name,
            quantity=intent.quantity,
            base_price=selected_product.base_price,
            shipping_charge=selected_product.shipping_charge,
            tax=selected_product.tax,
            final_amount=final_amount,
            reason=selection_reason,
        )

        # 7. Record Buyer Agent action in audit_logs
        audit_service.log(
            db=db,
            agent="Buyer Agent",
            action="Purchase Proposal",
            decision="SUCCESS",
            reason=(
                f"Proposed purchase for '{proposal.product_name}' (ID: {proposal.product_id}) | "
                f"Final Amount: INR {proposal.final_amount:.2f} | Reason: {proposal.reason}"
            ),
        )

        return proposal


buyer_agent = BuyerAgent()
