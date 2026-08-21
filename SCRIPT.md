# Demo video script

Target length **6 minutes**. A 3-minute short version is at the bottom.
Everything in *italics* is what you say; everything in `code` is what you do.

---

## Before you press record

```bash
cd ~/Desktop/Synchrome

# 1. clean slate so the numbers on screen are tidy
docker compose up -d                 # PostgreSQL + pgvector
rm -f sentinel_model.joblib          # forces a fresh, honest model train
docker compose exec db psql -U sentinel -d sentinel -c "TRUNCATE applications;"

# 2. three terminals
make api                             # terminal 1 - wait for "Model ready"
make web                             # terminal 2
                                     # terminal 3 stays free for `make demo`
```

Then: open `localhost:5173`, sign in as **admin@sentinel.local**, sign out again, and leave the login
screen showing. Close Slack/mail, hide bookmarks, set the browser to 100 % zoom.

**Checklist:** terminal font large enough to read · notifications off · microphone working ·
window at 1920×1080.

---

## Scene 1 — What the problem is (0:00 – 0:40)

**Screen:** the login page.

> *"Hi, I'm <name>. My problem statement is real-time fraud detection in digital lending.*
>
> *There are three hard parts to it. Fraud patterns change every few weeks, but writing and shipping
> a new rule takes months. Every genuine customer you wrongly block just walks to another lender, and
> that loss never appears in a fraud report. And the whole decision has to happen while the customer
> is sitting on the screen waiting.*
>
> *So I built Sentinel — it scores an application in about 30 milliseconds, decides one of four
> outcomes, and tells the analyst exactly why."*

---

## Scene 2 — It actually works (0:40 – 1:15)

**Screen:** terminal.

```bash
make test
```

> *"Twenty tests, all passing. They cover the decision thresholds, the rule pack, PII masking,
> authentication and roles — and two of them test behaviour rather than code: a burst of six
> applications from one device must escalate, and once an analyst confirms fraud, the next
> application from that device must be blocked. I'll show you both of those live in a minute."*

**Screen:** browser → `127.0.0.1:8000/docs`.

> *"Everything is an API first. Scoring, the case queue, analyst feedback, retraining, metrics —
> ten endpoints with generated OpenAPI docs. The React console you're about to see is just one
> client; a loan origination system would be another."*

---

## Scene 3 — Live traffic (1:15 – 2:10)

**Screen:** sign in to the console as **admin**, then run in terminal 3:

```bash
make demo
```

> *"This is simulated application traffic hitting the real API — sixty applications, about five a
> second. Every line in that terminal is a real API response with its own decision and latency.*
>
> *The console polls every two seconds, so the queue fills up live.*
>
> *Look at the top row of numbers. Two thirds go straight through with no friction at all. The p95
> decision time is under forty milliseconds, and that includes a hop to a PostgreSQL container —
> this runs inside the application flow, not in a nightly batch."*

**Point at:** the decision mix bar.

> *"Four outcomes, not two. Allow, step-up, review, block. That distinction is the whole answer to
> false positives — suspicion costs the customer an OTP, not their loan."*

---

## Scene 4 — Catching the fraud ring (2:10 – 3:10)

**Screen:** click the **BLOCK** filter.

> *"Now the interesting part. Several of these say the same thing: 'same device used by five
> different applicant names in twenty-four hours.'*
>
> *Individually each of those applications is clean — no emulator, normal typing speed, a reasonable
> loan amount. A rule engine that looks at one application at a time passes every single one of them.*
>
> *What gives the ring away is the pattern across them, and we only see it because device and IP
> velocity are counted at the moment of scoring, straight off the database, not in a batch job that
> runs tonight."*

---

## Scene 5 — Why it decided that (3:10 – 4:20)

**Screen:** click one of those rows to open the case panel. Walk down it slowly.

> *"This is what the analyst gets. First, the score composition — how much came from the machine
> learning model, the anomaly model, and the rules. Nothing is hidden behind a single number.*
>
> *Then the evidence, ranked. The orange ones are rules, in plain English. The blue ones come from
> the model itself: 'typing speed raises risk, contribution plus 2.7 log-odds.' I used logistic
> regression on purpose — because it's linear, each feature's contribution is exact arithmetic, so
> the explanation is the decision itself, not a guess from a separate explainer.*
>
> *Below that, the closest matching fraud typology, found by vector search: device farm slash
> application ring, with the control that actually stops it.*
>
> *And then the AI summary."*

**Point at:** the grey footnote under the AI summary.

> *"Read that line: 'explanation only — the decision above was made by the rules and models, not by
> the language model.' That's the rule I designed around. The LLM is called after the decision is
> already returned, so if it's slow, rate-limited or down, the wording of the case file changes and
> the credit decision doesn't. Right now it's running the deterministic fallback because I have no
> API key configured — and that fallback is part of the product, not a placeholder. One environment
> variable points it at Claude on the Anthropic API or on AWS Bedrock."*

---

## Scene 6 — It learns from the analyst (4:20 – 5:15)

**Screen:** click **Confirm fraud**, then in terminal 3:

```bash
make demo
```

> *"I've just done what an analyst does — confirmed this case as fraud."*

**Screen:** wait for new rows, click the **BLOCK** filter again and open a new case from that device.

> *"And here's the next application from that same device. Blocked, and the first line of evidence is
> 'device or IP previously confirmed as fraud by an analyst.' One click protected the whole portfolio
> from the very next application — no retraining, no deployment."*

**Screen:** click **Retrain from feedback** in the top bar.

> *"The slower half of the loop is retraining. Every labelled case goes back in at twelve times the
> weight of a synthetic sample. But retraining a live credit control is risky, so a new model is only
> promoted if it isn't meaningfully worse than the current one — and the API reports both sets of
> metrics either way. I added that check after watching a single bad label move the score in the
> wrong direction."*

---

## Scene 7 — Security, and closing (5:15 – 6:00)

**Screen:** terminal.

```bash
cat .env.example
```

> *"Quick word on security. Every secret comes from the environment — this template ships blank, the
> real file is git-ignored, and if no JWT secret is set the service generates a random one instead of
> falling back to a default. Passwords are scrypt-hashed. Every endpoint needs a bearer token,
> retraining needs the admin role, inputs are strictly validated, and PAN, Aadhaar, phone and email
> are masked at the trust boundary — before anything is stored or sent to a model."*

**Screen:** back to the console.

> *"So, to summarise: about thirty milliseconds per decision, four graded outcomes instead of a
> yes-no, an explanation for every single one, and a loop that learns from the analyst instantly and
> retrains safely.*
>
> *The code, the README, the architecture diagram and the tests are all on GitHub. Thank you."*

---

## Short version (3 minutes)

Keep scenes **3, 4, 5 and 6**. Compress scene 1 to two sentences, drop scene 2 (mention the 20 tests
while the queue is filling), and end after the retrain click with the summary line.

---

## Things to avoid on camera

- Don't read the slides — the deck is a separate deliverable.
- Don't apologise for the fallback LLM. Say it is the designed failure mode; it is a strength.
- Don't claim it is deployed on AWS. Say it runs in Docker and is built to deploy there.
- Don't zoom around the code. One file tree shot is enough; the repository speaks for itself.
- If a number on screen differs from the deck, say the real one. The deck's model metrics come from a
  held-out test set; the console shows the live demo run.

## If something breaks mid-recording

| Problem | Say this, then fix it |
|---|---|
| Queue is empty | *"Let me push some traffic through."* → `make demo` |
| Retrain button missing | You're signed in as the analyst — sign in as admin |
| Session expired | *"Tokens last an hour."* → sign in again |
| Everything looks stale | Stop, reset with `TRUNCATE applications`, restart the recording |
