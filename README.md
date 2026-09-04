# PayGuard 🛡️

### The Multi-Agent Autonomous Commerce Platform That Pays Within Your Intent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=flat-square)](https://groq.com)
[![Razorpay](https://img.shields.io/badge/Razorpay-Test_Mode-0C2340?style=flat-square&logo=razorpay&logoColor=white)](https://razorpay.com)
[![License](https://img.shields.io/badge/License-MIT-gold?style=flat-square)](LICENSE)

---

## 📌 Overview

AI agents are rapidly transitioning from conversational recommendation engines to **autonomous economic actors** capable of taking actions on behalf of humans. In commerce, an unconstrained AI model can turn a hallucination, ambiguity, or specification drift directly into an unauthorized financial transaction.

> **"The AI can act. Your intent sets the boundary."**  
> **"The AI proposes. The Policy Engine decides. Razorpay executes."**

**PayGuard** is an autonomous multi-agent agentic-commerce infrastructure system. It establishes a bounded, verifiable, and policy-governed transaction layer between natural-language user intent and financial payment execution. 

PayGuard transforms natural-language prompts into an immutable **Intent Contract**, tasks specialized agents with catalog discovery and drift interception, independently audits proposals across a **5-Factor Verification Matrix**, applies **Deterministic Policy Guardrails**, and securely finalizes payments via **Razorpay Test Mode** with server-side **HMAC SHA256** cryptographic signature validation.

---

## 🏛️ System Architecture

PayGuard operates on a strict **Separation of Concerns & Separation of Powers** principle: Large Language Models (LLMs) are restricted to semantic intent extraction and candidate discovery; they have **zero authority** to grant financial clearance or execute payments.

```mermaid
flowchart TD
    User([User Natural Language Prompt]) -->|POST /agent/intent| IA[Intent Agent]
    
    subgraph S1["1. Intent Locking"]
        IA -->|Extract Parameters via Groq LLM| IC[(PostgreSQL: IntentContract)]
    end
    
    IC -->|POST /agent/buy| BA[Buyer Agent]
    
    subgraph S2["2. Catalog Discovery & Drift Intercept"]
        BA <-->|Query Inventory & Specs| DB[(PostgreSQL: Products Catalog)]
        BA --> DD{Drift Detector}
        DD -->|Intent Drift Detected| ALT[Alternative Finder: Up to 3 Attempts]
        ALT --> BA
        DD -->|Compliant Proposal| PP[Purchase Proposal]
    end
    
    PP -->|POST /agent/verify| VA[Verification Agent]
    
    subgraph S3["3. Independent 5-Factor Verification"]
        VA --> C1[1. Category Match Check]
        VA --> C2[2. Purpose Relevance Check]
        VA --> C3[3. Quantity Limit Check]
        VA --> C4[4. Stock Availability Check]
        VA --> C5[5. Pricing Formula Validation]
    end
    
    S3 --> PE[Deterministic Policy Engine]
    
    subgraph S4["4. Deterministic Policy Enforcement"]
        PE --> DEC{Policy Decision}
        DEC -->|APPROVE| PA[Payment Agent]
        DEC -->|ASK_USER| CONF[Pause Agent & Await User Confirmation]
        CONF -->|User Confirmed| PA
        DEC -->|BLOCK| BLK[Halt & Reject Order Creation]
    end
    
    subgraph S5["5. Payment Execution & Verification"]
        PA -->|POST /agent/payment/create| RZP_API[Razorpay Orders API]
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

## 🤖 The Multi-Agent Pipeline

PayGuard decomposes agentic commerce into five decoupled agents and services:

| Agent / Service | Core Responsibility | Technology | Determinism |
| :--- | :--- | :--- | :--- |
| **1. Intent Agent** | Extracts structured constraints (`product_type`, `purpose`, `max_budget`, `quantity`, `preferences`, `payment_authorized`) and locks an immutable `IntentContract` in PostgreSQL. | Groq LLM (`llama-3.3-70b-versatile`) + Pydantic | Semantic + Schema-enforced |
| **2. Buyer Agent** | Discovers merchant inventory candidates, calculates base + shipping + tax formulas, handles availability classification, and executes a 3-attempt alternative search loop. | PostgreSQL + Groq + Python Algorithms | Hybrid Discovery |
| **3. Verification Agent** | Independently audits the candidate product against the `IntentContract` across 5 isolated checks without LLM involvement. | Pure Python + PostgreSQL | **100% Deterministic** |
| **4. Policy Engine** | Evaluates deterministic financial and merchant guardrails (budget caps, high-value thresholds, duplicate blocks). Returns `APPROVE`, `ASK_USER`, or `BLOCK`. | Pure Python + PostgreSQL | **100% Deterministic** |
| **5. Payment Agent** | Re-verifies all parameters on the backend, generates server-side Razorpay test orders, opens the checkout interface, and cryptographically verifies signatures. | Razorpay Python SDK + HMAC SHA256 | **100% Cryptographic** |

---

## 🛡️ Policy & Verification Guardrails

### The 5-Factor Verification Matrix

Before any proposed purchase reaches the Policy Engine, the **Verification Agent** independently verifies the candidate against the authoritative database record:

1. **`category_match`**: Verifies candidate category matches requested product type.
2. **`purpose_relevance`**: Confirms product specifications satisfy user purpose (e.g., coding, noise cancellation).
3. **`quantity_limit`**: Enforces `proposed_quantity <= authorized_quantity`.
4. **`stock_availability`**: Asserts `available_stock >= requested_quantity`.
5. **`pricing_calculation`**: Validates deterministic pricing formula:  
   $$\text{Final Amount} = (\text{Base Price} + \text{Shipping Charge} + \text{Tax}) \times \text{Quantity}$$

### Policy Engine Decisions

| Decision | Trigger Conditions | Execution Behavior |
| :--- | :--- | :--- |
| **`APPROVE`** | All 5 checks PASS, payment authorized, and $\text{Final Amount} < \text{High-Value Threshold}$ (`₹80,000`). | **Auto-Approved**: Automatically launches Razorpay checkout without requiring secondary manual approval. |
| **`ASK_USER`** | All 5 checks PASS, but $\text{Final Amount} \ge \text{High-Value Threshold}$ (`₹80,000`). | **Paused Execution**: Explains high-value threshold trigger, renders confirmation prompt, and requires explicit user approval before payment order creation. |
| **`BLOCK`** | Any verification failure, intentional drift, unauthorized payment flag, amount exceeding budget, or amount exceeding merchant cap (`₹1,00,000`). | **Safety Intercept**: Payment order creation is strictly denied (returns HTTP 400). Renders reason and enables alternative search. |

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
   - Triggered when all catalog matches have `stock < quantity`.
   - Automatically searches for compliant in-stock alternatives.
4. **`SPEC_NOT_AVAILABLE`**:
   - Triggered when candidate products fail hard specification constraints.
   - Strictly preserves constraints without silent relaxation.

---

## 🔒 Security Hardening

PayGuard implements production-style security safeguards across all architectural layers:

* **Strict Secrets Isolation**: `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, and `RAZORPAY_KEY_SECRET` are loaded exclusively from `.env`. `RAZORPAY_KEY_SECRET` is never exposed to the frontend or returned in API payloads.
* **Server-Side Authorization**: `payment_agent.initiate_payment` never trusts frontend parameters (prices, budgets, or authorization flags). It queries authoritative PostgreSQL models directly.
* **Cryptographic Signature Verification**: Razorpay payment verification executes server-side HMAC SHA256 validation comparing `razorpay_order_id|razorpay_payment_id` against `RAZORPAY_KEY_SECRET`.
* **Order ID Matching**: Rejects incoming verification tokens if the client-submitted `razorpay_order_id` does not match the database transaction record.
* **Duplicate Purchase Intercept**: Blocks duplicate order creation if an active transaction is already `COMPLETED` for that Intent Contract.
* **Server-Side Retry Throttling**: Enforces `max_automated_retries` server-side to prevent infinite payment loops.
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

### 1. Intent Extraction Agent
```http
POST /agent/intent
Content-Type: application/json

{
  "request": "Buy me a laptop for coding under 80000, quantity 1"
}
```
**Response (`201 Created`):**
```json
{
  "intent_contract_id": 42,
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
  "intent_contract_id": 42
}
```
**Response (`200 OK`):**
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
  "intent_contract_id": 42,
  "product_id": 6,
  "quantity": 1
}
```
**Response (`200 OK`):**
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
  "intent_contract_id": 42,
  "product_id": 6,
  "quantity": 1,
  "user_confirmed": false
}
```
**Response (`201 Created`):**
```json
{
  "transaction_id": 24,
  "razorpay_order_id": "order_TY6HBUTbuZtDy2",
  "razorpay_key_id": "rzp_test_TY3FK2uuxFvV3A",
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
  "transaction_id": 24,
  "razorpay_order_id": "order_TY6HBUTbuZtDy2",
  "razorpay_payment_id": "pay_TY6HExample123",
  "razorpay_signature": "9ef5426da7d673f8a42f5c7de0b35b64..."
}
```
**Response (`200 OK`):**
```json
{
  "transaction_id": 24,
  "status": "COMPLETED",
  "verified": true,
  "razorpay_order_id": "order_TY6HBUTbuZtDy2",
  "razorpay_payment_id": "pay_TY6HExample123",
  "message": "Payment verified and transaction completed successfully."
}
```

### 6. Audit Trail & Policy Telemetry
* `GET /api/audit-logs?limit=25`: Returns recent immutable PostgreSQL audit records.
* `GET /api/policies`: Returns active merchant policy thresholds.
* `GET /health`: Returns service health and database connection status.

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
│   ├── drift_detector.py       # 5-factor semantic and numerical drift detector
│   ├── groq_service.py         # Groq API client with JSON schema enforcement
│   ├── payment_service.py      # Razorpay client with connection retry resilience
│   └── policy_engine.py        # Deterministic Python policy decision engine
├── static/
│   ├── app.css                 # Minimal editorial dark design system
│   ├── app.js                  # Frontend controller & Razorpay checkout integration
│   └── index.html              # Single-page editorial AI buyer interface
├── app.py                      # FastAPI application, route declarations & middleware
├── database.py                 # SQLAlchemy engine, session factory & DB connection verification
├── models.py                   # SQLAlchemy ORM models (Product, Intent, Transaction, Audit)
├── schemas.py                  # Pydantic v2 validation models & request/response schemas
├── seed_products.py            # PostgreSQL database seeding (15 products & default policy)
├── requirements.txt            # Python production dependencies
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
DATABASE_URL=postgresql://postgres:password@localhost:5432/payguard

# Groq LLM Configuration
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

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

| Scenario | Input Prompt | Expected Flow & Policy Outcome |
| :--- | :--- | :--- |
| **1. Autonomous Approval** | `Buy me wireless headphones under ₹25,000, quantity 1` | Picks `Audio-Technica ATH-M50xBT2` (₹20,838.20). $\text{Amount} < ₹80\text{k}$. **`APPROVE`** $\rightarrow$ Automatically opens Razorpay checkout. |
| **2. Auto-Approved Laptop** | `Buy me a laptop for coding under 80000` | Picks `Acer Swift Go 14` (₹71,038.20). $\text{Amount} \le ₹80\text{k}$. **`APPROVE`** $\rightarrow$ Auto-launches checkout. |
| **3. No Product Under Budget** | `Buy me a laptop under 50000` | Lowest model is ₹71,038.20. **`NO_PRODUCT_UNDER_BUDGET`** $\rightarrow$ Renders breakdown with +₹21,038.20 diff & "Increase Budget" button. |
| **4. Uncataloged Category** | `Buy running shoes under 3000` | Category not in database. **`PRODUCT_NOT_AVAILABLE`** $\rightarrow$ Displays available verified categories. |
| **5. Policy Hard Cap Block** | `Buy me a MacBook Pro 14 under ₹2,10,000` | Exceeds merchant cap (₹1,00,000). **`BLOCK`** $\rightarrow$ Safety Intercept prevents payment creation. |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
