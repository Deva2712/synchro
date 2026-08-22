# Demo script — 5 minutes

*Italics* = what you say. `code` = what you run.

## Setup before recording

**Option A — everything in Docker** (simplest, one command):

```bash
docker compose up --build -d                 # wait for both containers to be healthy
docker compose exec db psql -U sentinel -d sentinel -c "TRUNCATE applications;"
```
Console and API are both on **http://localhost:8000**. Traffic:
`docker compose exec app python -m backend.data.simulate --n 60 --rate 5 --ring --password "$SEED_ANALYST_PASSWORD"`

**Option B — local, if you want the terminals visible on camera:**

```bash
docker compose up -d db
rm -f sentinel_model.joblib
make api      # terminal 1, wait for "Model ready"
make web      # terminal 2 -> localhost:5173
              # terminal 3 free for `make demo`
```

Leave the login screen showing. Notifications off, browser at 100%.

---

## 1. The problem (30s) — login screen

> *"I'm <name>. My problem is real-time fraud detection in digital lending.*
>
> *Three hard parts. Fraud changes every few weeks, rules take months to ship. Every good customer
> you wrongly block just goes to another lender. And the decision has to happen while the customer
> is waiting on screen.*
>
> *So I built Sentinel. It scores an application in about 30 milliseconds and tells the analyst why."*

## 2. Tests and API (30s) — terminal, then `/docs`

```bash
make test
```

> *"Twenty tests passing. Two of them test behaviour: six applications from one device must escalate,
> and once fraud is confirmed the next application from that device must be blocked. I'll show both."*

Open `127.0.0.1:8000/docs`.

> *"API first — ten endpoints with generated docs. The console is just one client."*

## 3. Live traffic (45s) — sign in as admin, then `make demo`

> *"Simulated traffic hitting the real API. Every line in the terminal is a real response.*
>
> *Two thirds go straight through. p95 is under 40 milliseconds including a hop to PostgreSQL.*
>
> *Four outcomes, not two. Allow, step up, review, block. That's the answer to false positives —
> suspicion costs an OTP, not the loan."*

## 4. The fraud ring (45s) — click the BLOCK filter

> *"Several of these say 'same device used by five different applicant names in 24 hours'.*
>
> *Each application on its own is clean. A rule engine checking one at a time passes all of them.
> What gives it away is the pattern across them — and we see it because device and IP velocity are
> counted at scoring time, not in a batch job tonight."*

## 5. Why it decided (75s) — open one of those rows

> *"Score composition first — how much came from the ML model, the anomaly model and the rules.*
>
> *Then ranked evidence. Orange is rules, in plain English. Blue is the model itself: typing speed,
> plus 2.7 log-odds. I used logistic regression on purpose — it's linear, so each contribution is
> exact arithmetic, not a guess from a separate explainer.*
>
> *Then the closest fraud typology from vector search, with the control that stops it."*

Point at the grey footnote.

> *"'Explanation only — the decision was made by the rules and models.' The LLM runs after the
> decision is already returned. If it's slow or down, the wording changes, the decision doesn't.
> Right now it's on the deterministic fallback because no API key is set — one variable points it at
> Claude on the Anthropic API or AWS Bedrock."*

## 6. It learns (60s) — click Confirm fraud, then `make demo`

Filter BLOCK again, open a new case from that device.

> *"Blocked, and the first reason is 'device previously confirmed as fraud by an analyst'. One click
> protected the whole portfolio from the next application — no retrain, no deploy."*

Click **Retrain from feedback**.

> *"Labelled cases go back in at 12 times the weight. But a new model is only promoted if it isn't
> worse than the current one — I added that after one bad label moved the score the wrong way."*

## 7. Close (45s) — `cat .env.example`

> *"Every secret comes from the environment. This template ships blank, the real file is git-ignored,
> and with no JWT secret set it generates a random one instead of a default. Passwords are hashed,
> every endpoint needs a token, retraining needs admin, and PAN, Aadhaar, phone and email are masked
> before anything is stored or sent to a model.*
>
> *So: 30 milliseconds a decision, four outcomes instead of yes or no, an explanation for every one,
> and a loop that learns from the analyst. Code and README are on GitHub. Thank you."*

---

**3-minute cut:** keep scenes 3–6 only. Mention the 20 tests while the queue fills.

**Don't:** read the slides · apologise for the LLM fallback (it's the designed failure mode) ·
claim it's deployed on AWS (say Docker, built to deploy there).

**If it breaks:** empty queue → `make demo` · no retrain button → sign in as admin ·
session expired → sign in again.
