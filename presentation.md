# Prompt: build the Sentinel presentation

Paste everything below into Claude (Claude Design, or Claude with the design/slides skill) to
generate the deck. Every number in here is measured from the running system — do not change them.

---

## The ask

Build a **16–18 slide presentation** for a hackathon project called **Sentinel**, a real-time fraud
detection platform for digital lending. Output a self-contained HTML deck (16:9, one section per
slide, printable to PDF) or a `.pptx` — whichever the tooling supports best.

**Audience:** the Synchrony hiring team, at a campus presentation. Engineers and risk people, not
marketers. They have read the problem statement and will ask hard questions.

**Voice:** a strong student engineer explaining their own work. Plain, direct, specific. First person
is fine ("I built", "I found"). No consultant language, no hype, no "revolutionary" or "cutting-edge",
no emoji.

**Hard rules:**
- Do not invent numbers, features, or claims. Everything factual you need is in this brief.
- Do not claim it is deployed on AWS. It runs in Docker and is built to deploy there.
- Include the limitations slide. Owning the gaps is a scoring point, not a weakness.
- Every claim that has a number should show it.

---

## The problem statement (given to us)

> Real-Time Fraud Detection and Prevention in Digital Lending Ecosystems. Build a real-time fraud
> detection platform that integrates machine learning and behavioural analytics to identify, prevent
> and respond to fraud across digital lending channels. Fraud patterns are increasingly sophisticated
> and dynamic; rule-based systems struggle to keep up. The challenge is a proactive, self-learning
> system that detects anomalies in real time, reduces false positives, and adapts to new fraud vectors
> without hurting customer trust or operational efficiency.

---

## What was actually built

**Stack:** React 18 + Vite console · FastAPI (Python) API · PostgreSQL + pgvector in Docker (SQLite
by default for zero-setup) · scikit-learn models · Claude via the Anthropic API or AWS Bedrock for
explanations only.

**The decision path**, in order: input validation and PII masking → 17 features → three scorers in
parallel (11-rule pack, logistic regression, isolation forest) → weighted policy → decision returned
→ *then*, asynchronously, vector search over a fraud typology knowledge base and an LLM narrative.

**Scoring formula** (weights and thresholds come from environment variables, not code):
```
risk = 0.55 × ML probability + 0.20 × anomaly score + 0.25 × rule score

BLOCK    risk ≥ 0.85, or a hard-block rule fires
REVIEW   risk ≥ 0.60
STEP_UP  risk ≥ 0.35
ALLOW    below that
```

**The 17 features, in three groups:**
- *Behavioural:* time on form, typing speed, paste events, form corrections, tab switches, hour of day
- *Device and network:* emulator/rooted, VPN or proxy, IP location vs declared address
- *Velocity, counted live at scoring time:* applications per device in 24 h, per IP in 24 h, distinct
  applicant names per device
- *Credit and identity:* loan-to-income, loan size, account age, email domain age, prior defaults
- *Deliberately excluded:* name, gender, religion, caste, age band, locality

**Measured results — model quality**, on 1,600 held-out applications:
| Metric | Value |
|---|---|
| ROC-AUC | 0.9386 |
| PR-AUC | 0.8613 |
| Recall at the review threshold | 82.2% |
| Precision at the review threshold | 68.2% |
| False-positive rate | 3.85% |

**Measured results — live demo run** (60 applications, on PostgreSQL):
| Metric | Value |
|---|---|
| Decision latency p50 / p95 | 29 ms / 37 ms (18 ms / 22 ms on SQLite) |
| Straight-through, no friction | 66.7% (40 of 60) |
| Step-up | 10.0% (6) |
| Review | 15.0% (9) |
| Blocked | 8.3% (5) |
| Tests passing | 20 / 20 |

Note the demo stream deliberately contains about 15% fraud plus a device-farm burst, so the
straight-through rate is far below what a real portfolio would show.

**Training data is synthetic and deliberately hard:** four documented fraud archetypes (device farm
ring, synthetic identity, bust-out, bot), 40% of fraud cases show only *some* warning signs, 1.5% of
labels are wrong, and legitimate users share devices, use VPNs and apply at 3 a.m. An earlier version
of the generator scored AUC 1.00, which only meant the fake fraud was too obvious.

**The fraud-ring walkthrough** — six applications from one device, each individually clean (no
emulator, no VPN, normal typing, an 800-day-old account, ₹1.8L against ₹60k monthly income):
| # | Applicant | Risk | Decision | Leading reason |
|---|---|---|---|---|
| 1 | Rahul Verma | 0.15 | ALLOW | IP location differs from address (model, +0.27) |
| 2 | Sneha Rao | 0.10 | ALLOW | Account age (model, +0.26) |
| 3 | Imran Qureshi | 0.21 | ALLOW | IP location differs from address (model, +0.27) |
| 4 | Anita Joshi | 0.44 | STEP UP | Same device used by 3 different applicant names in 24h |
| 5 | Vivek Nanda | 0.55 | STEP UP | Same device used by 4 different applicant names in 24h |
| 6 | Farah Sheikh | 0.59 | STEP UP | Same device used by 5 different applicant names in 24h |

Then the analyst confirms one as fraud, and application 7 from that device is BLOCKed outright, with
`CONFIRMED_FRAUD_DEVICE` as its first line of evidence.

**The learning loop, three steps:**
1. *Instant* — a confirmed fraud denylists that device and IP portfolio-wide, via a hard-block rule.
   No retrain, no deploy.
2. *On demand* — labelled cases rejoin training at 12× the weight of a synthetic sample. Admin-only,
   logged, and the API returns the old and new metrics side by side.
3. *Governed* — a candidate model is only promoted if it loses no more than 0.01 ROC-AUC against the
   incumbent. Observed: one labelled case moved ROC-AUC 0.9386 → 0.9339, a 0.005 drop, inside
   tolerance, so it was promoted and both numbers were reported. A larger drop keeps the old model
   serving.

**Explainability** — three layers, all shown to the analyst:
- Rule hits as plain facts: *"Same device used by 5 different applicant names in 24h"*
- Model contributions as exact arithmetic: *"Typing speed raises risk (contribution +2.68 log-odds)"*.
  Logistic regression was chosen **because** it is linear — the contribution is `coefficient × scaled
  value`, so the explanation is the decision itself, not a surrogate model's guess.
- Vector search returns the closest fraud typology (e.g. "Device farm / application ring", similarity
  0.94) together with the control that stops it.

**The AI guardrails, in order:** PAN, Aadhaar, mobile, email and card numbers masked before the prompt
is built → system prompt forbids inventing facts, guessing masked values, or reasoning about protected
attributes → structured output schema with four allowed actions → output masked again → 20 s timeout,
one retry, then a deterministic fallback. The LLM is called *after* the decision is returned, so it can
never delay or change one. With no API key configured it runs the fallback, and the console labels
every summary with its source.

**Security:** JWT (HS256, 60 min) with scrypt-hashed passwords and constant-time comparison · analyst
vs admin roles, retrain is admin-only · strict input schemas that reject unknown fields · per-client
rate limiting · explicit CORS allow-list · every secret from the environment, `.env` git-ignored,
`.env.example` blank, and a missing JWT secret becomes a random ephemeral one rather than a default.

**Tests — 20, including two behavioural ones** that assert the product promise: a six-application
device-farm burst must escalate by the last one, and after a confirmed fraud the next clean-looking
application from that device must be blocked.

**Known limitations, each with its upgrade path:**
| Simplification | Why it is fine now | Upgrade |
|---|---|---|
| Vector search runs in Python | The knowledge base is 10 documents | pgvector `<=>` ordering |
| Local TF-IDF + SVD embeddings | Offline, free, deterministic | Bedrock Titan or Voyage — one function |
| Rate limiting held in memory | Correct for one API instance | Redis or the API gateway |
| Training data is synthetic | Real lending data is not available to a student | Real labelled history; the loop is built |
| SQLite by default | Anyone can run it with no setup | `DATABASE_URL` already accepts Postgres |
| Console polls every 2 s | The real-time part is the 30 ms decision | Server-sent events |

**Next steps I would work on:** linking fraud rings by shared bank accounts and addresses rather than
just devices, checking loan stacking across lenders, and running a new model in shadow mode before
promoting it.

**Repository:** https://github.com/Deva2712/synchro

---

## Slide plan

Use these titles and content. Merge or split only if a slide is clearly overfull.

1. **Title** — Sentinel · Real-time fraud detection and prevention in digital lending. Sub-line: the
   stack. Placeholders for `<name>` and `<roll number>`.
2. **The problem** — four cards: fraud changes faster than rule releases · false positives cost real
   customers silently · the decision must fit inside a form submit · a score alone is not actionable.
   Close with: *decide in milliseconds, keep learning, keep good customers, explain every call.*
3. **What I learned building it** — four insights: behaviour is harder to fake than documents ·
   velocity is the strongest signal and only exists if computed on the write path · rules and ML cover
   different failures · the output should be an explanation, not a number.
4. **What I built** — the four decisions as cards, plus three stat tiles: 37 ms p95, 0.939 ROC-AUC,
   instant + governed learning loop.
5. **Architecture** — five stacked layers with arrows: Frontend → Security → Decision engine (~30 ms)
   → AI layer (asynchronous) → Database. Mark clearly where the decision is returned and that the LLM
   runs after it.
6. **How the score is calculated** — the formula, the four thresholds, and three notes: weights are
   config not code · rules combine with noisy-OR so weak signals accumulate but never reach certainty ·
   three models cover three different failure modes.
7. **The 17 signals** — the four groups, plus the excluded-attributes card.
8. **Example: catching a fraud ring** — the six-row table above, then the callout about escalating to
   verification rather than a block, and application 7 being blocked after the analyst's verdict.
9. **Explainability** — the three layers with the real example strings.
10. **AI layer and guardrails** — where the LLM sits, the five guardrails in order, and the fact that
    it works on Bedrock with one environment variable.
11. **The learning loop** — the three steps as columns, with the honest promotion-gate observation.
12. **Results** — the two metric tables side by side, plus the note on why the synthetic data is hard
    and what 68% precision actually means (one in three reviewed cases is genuine, and it is
    *reviewed*, not blocked).
13. **The console — live stream** — screenshot, with a line about decisions carrying icon + label so
    colour is never the only signal.
14. **The console — case file** — screenshot, pointing at score composition, evidence, typology, the
    AI summary and its source line, and the two verdict buttons.
15. **Security and responsible AI** — two columns, six bullets each, from the lists above.
16. **How the code is organised** — API-first, one module per job, configuration not constants, the 20
    tests, and the five `make` commands.
17. **Known limitations** — the table above, then the next-steps line.
18. **Summary** — five bullets mapping the solution back to the brief (real time · self-learning ·
    fewer false positives · new fraud vectors · customer trust), plus how to run it.

## Screenshots to place

Two images live in `deck/assets/`:
- `console-queue.png` → slide 13, full width
- `console-detail.png` → slide 14, centred, roughly 60% width (it is a tall full-page capture)

Embed them as base64 data URIs so the deck is one self-contained file.

## Design direction

- **Light background, dark ink.** Judges may print it. White paper, near-black text (`#14140f`),
  secondary text a warm grey (`#4a4945`).
- **One accent:** blue `#2a78d6` for kickers, rules and emphasis. Status colours only for decisions:
  ALLOW `#0ca30c`, STEP UP `#c98500`, REVIEW `#ec835a`, BLOCK `#d03b3b`. Every decision chip carries an
  icon and a text label, so colour is never the only carrier of meaning.
- **Typography:** system sans. Slide titles ~34px with tight tracking (`-0.02em`); body 15–16px;
  small print 13px. Big numbers get tabular figures and tight tracking. Never centre body text.
- **Layout:** a small uppercase kicker above each title, generous margins, two- or three-column card
  grids rather than long bullet lists. Cards have a light panel background (`#f7f7f4`) and a hairline
  border, not shadows.
- **Restraint:** no gradients behind text, no stock photography, no icon soup, no decorative shapes.
  The only images are the two screenshots.
- **Tables** are for data with more than three columns; cards are for ideas. Do not force prose into
  a table.
- Every slide has a footer: project name on the left, slide number on the right.

## Also useful

The repository already contains a working version of this deck built with plain HTML and CSS at
`deck/build.py` (run `python deck/build.py --pdf`). Read it for the exact wording and structure if you
want to match or improve it rather than start from scratch.
