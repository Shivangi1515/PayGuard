import json
import logging
import re
from typing import Optional, Dict, Any
from pydantic import ValidationError
from schemas import IntentContract
from services.groq_service import groq_service, GroqService

logger = logging.getLogger("payguard.intent_agent")

SYSTEM_PROMPT = """You are the Intent Extraction Agent for PayGuard, an autonomous agent payment and policy verification system.

Your SOLE responsibility is to analyze the user's natural language purchase request and extract structured purchase intent parameters into pure JSON.

CRITICAL POLICY & SAFETY RULES:
1. You are strictly an intent extraction engine.
2. You MUST NOT approve payments, grant financial authorizations, or make policy decisions.
3. 'payment_authorized' should only be true if the user's message explicitly includes words stating they authorize/agree to payment for this request (e.g. "I authorize payment", "charge my card", "authorized"). Default is false.
4. Extract accurate numbers for budget and quantity. If budget is given in thousands/lakhs (e.g. "1.5 lakh"), convert to exact INR numeric value (e.g. 150000.0). If no budget is specified, provide a reasonable upper estimate based on the item class.

You must respond ONLY with a valid JSON object adhering to this schema:
{
  "product_type": "string (e.g., 'Laptop', 'Smartphone', 'Headphones', 'Electronics')",
  "purpose": "string (e.g., 'Software Development', 'Gaming', 'Gym/Workout', 'Office')",
  "max_budget": float (in INR, positive number),
  "quantity": int (minimum 1, default 1),
  "preferences": ["string", "string", ...],
  "payment_authorized": boolean
}
"""


class IntentExtractionError(Exception):
    """Raised when intent extraction fails due to validation, JSON, or API errors."""
    pass


class IntentAgent:
    """Agent responsible for extracting structured purchase intent from natural language requests."""

    def __init__(self, service: Optional[GroqService] = None):
        self.service = service or groq_service

    def _clean_json_string(self, raw_content: str) -> str:
        """Strips markdown code blocks, backticks, and extra whitespace from LLM response."""
        content = raw_content.strip()
        # Remove ```json ... ``` or ``` ... ``` wrappers if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
        return content.strip()

    def extract_intent(self, request_text: str, timeout: float = 20.0) -> IntentContract:
        """Extracts and returns a strictly validated IntentContract from a natural language request.

        Args:
            request_text: User's natural language purchase request.
            timeout: Timeout in seconds for the Groq API call.

        Returns:
            IntentContract: Strictly validated Pydantic model.

        Raises:
            IntentExtractionError: If extraction, parsing, or validation fails.
        """
        if not request_text or not request_text.strip():
            raise IntentExtractionError("Purchase request cannot be empty.")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract the purchase intent from the following user request:\n\n\"{request_text.strip()}\"",
            },
        ]

        # Call Groq LLM
        try:
            raw_response = self.service.chat_completion(
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
        except TimeoutError as e:
            logger.error(f"IntentAgent timeout error: {e}")
            raise IntentExtractionError(f"Intent extraction timed out: {e}") from e
        except (PermissionError, ConnectionError, RuntimeError, ValueError) as e:
            logger.error(f"IntentAgent Groq API error: {e}")
            raise IntentExtractionError(f"Groq API error during intent extraction: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during Groq API call: {e}")
            raise IntentExtractionError(f"Unexpected LLM service error: {e}") from e

        # Parse JSON
        cleaned_json = self._clean_json_string(raw_response)
        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: '{cleaned_json}'. Error: {e}")
            raise IntentExtractionError(
                f"LLM returned invalid JSON for intent extraction: {e}"
            ) from e

        if not isinstance(data, dict):
            logger.error(f"LLM response parsed into non-dict structure: {type(data)}")
            raise IntentExtractionError("LLM response did not format as a JSON object.")

        # Ensure raw_request is stored with the contract
        data["raw_request"] = request_text.strip()

        # Validate with Pydantic
        try:
            contract = IntentContract(**data)
            logger.info(
                f"Successfully extracted IntentContract: product_type='{contract.product_type}', "
                f"max_budget=₹{contract.max_budget:.2f}, quantity={contract.quantity}, "
                f"authorized={contract.payment_authorized}"
            )
            return contract
        except ValidationError as e:
            logger.error(f"IntentContract validation failed for data: {data}. Errors: {e.errors()}")
            missing_or_invalid = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            raise IntentExtractionError(
                f"Extracted intent failed contract validation: {'; '.join(missing_or_invalid)}"
            ) from e


# Global reusable agent instance
intent_agent = IntentAgent()
