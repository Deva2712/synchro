# Requirement checklist

Every line of the hackathon brief, where it lives in this repository, and how to show it in the
demo. Marked honestly: **Done**, **Equivalent** (the brief said "or equivalent" and we used one),
or **Partial** (built but not fully deployed).

Legend for the demo column: 🖥️ = show on screen, 💬 = say it out loud, 📄 = it is in the PDF.

---

## Architecture expectations

### Frontend — React JS user interface

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| React JS interface | ✅ Done | [frontend/src/](frontend/src/) — React 18 + Vite, 5 components | 🖥️ The console at `localhost:5173` |
| Real interaction, not a mock | ✅ Done | [App.jsx](frontend/src/App.jsx) polls the API every 2 s | 🖥️ Run `make demo` and let rows appear live |
| Considered UI craft | ✅ Done | [styles.css](frontend/src/styles.css) — translucent chrome, size-specific tracking, instant press feedback, light/dark themes, reduced-motion / reduced-transparency / high-contrast support | 🖥️ Click the ☀/☾ button to switch theme |

### Backend — Spring Boot **or equivalent** API service

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| API service | 🟡 Equivalent | FastAPI (Python) instead of Spring Boot — the brief allows an equivalent. Chosen because the ML models are Python | 💬 Say it plainly: "FastAPI, the equivalent the brief allows" |
| API-first design | ✅ Done | 10 endpoints, auto-generated OpenAPI | 🖥️ Open `127.0.0.1:8000/docs` |
| Modular structure | ✅ Done | `config · db · features · rules · model · knowledge · llm · decision · security · schemas · main` | 🖥️ Show the file tree for two seconds |

### Database — PostgreSQL + pgvector or equivalent

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| PostgreSQL for structured data | ✅ Done | [docker-compose.yml](docker-compose.yml) runs `pgvector/pgvector:pg16`; [db.py](backend/app/db.py) works on both Postgres and SQLite | 🖥️ `docker compose ps` then `docker compose exec db psql -U sentinel -d sentinel -c "\dt"` |
| Vector storage for semantic search | 🟡 Equivalent | Typology embeddings are stored in the `typologies` table and searched by cosine similarity in [knowledge.py](backend/app/knowledge.py). The image already ships pgvector; with ~10 documents an in-process dot product is exact and instant | 💬 Say what it is *and* what the upgrade is — it is on slide 17 |

### AI layer — Bedrock or equivalent, embeddings, prompts, guardrails

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| LLM service | ✅ Done (code) / 🟡 not billed | [llm.py](backend/app/llm.py) — Claude via `anthropic` SDK; `LLM_BACKEND=bedrock` switches to `AnthropicBedrockMantle` with the AWS credential chain | 🖥️ Show `llm.py` lines 60–75; 💬 "no key configured, so it runs the deterministic fallback — that is the designed failure mode" |
| Embeddings model for vector search | ✅ Done | TF-IDF + SVD embedder, persisted with joblib; one function to swap for Titan/Voyage | 🖥️ The "Matched typologies" block with its similarity score |
| Prompt templates | ✅ Done | `SYSTEM_PROMPT` and `_prompt()` in [llm.py](backend/app/llm.py) | 📄 Slide 10 |
| Guardrails | ✅ Done | PII masked before the prompt, structured output schema (`FraudNarrative`), output masked again, timeout + fallback, and the model can never change the decision | 🖥️ The footnote under every AI summary in the console |
| AI agent framework | ⚪ Not used (optional) | Deliberate: a single structured call is the right size for this job | 💬 Only if asked |

### Cloud layer — AWS or equivalent, secure storage, monitoring

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| Deployment platform | 🟡 Partial | Runs in Docker locally; the app is stateless and config-driven, so it is deploy-ready (ECS/Fargate + RDS + Secrets Manager). **Not deployed to a live AWS account** | 💬 Be honest: "runs in Docker, designed for ECS + RDS; I did not have an AWS account to deploy into" |
| Secure storage and access management | ✅ Done | All secrets from environment variables, IAM/credential chain for AWS, `.env` git-ignored, roles enforced on the API | 🖥️ `cat .env.example` — every value blank |
| Monitoring / logging | 🟡 Partial | Structured startup, retrain and LLM-failure logs; `/health` and `/v1/metrics` endpoints feed the dashboard | 🖥️ The API terminal output and the KPI row |

### Security layer

| Requirement | Status | Where | How to demonstrate |
|---|---|---|---|
| Authentication / authorization | ✅ Done | JWT (HS256, 60 min), scrypt password hashing, analyst vs admin roles | 🖥️ Sign in; 🖥️ show that retrain is admin-only (`test_analyst_cannot_retrain`) |
| Input validation | ✅ Done | [schemas.py](backend/app/schemas.py) — bounded numbers, IPv4 check, enums, `extra="forbid"` | 🖥️ In `/docs`, send a negative amount → `422` |
| Secure API usage | ✅ Done | Bearer tokens on every endpoint, per-client rate limiting, explicit CORS allow-list | 🖥️ `curl` without a token → `401` |
| No hardcoded secrets | ✅ Done | Nothing in the code; a missing JWT secret becomes a random ephemeral one, never a default | 🖥️ `grep -ri "password\s*=" backend/app` returns only variable names |
| Responsible data handling | ✅ Done | PAN, Aadhaar, mobile, email, card numbers masked at the trust boundary before storage or prompting | 🖥️ Show a stored record: identifiers are already `XXXX` |

---

## Engineering practices

| Practice | Status | Evidence |
|---|---|---|
| Clean, modular code | ✅ | One responsibility per module; the decision is assembled in exactly one place ([decision.py](backend/app/decision.py)) |
| Meaningful naming | ✅ | `score_application`, `evaluate`, `build_features`, `PROMOTION_TOLERANCE` — no `data2`, no `tmp` |
| API-first design | ✅ | Every capability is an endpoint; the console only consumes them |
| Version control (Git/GitHub) | ✅ | https://github.com/Deva2712/synchro — incremental commits with real messages |
| Clear README | ✅ | [README.md](README.md) — architecture, quickstart, API table, security, limits |
| Setup and run instructions | ✅ | README quickstart + [deck/Demo-Guide.pdf](deck/Demo-Guide.pdf) (14-page runbook) |
| Architecture diagram | ✅ | Mermaid diagram in the README, layered diagram on slide 5 |
| Unit testing / coverage | ✅ | 20 tests — policy, rules, PII, auth, validation, plus two behavioural tests |
| Secure credential handling | ✅ | Environment only; `.env` git-ignored; `.env.example` blank |
| Responsible AI | ✅ | LLM cannot decide; no protected attributes; masked PII; human in the loop; full audit trail |
| Explainability and transparency | ✅ | Ranked evidence, exact log-odds contributions, matched typology, and the model's source named in the UI |

---

## Submission requirements

| Requirement | Status | Action |
|---|---|---|
| PPT or PDF explaining approach, insights, findings, solution, code | ✅ | [deck/Sentinel.pdf](deck/Sentinel.pdf) — 18 slides |
| Recorded demo | ⬜ **You still have to record it** | Follow [SCRIPT.md](SCRIPT.md) |
| ZIP file to Technologyinterns@syf.com | ⬜ To do | `zip <roll>.zip <roll>.pdf <roll>.mp4` |
| Files named with roll number only | ⬜ To do | `python deck/build.py --pdf --author "Name" --roll "<roll>"` then rename |
| Deadline 12:00 PM IST, 21 August | ⬜ | Send it early |
| Present on 24–25 August | ⬜ | Q&A prep is on page 5 of the Demo Guide |

---

## Where we knowingly differ from the brief

Say these before a judge asks. Being straight about them is worth more than pretending.

1. **FastAPI, not Spring Boot.** The brief allows an equivalent. The models are scikit-learn, so a
   Python service keeps training and serving in one language and removes a network hop.
2. **Cosine search in Python, not a pgvector query.** The knowledge base is ten documents. The
   Postgres image already has pgvector; the switch is one SQL clause and is written down in the README.
3. **Not deployed to a live AWS account.** It runs in Docker with a config-driven, stateless design.
   The Bedrock code path exists and is one environment variable away.
4. **Synthetic training data.** Real lending data is not available to a student project. The
   generator encodes four documented fraud archetypes and is deliberately hard — 40 % of fraud cases
   show only some warning signs, and 1.5 % of labels are wrong.
