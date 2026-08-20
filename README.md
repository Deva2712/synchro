# Sentinel — Real-Time Fraud Detection & Prevention for Digital Lending

Sentinel scores a loan application in about **20 ms**, decides
ALLOW / STEP-UP / REVIEW / BLOCK, and gives the fraud analyst the reasons behind that
decision instead of just a risk number.

Built for the Synchrony problem statement *"Real-Time Fraud Detection and Prevention in
Digital Lending Ecosystems"*.

## How it works

Rules are fast and easy to explain, but they only catch fraud someone has already seen.
Machine learning adapts, but on its own it is hard to explain. So Sentinel uses both,
plus an anomaly model that flags applications that simply do not look normal. The three
scores are combined using weights and thresholds that come from configuration, so a risk
team can retune them without changing code.

An LLM is used only to *explain* the decision in plain language — it never decides
anything. When an analyst confirms a case as fraud, that device is blocked immediately
for future applications, and the case is added to the training data for the next model.

---

## Architecture

```mermaid
flowchart LR
    subgraph Client["Channel"]
        LOS["Loan origination app<br/>(web / android / ios)"]
        UI["React console<br/>fraud analysts"]
    end

    subgraph API["Sentinel API — FastAPI, API-first"]
        AUTH["JWT auth · rate limit<br/>schema validation · PII masking"]
        FE["Feature engineering<br/>17 behavioural + transactional signals"]
        RULES["Rule pack<br/>11 rules, noisy-OR, hard blocks"]
        ML["Supervised model<br/>logistic regression"]
        ANOM["Novelty detector<br/>isolation forest"]
        POLICY["Decision policy<br/>weights + thresholds"]
    end

    subgraph AI["AI layer"]
        VEC["Vector search<br/>fraud typology KB"]
        LLM["Claude — Anthropic API or AWS Bedrock<br/>structured output + guardrails"]
    end

    subgraph Data["Storage"]
        PG[("PostgreSQL<br/>applications · users · velocity")]
        VS[("Vectors<br/>pgvector column")]
        MODELS["Model artefacts"]
    end

    LOS -->|"POST /v1/applications/score"| AUTH
    AUTH --> FE --> RULES --> POLICY
    FE --> ML --> POLICY
    FE --> ANOM --> POLICY
    POLICY -->|"decision in ~20 ms"| LOS
    POLICY --> PG
    POLICY -.->|"async, off the customer path"| VEC --> LLM -.-> PG
    VEC <--> VS
    UI -->|"queue · case · verdict"| AUTH
    UI -->|"analyst verdict"| PG
    PG -->|"labelled cases"| MODELS -->|"retrain"| ML
```

**Why the LLM call is asynchronous:** the customer-facing decision must never wait on a
language model. The deterministic path answers in ~20 ms; the narrative is written a few
seconds later and attached to the case file.

---

## Quickstart

```bash
# 1. Configure — nothing is hardcoded
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"   # paste into .env
#    also set SEED_ADMIN_PASSWORD and SEED_ANALYST_PASSWORD in .env

# 2. Install
make setup                    # venv + pip install + npm install

# 3. Run (three terminals)
make api                      # http://127.0.0.1:8000  — OpenAPI docs at /docs
make web                      # http://localhost:5173  — analyst console
make demo                     # pushes simulated traffic, including a device-farm ring

# 4. Test
make test                     # 20 tests
```

First start trains the model from synthetic traffic (~5 s) and seeds the typology
knowledge base. No API keys are required to run the demo — with no LLM credentials the
explanation layer falls back to a deterministic template, which is the designed failure
mode, not a stub.

**PostgreSQL instead of SQLite** (optional):

```bash
docker compose up -d
export DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel
pip install "psycopg[binary]"
```

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/v1/auth/login` | Issue a JWT (60 min, HS256) |
| `GET` | `/v1/me` | Current identity and role |
| `POST` | `/v1/applications/score` | **Score one application in real time** |
| `GET` | `/v1/applications` | Case queue, filterable by decision |
| `GET` | `/v1/applications/{id}` | Full case file: features, evidence, typologies, narrative |
| `POST` | `/v1/applications/{id}/feedback` | Analyst verdict → denylist + training data |
| `GET` | `/v1/model/info` | Live model metrics, weights, thresholds |
| `POST` | `/v1/model/retrain` | Retrain from analyst feedback (admin only) |
| `GET` | `/v1/metrics` | Operational metrics for the console |
| `GET` | `/health` | Liveness |

Example:

```bash
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"analyst@sentinel.local","password":"'"$SEED_ANALYST_PASSWORD"'"}' | jq -r .access_token)

curl -s -X POST localhost:8000/v1/applications/score \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d @backend/data/sample_application.json | jq
```

---

## How a decision is made

```
risk = 0.55 · P(fraud | supervised model)
     + 0.20 · novelty score (isolation forest)
     + 0.25 · rule score (noisy-OR over 11 rules)

BLOCK    risk ≥ 0.85   or any hard-block rule fires
REVIEW   risk ≥ 0.60
STEP_UP  risk ≥ 0.35   (OTP / liveness — friction, not refusal)
ALLOW    otherwise
```

Weights and thresholds are environment configuration, so a risk team can retune the
portfolio without a code change or a redeploy.

**Signals** (`backend/app/features.py`) — behavioural: session duration, typing speed,
paste events, form corrections, tab switches. Device/network: emulator, VPN/proxy,
geo-mismatch, night-time. Velocity, computed live off the write path: applications per
device and per IP in 24 h, and distinct applicant names per device — the signal that
catches an application ring on its third submission.

**Explainability** — every decision carries ranked evidence. Rule hits state the fact
("Same device used by 5 different applicant names in 24h"); model contributions are the
exact per-feature log-odds terms of the linear model (`coefficient × standardised value`),
not a post-hoc approximation.

---

## Measured results

Held-out synthetic evaluation (20 % of 8,000 applications, four fraud archetypes, 40 % of
fraud cases deliberately "stealthy", 1.5 % label noise):

| Metric | Value |
|---|---|
| ROC-AUC | **0.939** |
| PR-AUC | 0.861 |
| Recall at the review threshold | **82.2 %** |
| Precision at the review threshold | 68.2 % |
| False-positive rate | **3.9 %** |
| Decision latency p50 / p95 | **18 ms / 22 ms** |
| Straight-through rate on live demo traffic | 83 % |
| Tests passing | 20 / 20 |

The training data is synthetic but deliberately not easy: 40 % of the fraud cases only
show some of the warning signs, 1.5 % of labels are wrong, and genuine users share
devices, use VPNs and apply at 3 a.m. The first version of the generator produced an
AUC of 1.00, which only meant the fake fraud was too obvious.

---

## Security

- **Authentication** JWT bearer tokens, HS256, 60-minute expiry; `scrypt` password
  hashing with per-user salt; constant-time verification.
- **Authorisation** analyst vs admin; retraining a credit control is admin-only and logged.
- **Input validation** every request is a strict Pydantic model — bounded numerics,
  IPv4 validation, enum-constrained fields, and `extra="forbid"` so unknown fields are
  rejected rather than silently accepted.
- **Rate limiting** per-client sliding window on the auth and scoring endpoints.
- **Secrets** read from the environment only. No key, password, or token appears in the
  repository; `.env` is git-ignored and `.env.example` ships blank. If no JWT secret is
  configured the service generates an ephemeral one rather than falling back to a
  well-known default. If no seed password is supplied, one is generated and printed once.
- **CORS** explicit origin allow-list, never `*`.
- **PII** PAN, Aadhaar, mobile, email and card numbers are masked at the trust boundary,
  before anything is written to the database or sent to a model.

## Responsible AI

- **The LLM never decides.** It receives an already-made decision and explains it. An LLM
  outage degrades the wording, never the control.
- **Guardrails**: masked input, a system prompt that forbids invention and forbids
  reasoning about protected attributes, a structured output schema the model cannot break
  out of, and a masking pass over the model's own output.
- **Transparency**: the console labels every narrative with its source
  (`anthropic:claude-opus-5` or `rule_based_fallback`) and states that the decision was
  made by rules and models.
- **Human in the loop**: STEP_UP means friction, not refusal. Only an analyst verdict
  turns a case into a denylist entry and into training data.
- **Auditability**: features, scores, rule hits, evidence and narrative are persisted per
  application — a decision can be reconstructed months later.

---

## Layout

```
backend/
  app/
    main.py        FastAPI application — every capability is an endpoint
    decision.py    orchestration: the one place a decision is made
    rules.py       11 deterministic rules with human-readable evidence
    model.py       logistic regression + isolation forest, training and explainability
    features.py    raw event -> feature vector (the model's input contract)
    knowledge.py   fraud typology KB, embeddings and vector search
    llm.py         Claude via Anthropic API or AWS Bedrock, guardrails, fallback
    security.py    JWT, password hashing, rate limiting, PII masking
    schemas.py     request/response contracts and validation
    db.py          SQLAlchemy models — same code on SQLite and PostgreSQL
    config.py      all tunables from the environment
  data/
    generate.py    synthetic traffic with four fraud archetypes
    simulate.py    demo traffic driver
  tests/           20 tests: policy, rules, PII, auth, API, learning loop
frontend/src/      React console: live queue, case file, verdict, retrain
```

## Testing

```bash
make test
```

These cover the decision thresholds, the rule pack and its wording, PII masking, login
and roles, and input validation (bad IP, negative amount, unknown field). Two of them
test behaviour rather than implementation:

- a device-farm burst of six applications under six names **must** escalate to
  REVIEW/BLOCK by the last one;
- after an analyst confirms fraud, the **next** clean-looking application from that same
  device is blocked, with `CONFIRMED_FRAUD_DEVICE` in the evidence.

## Known limits

Deliberate, and each has a stated upgrade path:

| Shortcut | Upgrade when |
|---|---|
| Vector search is an in-process cosine over ~10 typologies | KB grows past a few hundred docs → `pgvector` `<=>` ordering |
| Rate limiting is in-process | more than one API replica → Redis or the API gateway |
| Local TF-IDF+SVD embeddings | swap `knowledge.embed` for Bedrock Titan / Voyage — storage and retrieval are unchanged |
| Training data is synthetic | real labelled history; the feedback loop is already wired |
| SQLite by default | `DATABASE_URL` already accepts PostgreSQL; compose file included |
