import os
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import groq
from groq import Groq, APIError, APITimeoutError, APIConnectionError, AuthenticationError

load_dotenv()

logger = logging.getLogger("payguard.groq_service")

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqService:
    """Reusable service for interacting with the Groq API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self._model = model or os.getenv("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL
        self._client: Optional[Groq] = None

    @property
    def model(self) -> str:
        return self._model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()

    @property
    def api_key(self) -> str:
        return self._api_key or os.getenv("GROQ_API_KEY", "").strip()

    def get_client(self, timeout: float = 30.0) -> Groq:
        """Initializes and returns a reusable Groq client instance."""
        current_api_key = self.api_key
        if not current_api_key or current_api_key in ("your_key_here", "your_groq_api_key_here"):
            raise ValueError(
                "GROQ_API_KEY is missing or contains placeholder in .env. Please set a valid GROQ_API_KEY."
            )

        if self._client is None or self._client.api_key != current_api_key:
            logger.info("Initializing new Groq client...")
            self._client = Groq(api_key=current_api_key, timeout=timeout)
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        timeout: float = 20.0,
    ) -> str:
        """Executes a chat completion request with error and timeout handling."""
        client = self.get_client(timeout=timeout)
        selected_model = model or self.model

        try:
            logger.info(f"Sending Groq completion request using model: {selected_model}")
            kwargs: Dict[str, Any] = {
                "model": selected_model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content
            if content is None:
                raise ValueError("Groq returned empty message content.")
            return content

        except APITimeoutError as e:
            logger.error(f"Groq API call timed out after {timeout} seconds: {e}")
            raise TimeoutError(f"Groq API request timed out: {e}") from e

        except AuthenticationError as e:
            logger.error(f"Groq API authentication failed: {e}")
            raise PermissionError(f"Invalid Groq API key: {e}") from e

        except APIConnectionError as e:
            logger.error(f"Failed to connect to Groq API: {e}")
            raise ConnectionError(f"Network error connecting to Groq API: {e}") from e

        except APIError as e:
            logger.error(f"Groq API returned an error: {e}")
            raise RuntimeError(f"Groq API error: {e}") from e


# Global reusable instance
groq_service = GroqService()
