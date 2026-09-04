import logging
import re
from typing import List, Dict, Any, Optional
import models
from schemas import DriftCheck, DriftReport
from services.groq_service import groq_service, GroqService

logger = logging.getLogger("payguard.drift_detector")

KNOWN_BRANDS = [
    "apple", "macbook", "dell", "xps", "lenovo", "thinkpad",
    "asus", "rog", "hp", "spectre", "acer", "swift",
    "samsung", "galaxy", "pixel", "google", "oneplus",
    "sony", "bose", "sennheiser", "audio-technica",
]

KNOWN_SPECS = [
    "oled", "4k", "qhd", "16gb", "32gb", "8gb", "512gb", "1tb",
    "rtx", "touch", "touchscreen", "anc", "noise canceling", "noise-canceling",
    "noise cancelling", "wireless", "5g", "titanium", "s-pen", "convertible",
]


class DriftDetector:
    """Detects deviations (drift) between a proposed purchase and the original IntentContract."""

    def __init__(self, groq: Optional[GroqService] = None):
        self.groq = groq or groq_service

    def detect_drift(
        self,
        intent: models.IntentContract,
        product: models.Product,
        quantity: int,
        final_amount: float,
        proposed_items: Optional[List[str]] = None,
    ) -> DriftReport:
        """Compares a proposed product against the user's IntentContract across 5 drift dimensions:

        1. budget drift: proposed final amount > user max budget
        2. quantity drift: proposed quantity does not match requested quantity
        3. product/category drift: wrong product category or type
        4. preference drift: missing essential requested features/specs or brand
        5. unexpected extra items: unrequested add-ons, abnormal surcharges, or extra items

        Returns:
            DriftReport: contains boolean flag, list of detected drift types, and detailed explanations.
        """
        drift_types: List[str] = []
        reasons: List[str] = []
        checks: List[DriftCheck] = []

        # -------------------------------------------------------------
        # 1. Budget Drift Detection
        # -------------------------------------------------------------
        calculated_total = round((product.base_price + product.shipping_charge + product.tax) * quantity, 2)
        effective_amount = max(final_amount, calculated_total)

        if effective_amount > intent.max_budget:
            drift_types.append("budget drift")
            msg = (
                f"Budget drift detected: Final amount INR {effective_amount:.2f} "
                f"exceeds authorized max budget INR {intent.max_budget:.2f} "
                f"by INR {effective_amount - intent.max_budget:.2f}."
            )
            reasons.append(msg)
            checks.append(DriftCheck(drift_type="budget drift", detected=True, explanation=msg))
        else:
            checks.append(
                DriftCheck(
                    drift_type="budget drift",
                    detected=False,
                    explanation=f"Budget compliant: INR {effective_amount:.2f} <= INR {intent.max_budget:.2f}.",
                )
            )

        # -------------------------------------------------------------
        # 2. Quantity Drift Detection
        # -------------------------------------------------------------
        if quantity != intent.quantity:
            drift_types.append("quantity drift")
            msg = (
                f"Quantity drift detected: Proposed quantity ({quantity}) "
                f"does not match authorized quantity ({intent.quantity})."
            )
            reasons.append(msg)
            checks.append(DriftCheck(drift_type="quantity drift", detected=True, explanation=msg))
        else:
            checks.append(
                DriftCheck(
                    drift_type="quantity drift",
                    detected=False,
                    explanation=f"Quantity compliant: {quantity} unit(s) proposed.",
                )
            )

        # -------------------------------------------------------------
        # 3. Product / Category Drift Detection
        # -------------------------------------------------------------
        req_type = (intent.product_type or "").lower().strip()
        base_req = req_type[:-1] if req_type.endswith("s") and len(req_type) > 3 else req_type
        prod_cat = (product.category or "").lower().strip()
        prod_name = (product.name or "").lower().strip()

        cat_matches = (
            base_req in prod_cat
            or req_type in prod_cat
            or base_req in prod_name
            or prod_cat in req_type
            or (base_req in ("laptop", "notebook", "computer") and prod_cat in ("laptops", "laptop"))
            or (base_req in ("phone", "smartphone", "mobile") and prod_cat in ("smartphones", "smartphones"))
            or (base_req in ("headphone", "earphone", "audio", "headset") and prod_cat in ("headphones", "audio"))
        )

        if not cat_matches:
            drift_types.append("product/category drift")
            msg = (
                f"Product/category drift detected: Product '{product.name}' in category '{product.category}' "
                f"does not match requested product type '{intent.product_type}'."
            )
            reasons.append(msg)
            checks.append(DriftCheck(drift_type="product/category drift", detected=True, explanation=msg))
        else:
            checks.append(
                DriftCheck(
                    drift_type="product/category drift",
                    detected=False,
                    explanation=f"Category compliant: '{product.category}' matches '{intent.product_type}'.",
                )
            )

        # -------------------------------------------------------------
        # 4. Preference Drift Detection
        # -------------------------------------------------------------
        missing_preferences = self._check_preference_drift(intent, product)
        if missing_preferences:
            drift_types.append("preference drift")
            msg = (
                f"Preference drift detected: Product '{product.name}' lacks requested "
                f"specification(s) / preference(s): {', '.join(missing_preferences)}."
            )
            reasons.append(msg)
            checks.append(DriftCheck(drift_type="preference drift", detected=True, explanation=msg))
        else:
            checks.append(
                DriftCheck(
                    drift_type="preference drift",
                    detected=False,
                    explanation="Preference compliant: Product satisfies requested preferences and purpose.",
                )
            )

        # -------------------------------------------------------------
        # 5. Unexpected Extra Items Drift Detection
        # -------------------------------------------------------------
        extra_items_found = self._check_unexpected_extra_items(intent, product, proposed_items)
        if extra_items_found:
            drift_types.append("unexpected extra items")
            msg = f"Unexpected extra items drift detected: {extra_items_found}."
            reasons.append(msg)
            checks.append(DriftCheck(drift_type="unexpected extra items", detected=True, explanation=msg))
        else:
            checks.append(
                DriftCheck(
                    drift_type="unexpected extra items",
                    detected=False,
                    explanation="No unexpected extra items or unrequested surcharge items detected.",
                )
            )

        # Build overall report
        has_drift = len(drift_types) > 0
        summary = (
            f"Drift detected in {len(drift_types)} dimension(s): {', '.join(drift_types)}. "
            + " | ".join(reasons)
            if has_drift
            else "No drift detected. Proposal is fully compliant with IntentContract."
        )

        return DriftReport(
            has_drift=has_drift,
            drift_types=drift_types,
            explanations=reasons,
            summary=summary,
            checks=checks,
        )

    def _check_preference_drift(
        self,
        intent: models.IntentContract,
        product: models.Product,
    ) -> List[str]:
        """Identifies explicit preferences in raw request/purpose missing from product."""
        missing: List[str] = []
        raw_text = f"{intent.raw_request or ''} {intent.purpose or ''}".lower()
        prod_text = f"{product.name or ''} {product.category or ''} {product.description or ''}".lower()

        # Check requested brands
        for brand in KNOWN_BRANDS:
            # Word boundary search for brand in raw request
            if re.search(rf"\b{re.escape(brand)}\b", raw_text):
                if not re.search(rf"\b{re.escape(brand)}\b", prod_text):
                    missing.append(f"Brand '{brand.capitalize()}'")

        # Check requested specifications
        for spec in KNOWN_SPECS:
            if re.search(rf"\b{re.escape(spec)}\b", raw_text):
                # Standardize common variations (e.g. noise canceling vs anc)
                if spec in ("anc", "noise canceling", "noise-canceling", "noise cancelling"):
                    if not any(k in prod_text for k in ("anc", "noise cancel", "noise-cancel", "noise reduction")):
                        missing.append("Active Noise Cancellation (ANC)")
                elif spec in ("touch", "touchscreen"):
                    if not any(k in prod_text for k in ("touch", "touchscreen", "touch 2-in-1")):
                        missing.append("Touchscreen display")
                elif spec in ("oled",):
                    if "oled" not in prod_text:
                        missing.append("OLED display")
                else:
                    if spec not in prod_text:
                        missing.append(f"Specification '{spec.upper()}'")

        # Deduplicate missing list while preserving order
        unique_missing = list(dict.fromkeys(missing))
        return unique_missing

    def _check_unexpected_extra_items(
        self,
        intent: models.IntentContract,
        product: models.Product,
        proposed_items: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Detects unrequested bundled accessories, unexpected add-ons or disproportionate charges."""
        if proposed_items:
            # If additional items were bundled that user didn't ask for
            unrequested = [
                item for item in proposed_items
                if item.lower() not in (intent.raw_request or "").lower()
            ]
            if unrequested:
                return f"Unrequested bundled item(s): {', '.join(unrequested)}"

        # Check for abnormal shipping/tax surcharge (e.g. shipping > base_price)
        if product.shipping_charge > product.base_price and product.base_price > 0:
            return f"Abnormal shipping charge (INR {product.shipping_charge:.2f}) exceeds product base price."

        return None


drift_detector = DriftDetector()
