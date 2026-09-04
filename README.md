# PayGuard 🛡️

### The AI Buyer That Acts Within Your Intent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Groq](https://img.shields.io/badge/Groq-openai%2Fgpt--oss--20b-F55036?style=flat-square)](https://groq.com)
[![Razorpay](https://img.shields.io/badge/Razorpay-Test_Mode-0C2340?style=flat-square&logo=razorpay&logoColor=white)](https://razorpay.com)

---

## 📌 Overview

AI agents are moving from recommending products to taking autonomous actions on behalf of users. In commerce, an unconstrained AI mistake or hallucination can directly turn into an unauthorized financial transaction.

PayGuard is an **agentic-commerce prototype platform** that allows specialized AI agents to perform purchasing tasks while deterministic authorization controls prevent the AI from exceeding the user's intent or merchant-defined autonomy limits.

> **"The AI can act. Your intent sets the boundary."**  
> **"The AI proposes. The Policy Engine decides. Razorpay executes."**

AI agents handle semantic reasoning and catalog discovery. Deterministic backend services enforce financial authorization and execute protected payment operations.

---

## 🏛️ System Architecture

PayGuard operates on a strict **Separation of Concerns & Separation of Powers** principle: Large Language Models (LLMs) are used only for intent extraction and candidate discovery. LLMs have **zero authority** to grant financial clearance, override spending caps, or execute payment operations.

```mermaid
flowchart TD
    User([User Natural Language Prompt]) -->|POST /agent/intent| IA[Intent Agent - AI Agent]
    
    subgraph S1["1. Intent Locking"]
        IA -->|Extract Parameters via Groq LLM| IC[(PostgreSQL: IntentContract)]
    end
    
    IC -->|POST /agent/buy| BA[Buyer Agent - AI Agent]
    
    subgraph S2["2. Catalog Discovery & Drift Intercept"]
        BA <-->|Query Inventory & Specs| DB[(PostgreSQL: Products Catalog)]
        BA --> DD{Drift Detector}
        DD -->|Intent Drift Detected| ALT[Alternative Finder: Up to 3 Attempts]
        ALT --> BA
        DD -->|Compliant Proposal| PP[Purchase Proposal]
    end
    
    PP -->|POST /agent/verify| VA[Verification Agent - Deterministic Service]
    
    subgraph S3["3. Independent 5-Factor Verification"]
        VA --> C1[1. Category Match Check]
        VA --> C2[2. Purpose Relevance Check]
        VA --> C3[3. Quantity Limit Check]
        VA --> C4[4. Stock Availability Check]
        VA --> C5[5. Pricing Formula Validation]
    end
    
    S3 --> PE[Policy Engine - Deterministic Policy Service]
    
    subgraph S4["4. Deterministic Policy Enforcement"]
        PE --> DEC{Policy Decision}
        DEC -->|APPROVE| PA[Payment Agent - Execution Service]
        DEC -->|ASK_USER| CONF[Pause Agent & Await User Confirmation]
        CONF -->|User Confirmed| PA
        DEC -->|BLOCK| BLK[Halt & Deny Order Creation]
    end
    
    subgraph S5["5. Payment Execution & Verification"]
        PA -->|POST /agent/payment/create| RZP_API[Razorpay Test Orders API]
        RZP_API --> RZP_UI[Razorpay Test Mode Checkout Modal]
        RZP_UI -->|Payment Completed| RZP_VERIF[POST /agent/payment/verify]
        RZP_VERIF -->|HMAC SHA256 Signature Verification| VERIF_RES{Valid Signature?}
        VERIF_RES -->|Yes| SUCCESS[(PostgreSQL: Transaction COMPLETED)]
        VERIF_RES -->|No| FAIL[(PostgreSQL: Transaction FAILED)]
    end
    
    S1 -.-> AL[(PostgreSQL: Immutable AuditLog)]
    S2 -.-> AL
    S3 -.-> AL
    S4 -.-> AL
    S5 -.-> AL
```

---

## 🤖 Pipeline Components & Terminology

PayGuard cleanly separates AI-driven agents from deterministic backend services:

| Component | Classification | Core Responsibility | Underlying Technology | Determinism |
| :--- | :--- | :--- | :--- | :--- |
| **1. Intent Agent** | **AI Agent** | Parses natural-language requests into structured parameters (`product_type`, `purpose`, `max_budget`, `quantity`, `preferences`, `payment_authorized`) and locks an immutable `IntentContract` in PostgreSQL. | Groq LLM (`openai/gpt-oss-20b`) + Pydantic v2 | Semantic + Schema-enforced |
| **2. Buyer Agent** | **AI Agent** | Discovers merchant inventory candidates in PostgreSQL, calculates base + shipping + tax formulas, classifies catalog availability, and runs up to 3 alternative candidate evaluations. | PostgreSQL + Groq LLM (`openai/gpt-oss-20b`) + Python | Hybrid Discovery |
| **3. Verification Agent** | **Deterministic Service** | Independently audits candidate products against the `IntentContract` across 5 isolated checks without LLM involvement. | Pure Python + PostgreSQL | **100% Deterministic** |
| **4. Policy Engine** | **Deterministic Policy Service** *(Not an AI agent)* | Evaluates deterministic financial and merchant guardrails (budget caps, high-value thresholds, duplicate blocks). Returns `APPROVE`, `ASK_USER`, or `BLOCK`. | Pure Python + PostgreSQL | **100% Deterministic** |
| **5. Payment Agent** | **Payment Execution Service** | Re-verifies all parameters on the backend, generates server-side Razorpay test orders, initiates checkout, and cryptographically verifies signatures. | Razorpay Python SDK + HMAC SHA256 | **100% Cryptographic** |

---

## 🛡️ Policy & Verification Guardrails

### The 5-Factor Verification Matrix

Before any proposed purchase reaches the Policy Engine, the **Verification Agent** independently audits the candidate against the authoritative database record:

1. **`category_match`**: Verifies candidate category matches requested product type.
2. **`purpose_relevance`**: Confirms product specifications satisfy user purpose (e.g., coding, noise cancellation).
3. **`quantity_limit`**: Enforces $\text{Proposed Quantity} \le \text{Authorized Quantity}$.
4. **`stock_availability`**: Asserts $\text{Available Stock} \ge \text{Requested Quantity}$.
5. **`pricing_calculation`**: Validates deterministic pricing formula:  
   $$\text{Final Amount} = (\text{Base Price} + \text{Shipping Charge} + \text{Tax}) \times \text{Quantity}$$

### Deterministic Policy Rules

> **"LLMs propose. Deterministic backend policy decides. Razorpay executes only after authorization."**

* **User Budget Constraint**: User budget is a strict hard limit. Transactions exceeding this limit are blocked.
* **Merchant High-Value Threshold (`₹80,000`)**: Controls autonomy. Transactions at or above this threshold require explicit user confirmation.
* **Merchant Max Transaction Cap (`₹1,00,000`)**: Strict hard limit. Transactions exceeding this cap cannot be created.

| Decision | Trigger Conditions | Execution Behavior |
| :--- | :--- | :--- |
| **`APPROVE`** | All 5 checks PASS, payment authorized, and $\text{Final Amount} < \text{High-Value Threshold}$ (`₹80,000`). | **Auto-Approved**: Automatically continues to payment order creation and launches Razorpay Test Mode checkout without requiring secondary manual approval. |
| **`ASK_USER`** | All 5 checks PASS, but $\text{Final Amount} \ge \text{High-Value Threshold}$ (`₹80,000`). | **Paused Execution**: Pauses the agent, explains high-value threshold trigger, and requires explicit user approval before payment order creation. |
| **`BLOCK`** | Any verification failure, intentional drift, unauthorized payment flag, amount exceeding user budget, or amount exceeding merchant cap (`₹1,00,000`). | **Safety Intercept**: Payment order creation is strictly denied (returns HTTP 400). Renders reason and enables alternative search. |

---

## 📦 Product Availability & Budget Handling

PayGuard classifies and handles catalog availability failures with structured user feedback:

1. **`NO_PRODUCT_UNDER_BUDGET`**:
   - Triggered when products exist in the category, but all exceed the authorized budget.
   - Calculates the lowest available option, final amount, and exact difference.
   - *Strict Rule*: PayGuard **never** automatically increases or relaxes the user's budget.
   - UI offers: `"Increase Budget to ₹XX,XXX"` or `"Cancel"`.
2. **`PRODUCT_NOT_AVAILABLE`**:
   - Triggered when the requested category does not exist in the merchant catalog.
   - Prevents LLM hallucinations; displays verified categories (`Laptops`, `Smartphones`, `Headphones`).
3. **`PRODUCT_OUT_OF_STOCK`**:
   - Triggered when all catalog matches have $\text{Stock} < \text{Quantity}$.
   - Automatically searches for compliant in-stock alternatives.
4. **`SPEC_NOT_AVAILABLE`**:
   - Triggered when candidate products fail hard specification constraints.
   - Strictly preserves constraints without silent relaxation.

---

## 💳 Razorpay Test API & Indian Payment Simulation

PayGuard integrates with **Razorpay Test Mode** to simulate full Indian payment flows (Card, UPI, Netbanking) in a sandboxed, risk-free environment without actual money movement.

> [!NOTE]
> PayGuard operates strictly on Razorpay Test Mode for development, demonstration, and validation. Test transactions do not represent live production payment processing.

### How Razorpay Test API is Used in PayGuard

```
 ┌──────────────────────┐         ┌────────────────────────┐         ┌──────────────────────┐
 │   Frontend Client    │         │    PayGuard Backend    │         │ Razorpay Test API    │
 └──────────┬───────────┘         └───────────┬────────────┘         └──────────┬───────────┘
            │                                 │                                 │
            │ 1. Request Purchase Clearance   │                                 │
            ├────────────────────────────────►│ 2. Evaluate Policy              │
            │                                 │    (Passes Policy Checks)       │
            │                                 │ 3. Create Test Order            │
            │                                 ├────────────────────────────────►│
            │                                 │ 4. Return order_id & public key │
            │ 5. Receive order_id + pub_key   │◄────────────────────────────────┤
            │◄────────────────────────────────┤                                 │
            │                                 │                                 │
            │ 6. Open Razorpay Test Popup     │                                 │
            │    (Simulate Card / UPI / Net)  │                                 │
            │ 7. Payment Success in Modal     │                                 │
            │                                 │                                 │
            │ 8. Send payment tokens          │                                 │
            │    (order_id, payment_id, sig)  │                                 │
            ├────────────────────────────────►│ 9. Verify HMAC SHA256 Signature│
            │                                 │    against RAZORPAY_KEY_SECRET  │
            │ 10. Return COMPLETED status     │ 10. Update DB: COMPLETED        │
            │◄────────────────────────────────┤                                 │
```

### Simulating Indian Payment Methods in Test Mode

When the native Razorpay Test Checkout modal opens in the UI, you can simulate multiple Indian payment instruments:

1. **Indian & International Test Cards**:
   * **Card Number**: `4111 1111 1111 1111` (or any valid Razorpay test card format).
   * **Expiry Date**: Any future month/year (e.g. `12/28`).
   * **Cardholder Name**: Any name (e.g. `Test Buyer`).
   * **CVV**: Any 3-digit number (e.g. `123`).
   * **2FA / OTP Simulation**: The Razorpay test gateway displays a simulated Indian banking OTP challenge. Click **"Success"** to simulate an authenticated bank approval or **"Failure"** to test gateway rejection.

2. **UPI Simulation (Unified Payments Interface)**:
   * **VPA / UPI ID**: Enter `success@razorpay` to simulate instantaneous UPI approval or `failure@razorpay` to simulate a failed UPI request.

3. **Netbanking Simulation**:
   * Select any major Indian bank (e.g. HDFC, SBI, ICICI, Axis).
   * Razorpay redirects to a sandbox confirmation page to simulate successful bank authorization.

### Backend Verification Safeguards
* **Protected Secrets**: `RAZORPAY_KEY_SECRET` remains server-side only and is never exposed to the frontend.
* **Server-Side Signature Validation**: Payment completion is cryptographically validated entirely on the backend via HMAC SHA256:
  $$\text{Expected Signature} = \text{HMAC-SHA256}(\text{order\_id} + "|" + \text{payment\_id}, \text{RAZORPAY\_KEY\_SECRET})$$
* **Untrusted Frontend Callbacks**: A frontend success callback alone **cannot** mark a transaction as completed. The database status remains `ORDER_CREATED` until the server validates the cryptographic signature.

---

## 🔒 Security Safeguards

Security safeguards implemented in this prototype:

* **Strict Secrets Isolation**: `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, and `RAZORPAY_KEY_SECRET` are loaded exclusively from `.env`. `RAZORPAY_KEY_SECRET` is never exposed to the client.
* **Server-Side Parameter Authorization**: `payment_agent.initiate_payment` re-evaluates all policy rules and product prices against PostgreSQL database records, ignoring client-supplied budget or price parameters.
* **Cryptographic Signature Verification**: Server validates HMAC SHA256 signatures over `razorpay_order_id|razorpay_payment_id` using the server's `RAZORPAY_KEY_SECRET`.
* **Order ID Matching**: Rejects incoming verification tokens if the client-submitted `razorpay_order_id` does not match the database transaction record.
* **Duplicate Purchase Intercept**: Blocks duplicate order creation if an active transaction is already `COMPLETED` for that Intent Contract.
* **Server-Side Retry Throttling**: Enforces `max_automated_retries` server-side to prevent infinite automated payment loops.
* **Transient Socket Recovery**: Implements HTTP session retry adapters with exponential backoff on `ConnectionResetError` (10054).
* **Defensive HTTP Headers**: Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, and explicit CORS origin policies.
* **Zero Secret Logging**: API keys, payment secrets, and signature hashes are masked from application logs and PostgreSQL audit entries.

---

## 🗄️ Database Schema & Models

PayGuard uses **PostgreSQL** with **SQLAlchemy ORM**:

```
 ┌────────────────────────┐       ┌────────────────────────┐
 │    intent_contracts    │       │        products        │
 ├────────────────────────┤       ├────────────────────────┤
 │ id (PK)                │       │ id (PK)                │
 │ raw_request            │       │ name                   │
 │ product_type           │       │ category               │
 │ purpose                │       │ description            │
 │ max_budget             │       │ base_price             │
 │ quantity               │       │ shipping_charge        │
 │ payment_authorized     │       │ tax                    │
 │ created_at             │       │ stock                  │
 └───────────┬────────────┘       └───────────┬────────────┘
             │                                │
             │ 1                            1 │
             │                                │
             │           ┌──────────┐         │
             └──────────►│    N     │◄────────┘
                         │transactions│
                         ├──────────┤
                         │ id (PK)  │
                         │ amount   │
                         │ status   │
                         │ rzp_order│
                         │ rzp_pay  │
                         └────┬─────┘
                              │ 1
                              │
                              ▼ N
                         ┌──────────┐
                         │audit_logs│
                         ├──────────┤
                         │ id (PK)  │
                         │ agent    │
                         │ action   │
                         │ decision │
                         │ reason   │
                         └──────────┘
```

### Table Definitions

1. **`intent_contracts`**: Stores user purchase requirements, purpose, extracted category, budget cap, and authorization boolean.
2. **`products`**: Merchant catalog inventory with base price, tax rate, delivery fee, and real-time stock count.
3. **`merchant_policies`**: Active spending rules (`max_transaction_amount`, `high_value_threshold`, `max_automated_retries`, `duplicate_purchase_block`).
4. **`transactions`**: Financial transaction ledger (`status`: `PENDING`, `ORDER_CREATED`, `WAITING_USER_CONFIRMATION`, `COMPLETED`, `BLOCKED`, `FAILED`).
5. **`audit_logs`**: Immutable audit records for every agent action, drift check, policy evaluation, and payment verification.

---

## 📡 API Reference

> [!NOTE]
> All IDs, amounts, and hashes in the examples below are illustrative placeholders.

### 1. Intent Extraction Agent
```http
POST /agent/intent
Content-Type: application/json

{
  "request": "Buy me a laptop for coding under 80000, quantity 1"
}
```
*Example Response (`201 Created`):*
```json
{
  "intent_contract_id": 1,
  "product_type": "Laptop",
  "purpose": "coding",
  "max_budget": 80000.0,
  "quantity": 1,
  "preferences": [],
  "payment_authorized": true
}
```

### 2. Buyer Agent Proposal
```http
POST /agent/buy
Content-Type: application/json

{
  "intent_contract_id": 1
}
```
*Example Response (`200 OK`):*
```json
{
  "product_id": 6,
  "product_name": "Acer Swift Go 14",
  "quantity": 1,
  "base_price": 59990.0,
  "shipping_charge": 250.0,
  "tax": 10798.2,
  "final_amount": 71038.2,
  "reason": "Acer Swift Go 14 offers an i5-13500H with 16GB RAM suitable for coding under INR 80,000.",
  "drift_detected": false,
  "drift_reasons": [],
  "attempts_count": 1,
  "alternative_selected": false,
  "attempts_history": [...]
}
```

### 3. Verification Agent & Policy Engine
```http
POST /agent/verify
Content-Type: application/json

{
  "intent_contract_id": 1,
  "product_id": 6,
  "quantity": 1
}
```
*Example Response (`200 OK`):*
```json
{
  "decision": "APPROVE",
  "reason": "All verification checks passed, payment is authorized, and transaction amount is within budget and policy limits.",
  "checks": [
    { "check_name": "category_match", "status": "PASS", "explanation": "Category 'Laptops' matches requested 'Laptop'." },
    { "check_name": "purpose_relevance", "status": "PASS", "explanation": "Product description matches purpose 'coding'." },
    { "check_name": "quantity_limit", "status": "PASS", "explanation": "Proposed quantity (1) within authorized limit (1)." },
    { "check_name": "stock_availability", "status": "PASS", "explanation": "Product in stock (20 available)." },
    { "check_name": "pricing_calculation", "status": "PASS", "explanation": "Final amount (INR 71038.20) calculated accurately." }
  ]
}
```

### 4. Create Razorpay Payment Order
```http
POST /agent/payment/create
Content-Type: application/json

{
  "intent_contract_id": 1,
  "product_id": 6,
  "quantity": 1,
  "user_confirmed": false
}
```
*Example Response (`201 Created`):*
```json
{
  "transaction_id": 1,
  "razorpay_order_id": "order_xxxxxxxxx",
  "razorpay_key_id": "rzp_test_xxxxxxxxx",
  "amount": 71038.2,
  "amount_in_paise": 7103820,
  "currency": "INR",
  "status": "ORDER_CREATED",
  "policy_decision": "APPROVE",
  "policy_reason": "All verification checks passed..."
}
```

### 5. Cryptographic Payment Verification
```http
POST /agent/payment/verify
Content-Type: application/json

{
  "transaction_id": 1,
  "razorpay_order_id": "order_xxxxxxxxx",
  "razorpay_payment_id": "pay_xxxxxxxxx",
  "razorpay_signature": "<example_hmac_sha256_signature>"
}
```
*Example Response (`200 OK`):*
```json
{
  "transaction_id": 1,
  "status": "COMPLETED",
  "verified": true,
  "razorpay_order_id": "order_xxxxxxxxx",
  "razorpay_payment_id": "pay_xxxxxxxxx",
  "message": "Payment verified and transaction completed successfully."
}
```

### 6. Audit Trail & Policy Telemetry
* `GET /api/audit-logs?limit=25`: Returns recent immutable PostgreSQL audit records.
* `GET /api/policies`: Returns active merchant policy thresholds.
* `GET /health`: Returns service health and database connection status.
* `GET /`: Serves the single-page web interface.

---

## 🛠️ Project Structure

```
PayGuard/
├── agents/
│   ├── buyer_agent.py          # Inventory search, drift detection & alternative finder
│   ├── intent_agent.py         # Groq LLM parameter extraction & IntentContract locking
│   ├── payment_agent.py        # Order creation, policy checks & signature verification
│   └── verification_agent.py   # Deterministic 5-factor independent verification
├── services/
│   ├── audit_service.py        # PostgreSQL audit trail logging service
│   ├── catalog_service.py      # Catalog lookup helper
│   ├── drift_detector.py       # 5-factor semantic and numerical drift detector
│   ├── groq_service.py         # Groq API client (openai/gpt-oss-20b)
│   ├── payment_service.py      # Razorpay client with connection retry resilience
│   └── policy_engine.py        # Deterministic Python policy decision engine
├── static/
│   ├── app.css                 # Minimal editorial dark design system
│   ├── app.js                  # Frontend controller & Razorpay checkout integration
│   └── index.html              # Single-page editorial AI buyer interface
├── app.py                      # FastAPI application, route declarations & middleware
├── database.py                 # SQLAlchemy engine, session factory & DB connection verification
├── diagnose_razorpay.py        # Safe diagnostic script for Razorpay credentials check
├── models.py                   # SQLAlchemy ORM models (Product, Intent, Transaction, Audit)
├── requirements.txt            # Python production dependencies
├── schemas.py                  # Pydantic v2 validation models & request/response schemas
├── seed_products.py            # PostgreSQL database seeding (15 products & default policy)
├── test_drift_and_alternatives.py # Automated test suite for drift detection & alternatives
├── test_payment_agent.py       # Automated test suite for payment agent & policy rules
├── .env.example                # Template for environment variables
└── README.md                   # Comprehensive developer documentation
```

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.11+**
* **PostgreSQL 14+** running locally or remotely
* **Groq API Key** ([console.groq.com](https://console.groq.com))
* **Razorpay Test Key & Secret** ([dashboard.razorpay.com](https://dashboard.razorpay.com))

---

### Step 1: Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Shivangi1515/PayGuard.git
cd PayGuard

# Create and activate virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

---

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```ini
# PostgreSQL Database URL
DATABASE_URL=postgresql://username:password@localhost:5432/payguard

# Groq LLM Configuration
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b

# Razorpay Test Mode Credentials
RAZORPAY_KEY_ID=rzp_test_your_key_id_here
RAZORPAY_KEY_SECRET=your_razorpay_secret_here
```

---

### Step 4: Seed Database Catalog

Initialize tables and seed the initial 15 verified catalog products and merchant policy:

```bash
python seed_products.py
```

---

### Step 5: Start the Application

```bash
uvicorn app:app --reload --port 8000
```

Open your browser and navigate to:
* **Web UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Testing Multi-Agent Scenarios

> [!NOTE]
> The examples below illustrate default catalog behavior with the default seed dataset (15 products) and active merchant policy.

| Scenario | Example Prompt | Expected Flow & Policy Outcome |
| :--- | :--- | :--- |
| **1. Autonomous Approval** | `Buy me wireless headphones under ₹25,000, quantity 1` | Selects `Audio-Technica ATH-M50xBT2` (₹20,838.20). $\text{Amount} < ₹80\text{k}$. **`APPROVE`** $\rightarrow$ Automatically opens Razorpay Test Mode checkout. |
| **2. Auto-Approved Laptop** | `Buy me a laptop for coding under 80000` | Selects `Acer Swift Go 14` (₹71,038.20). $\text{Amount} \le ₹80\text{k}$. **`APPROVE`** $\rightarrow$ Auto-launches checkout. |
| **3. No Product Under Budget** | `Buy me a laptop under 50000` | Lowest available model is ₹71,038.20. **`NO_PRODUCT_UNDER_BUDGET`** $\rightarrow$ Renders breakdown with +₹21,038.20 difference & "Increase Budget" action. |
| **4. Uncataloged Category** | `Buy running shoes under 3000` | Category not present in database. **`PRODUCT_NOT_AVAILABLE`** $\rightarrow$ Displays available verified merchant categories. |
| **5. Policy Hard Cap Block** | `Buy me a MacBook Pro 14 under ₹2,10,000` | Exceeds merchant policy cap (₹1,00,000). **`BLOCK`** $\rightarrow$ Safety Intercept prevents payment creation. |

---

## 🔮 Implemented vs. Future Extensions

### Currently Implemented
- [x] Multi-agent intent extraction with Groq LLM (`openai/gpt-oss-20b`)
- [x] Immutable `IntentContract` locking in PostgreSQL
- [x] Catalog search with availability classification & 3-attempt alternative finder
- [x] 5-factor independent deterministic verification matrix
- [x] Deterministic policy engine (`APPROVE`, `ASK_USER`, `BLOCK`)
- [x] Razorpay Test Mode checkout integration with server-side HMAC SHA256 signature verification
- [x] Indian payment method simulation (Cards, UPI, Netbanking, simulated OTP) in Test Mode
- [x] Immutable audit trail logging in PostgreSQL
- [x] Minimal editorial frontend with real-time multi-agent execution pipeline

### Future Extensions
- Multi-merchant live catalog API integrations
- User authentication and multi-tenant intent contract management
- Webhook-based asynchronous payment capture verification
- Configurable dynamic policy rules per organization
