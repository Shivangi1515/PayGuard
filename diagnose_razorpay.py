import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is explicitly loaded from project root
PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

import razorpay  # type: ignore


def diagnose():
    print("=" * 60)
    print("PAYGUARD RAZORPAY CONFIGURATION & AUTH DIAGNOSTIC")
    print("=" * 60)

    # 1. Verify .env file location
    print(f"\n1. Project Root: {PROJECT_ROOT}")
    print(f"   .env Path:    {ENV_PATH}")
    print(f"   .env Exists:  {ENV_PATH.exists()}")

    # 2. Check RAZORPAY_KEY_ID
    raw_key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_id = raw_key_id.strip().strip("'\"")
    key_id_exists = bool(key_id)
    key_id_len = len(key_id)
    key_id_prefix_ok = key_id.startswith("rzp_test_")
    key_id_masked = f"{key_id[:10]}..." if key_id_len >= 10 else key_id

    print(f"\n2. RAZORPAY_KEY_ID Check:")
    print(f"   - Loaded:                {key_id_exists}")
    print(f"   - Non-Empty:             {key_id_exists and key_id_len > 0}")
    print(f"   - Length:                {key_id_len} chars")
    print(f"   - Begins with rzp_test_: {key_id_prefix_ok}")
    print(f"   - Safe Preview (10 ch):  {key_id_masked if key_id_exists else 'NOT FOUND'}")

    # 3. Check RAZORPAY_KEY_SECRET
    raw_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    key_secret = raw_key_secret.strip().strip("'\"")
    key_secret_exists = bool(key_secret)
    key_secret_len = len(key_secret)

    print(f"\n3. RAZORPAY_KEY_SECRET Check:")
    print(f"   - Loaded:                {key_secret_exists}")
    print(f"   - Non-Empty:             {key_secret_exists and key_secret_len > 0}")
    print(f"   - Length:                {key_secret_len} chars")
    print(f"   - Secret Exposed:        NO (Kept strictly private)")

    # 4. Client Initialization & Live Test Call
    print(f"\n4. Razorpay Client Initialization:")
    if not key_id_exists or not key_secret_exists:
        print("   [!] ERROR: Missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET in .env.")
        print("   Please add valid Razorpay test keys in .env:")
        print("     RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxx")
        print("     RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx")
        return

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        print("   [OK] Razorpay Client object initialized successfully.")
    except Exception as e:
        print(f"   [!] Razorpay Client initialization failed: {e}")
        return

    print(f"\n5. Razorpay Orders API Test Call (Creating 1 INR Test Order):")
    test_order_data = {
        "amount": 100,  # 1 INR = 100 paise
        "currency": "INR",
        "receipt": "diag_test_order_001",
        "notes": {"diagnostic": "payguard_auth_verification"},
    }

    try:
        order = client.order.create(data=test_order_data)
        order_id = order.get("id")
        print(f"   [OK] AUTHENTICATION SUCCESSFUL!")
        print(f"   [OK] Test Razorpay Order created: {order_id}")
        print(f"   [OK] Amount in Paise: {order.get('amount')} ({order.get('currency')})")
        print(f"   [OK] Status: {order.get('status')}")
    except razorpay.errors.BadRequestError as e:
        print(f"   [!] Razorpay API Authentication Failed: {e}")
        print("   Possible causes:")
        print("     - The Key Secret does not match the Key ID.")
        print("     - The keys are for Live mode instead of Test mode, or vice versa.")
        print("     - The keys have extra spaces or quotes around them in .env.")
    except Exception as e:
        print(f"   [!] Unexpected Razorpay API Error: {type(e).__name__} - {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    diagnose()
