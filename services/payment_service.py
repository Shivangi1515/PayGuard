import os
import hmac
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import razorpay  # type: ignore
from dotenv import load_dotenv

# Ensure .env is explicitly loaded from the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

logger = logging.getLogger("payguard.payment_service")


class PaymentServiceError(Exception):
    """Base exception for payment service operations."""
    pass


class PaymentService:
    """Service handling integration with Razorpay Test Mode."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
    ):
        self._explicit_key_id = key_id
        self._explicit_key_secret = key_secret
        self._client: Optional[razorpay.Client] = None

    @property
    def key_id(self) -> str:
        """Returns the trimmed Razorpay Key ID."""
        if self._explicit_key_id:
            return self._explicit_key_id.strip().strip("'\"")
        val = os.getenv("RAZORPAY_KEY_ID", "")
        return val.strip().strip("'\"")

    @key_id.setter
    def key_id(self, value: str):
        self._explicit_key_id = value
        self._client = None

    @property
    def key_secret(self) -> str:
        """Returns the trimmed Razorpay Key Secret."""
        if self._explicit_key_secret:
            return self._explicit_key_secret.strip().strip("'\"")
        val = os.getenv("RAZORPAY_KEY_SECRET", "")
        return val.strip().strip("'\"")

    @key_secret.setter
    def key_secret(self, value: str):
        self._explicit_key_secret = value
        self._client = None

    def get_client(self, force_new: bool = False) -> razorpay.Client:
        """Instantiates or returns the Razorpay client, refreshing on demand."""
        current_auth = (self.key_id, self.key_secret)
        if force_new or self._client is None or getattr(self._client, "auth", None) != current_auth:
            if not self.key_id or not self.key_secret:
                logger.warning("RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET not configured in .env.")
            client = razorpay.Client(auth=current_auth)
            # Configure requests session with retries for transient socket resets
            try:
                from urllib3.util.retry import Retry
                from requests.adapters import HTTPAdapter
                adapter = HTTPAdapter(
                    max_retries=Retry(
                        total=3,
                        backoff_factor=0.3,
                        status_forcelist=[500, 502, 503, 504],
                    )
                )
                client.session.mount("https://", adapter)
                client.session.mount("http://", adapter)
            except Exception as opt_err:
                logger.debug(f"Session adapter configuration skipped: {opt_err}")
            self._client = client
        return self._client

    @property
    def client(self) -> razorpay.Client:
        """Lazily initializes and returns the Razorpay client using current credentials."""
        return self.get_client()

    def get_public_key(self) -> str:
        """Returns the public Razorpay Key ID safe for client-side consumption."""
        return self.key_id

    def create_order(
        self,
        amount: float,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Creates a Razorpay order in Test Mode using the validated final amount.

        Args:
            amount: Final amount in INR (will be converted to paise).
            currency: 3-letter currency code (default 'INR').
            receipt: Internal transaction/order reference.
            notes: Metadata dictionary.
            max_retries: Maximum attempts on transient socket/connection resets.

        Returns:
            Dict containing order details returned by Razorpay API.
        """
        # Razorpay expects amount in smallest currency unit (paise for INR)
        amount_in_paise = int(round(amount * 100))
        if amount_in_paise <= 0:
            raise PaymentServiceError(f"Invalid transaction amount: {amount}")

        order_data = {
            "amount": amount_in_paise,
            "currency": currency.upper(),
            "payment_capture": 1,  # Auto capture payment upon authorization
        }
        if receipt:
            order_data["receipt"] = str(receipt)[:40]
        if notes:
            order_data["notes"] = {str(k): str(v)[:50] for k, v in notes.items()}

        last_err: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                safe_key_preview = f"{self.key_id[:10]}..." if len(self.key_id) >= 10 else self.key_id
                logger.info(
                    f"Creating Razorpay Test order (attempt {attempt}/{max_retries}): "
                    f"amount=INR {amount:.2f} ({amount_in_paise} paise), key_id={safe_key_preview}, receipt={receipt}"
                )
                # Force fresh client if retrying after connection reset
                client = self.get_client(force_new=(attempt > 1))
                order = client.order.create(data=order_data)
                logger.info(f"Razorpay order created successfully: ID={order.get('id')}")
                return order
            except Exception as e:
                last_err = e
                err_str = str(e)
                is_transient = any(keyword in err_str.lower() for keyword in [
                    "connection reset", "connection aborted", "forcibly closed", "10054", "timeout", "timed out"
                ])
                if is_transient and attempt < max_retries:
                    logger.warning(
                        f"Transient connection error on attempt {attempt}: {e}. Retrying with fresh session..."
                    )
                    import time
                    time.sleep(0.5 * attempt)
                    continue
                else:
                    logger.error(f"Failed to create Razorpay order on attempt {attempt}: {e}")
                    break

        raise PaymentServiceError(f"Razorpay order creation failed: {str(last_err)}")

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verifies the authenticity of a Razorpay payment signature using HMAC SHA256.

        Args:
            razorpay_order_id: Order ID generated by Razorpay.
            razorpay_payment_id: Payment ID received upon transaction completion.
            razorpay_signature: Cryptographic signature provided by Razorpay.

        Returns:
            bool: True if signature is valid, False otherwise.
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            logger.warning("Missing required parameters for signature verification.")
            return False

        secret = self.key_secret
        if not secret:
            logger.error("Cannot verify signature: RAZORPAY_KEY_SECRET is missing.")
            return False

        try:
            # SDK utility verification
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
            self.client.utility.verify_payment_signature(params_dict)
            logger.info(f"Signature verified successfully for Order={razorpay_order_id}, Payment={razorpay_payment_id}")
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Signature verification failed for Order={razorpay_order_id}, Payment={razorpay_payment_id}")
            return False
        except Exception as e:
            logger.warning(f"SDK verification fallback to direct HMAC ({e})")
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
            generated_signature = hmac.new(
                secret.encode("utf-8"),
                msg,
                hashlib.sha256,
            ).hexdigest()
            is_valid = hmac.compare_digest(generated_signature, razorpay_signature)
            logger.info(f"Direct HMAC comparison result: {is_valid}")
            return is_valid


payment_service = PaymentService()
