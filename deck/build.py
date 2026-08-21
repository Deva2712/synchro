"""Builds the submission deck (deck/slides.html) and prints it to PDF via headless Chrome.

    python deck/build.py            # writes deck/slides.html
    python deck/build.py --pdf      # also writes deck/Sentinel.pdf
"""
import base64
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent

# Screenshots are inlined as data URIs so the deck is a single self-contained file.
IMAGES = {
    path.name: "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    for path in sorted((HERE / "assets").glob("*.png"))
}

def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


# Fill these in from the command line:
#   python deck/build.py --pdf --author "Your Name" --roll "21XX1234"
AUTHOR = _arg("--author", "<Your name>")
ROLL = _arg("--roll", "<Roll number>")

CSS = """
@page{size:1280px 720px;margin:0}
:root{
  --ink:#14140f; --ink-2:#4a4945; --muted:#8a8880; --line:#e3e2dc; --paper:#ffffff;
  --panel:#f7f7f4; --accent:#2a78d6; --allow:#0ca30c; --step:#c98500; --review:#ec835a;
  --block:#d03b3b; --violet:#4a3aa7;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#5a5a55;font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Inter,sans-serif;
     color:var(--ink);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.slide{width:1280px;height:720px;background:var(--paper);padding:52px 68px;position:relative;
       overflow:hidden;page-break-after:always;display:flex;flex-direction:column}
.slide+.slide{margin-top:18px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
        font-weight:700;margin-bottom:10px}
h1{font-size:40px;line-height:1.1;letter-spacing:-.02em;font-weight:700}
h2{font-size:34px;line-height:1.15;letter-spacing:-.02em;font-weight:700;margin-bottom:6px}
h3{font-size:15px;font-weight:700;letter-spacing:-.01em}
.sub{font-size:17px;color:var(--ink-2);line-height:1.45;margin-top:10px;max-width:1000px}
.body{flex:1;margin-top:24px;padding-bottom:34px;font-size:16px;color:var(--ink-2);line-height:1.5}
.foot{position:absolute;left:68px;right:68px;bottom:24px;display:flex;justify-content:space-between;
      font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding-top:10px}
.cols{display:grid;gap:18px}
.c2{grid-template-columns:1fr 1fr}.c3{grid-template-columns:repeat(3,1fr)}.c4{grid-template-columns:repeat(4,1fr)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.card h3{margin-bottom:6px}
.card p{font-size:14px;line-height:1.45;color:var(--ink-2)}
.num{font-size:34px;font-weight:700;letter-spacing:-.02em;color:var(--ink);display:block}
.num.sm{font-size:26px}
.lbl{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}
ul{list-style:none;display:grid;gap:12px}
li{padding-left:20px;position:relative;font-size:16px;line-height:1.45}
li::before{content:"";position:absolute;left:0;top:9px;width:7px;height:7px;border-radius:2px;background:var(--accent)}
li b{color:var(--ink)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
   font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:8px 10px;border-bottom:1px solid var(--line);color:var(--ink-2)}
td b{color:var(--ink)}
.right{text-align:right}
.pill{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:999px;font-size:11px;
      font-weight:700;letter-spacing:.04em;border:1px solid;white-space:nowrap}
.p-allow{color:var(--allow);border-color:var(--allow);background:#0ca30c14}
.p-step{color:var(--step);border-color:var(--step);background:#c9850014}
.p-review{color:#b4562c;border-color:var(--review);background:#ec835a1f}
.p-block{color:var(--block);border-color:var(--block);background:#d03b3b14}
.title-slide{background:#14140f;color:#fff;justify-content:center}
.title-slide h1{font-size:56px;color:#fff}
.title-slide .sub{color:#c3c2b7;font-size:19px}
.title-slide .foot{color:#8a8880;border-color:#33332f}
.mark{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#3987e5,#1baf7a);margin-bottom:22px}
.band{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--panel);
      display:grid;grid-template-columns:132px 1fr;gap:14px;align-items:center}
.band .band-label{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600;line-height:1.3}
.band .boxes{display:flex;gap:8px;flex-wrap:wrap}
.box{background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 11px;font-size:13px;flex:1;min-width:110px}
.box b{display:block;font-size:13px;color:var(--ink)}
.box span{font-size:11px;color:var(--muted)}
.box.accent{border-color:var(--accent);box-shadow:inset 0 0 0 1px #2a78d626}
.arrow{text-align:center;color:var(--muted);font-size:12px;margin:3px 0;letter-spacing:.3em}
.callout{border-left:3px solid var(--accent);background:#2a78d60d;padding:12px 16px;border-radius:0 8px 8px 0;font-size:15px}
.shot{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#14140f;display:flex;
      align-items:flex-start;justify-content:center}
.shot img{width:100%;display:block}
.formula{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:15px;line-height:1.9;
         background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 22px}
.tag{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
     border:1px solid var(--line);border-radius:4px;padding:1px 6px;margin-right:6px}
.small{font-size:13px;color:var(--muted);line-height:1.45}
@media print{
  body{background:#fff}
  .slide+.slide{margin-top:0}
  .slide{height:718px;box-shadow:none}
}
"""


def slide(kicker, title, body, n, note=""):
    return f"""<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2>{title}</h2>
  {f'<p class="sub">{note}</p>' if note else ''}
  <div class="body">{body}</div>
  <div class="foot"><span>Sentinel · Real-Time Fraud Detection for Digital Lending</span><span>{n}</span></div>
</section>"""


SLIDES = []

# 1 - title
SLIDES.append(f"""<section class="slide title-slide">
  <div class="mark"></div>
  <h1>Sentinel</h1>
  <p class="sub">Real-time fraud detection and prevention in digital lending<br>
  A working prototype: rules + machine learning + behavioural signals, with an LLM used only to explain the decision.</p>
  <p class="sub" style="margin-top:34px;font-size:15px">{AUTHOR} &middot; Roll number {ROLL}<br>
  FastAPI &middot; React &middot; PostgreSQL / pgvector &middot; Claude (Anthropic API or AWS Bedrock)</p>
  <div class="foot"><span>Synchrony Hackathon submission</span><span>1</span></div>
</section>""")

# 2 - problem
SLIDES.append(slide("The problem", "Why rule-only fraud systems struggle", """
<div class="cols c2">
  <div class="card"><h3>Fraud changes faster than rules</h3><p>Fraud patterns change every few weeks. Writing and releasing a new rule takes much longer than that.</p></div>
  <div class="card"><h3>False positives cost real customers</h3><p>If a genuine customer gets blocked, they simply apply somewhere else. This loss never shows up in a fraud report.</p></div>
  <div class="card"><h3>There is very little time</h3><p>The decision has to happen while the customer is waiting on the screen. A few hundred milliseconds is already too slow.</p></div>
  <div class="card"><h3>A score alone is not useful</h3><p>An analyst cannot do much with "risk = 0.87". They need to know <i>why</i> before they can act on it.</p></div>
</div>
<div class="callout" style="margin-top:18px">So the real requirement is: decide in milliseconds, keep learning without a new release, avoid blocking good customers, and explain every decision.</div>
""", 2))

# 3 - insights
SLIDES.append(slide("What I learned while building", "Four things that shaped the design", """
<ul>
  <li><b>Behaviour is harder to fake than documents.</b> A fraudster can buy a stolen PAN, but typing speed, pasting, corrections and how long someone spends on the form are much harder to imitate.</li>
  <li><b>Velocity is the strongest signal, and it is cheap.</b> "How many different applicant names used this device today" catches a fraud ring by its 4th application &mdash; but only if you count it at the moment of scoring, not in a nightly job.</li>
  <li><b>Rules and ML are better together.</b> Rules work on day one and explain themselves. The ML model adapts. An anomaly model catches patterns that nobody has labelled yet.</li>
  <li><b>The output should be an explanation, not a number.</b> Evidence, matching fraud type, and what to check next &mdash; so the analyst can decide quickly.</li>
</ul>
""", 3))

# 4 - solution
SLIDES.append(slide("What I built", "One fast decision with four possible outcomes", """
<div class="cols c4" style="margin-bottom:20px">
  <div class="card"><span class="pill p-allow">&#10003; ALLOW</span><p style="margin-top:10px">Application continues normally. Two thirds of the demo traffic.</p></div>
  <div class="card"><span class="pill p-step">! STEP UP</span><p style="margin-top:10px">Ask for OTP or liveness check. Extra friction, not a rejection.</p></div>
  <div class="card"><span class="pill p-review">&#8981; REVIEW</span><p style="margin-top:10px">Held for a fraud analyst, with the case already prepared.</p></div>
  <div class="card"><span class="pill p-block">&#10005; BLOCK</span><p style="margin-top:10px">Blocked and raised as a fraud case.</p></div>
</div>
<div class="cols c3">
  <div class="card"><span class="lbl">Decision time (p95)</span><span class="num">22 ms</span><p>Only rules and models are in this path. The LLM is called afterwards.</p></div>
  <div class="card"><span class="lbl">Model accuracy (ROC-AUC)</span><span class="num">0.939</span><p>82% of fraud caught at the review threshold, with a 3.9% false-positive rate.</p></div>
  <div class="card"><span class="lbl">Learning loop</span><span class="num sm">Instant + retrain</span><p>An analyst marking fraud blocks that device immediately, and the case is added to the training data.</p></div>
</div>
""", 4))

# 5 - architecture
SLIDES.append(slide("Architecture", "Five layers, one decision path", """
<div style="display:grid;gap:0">
  <div class="band"><div class="band-label">Frontend</div><div class="boxes">
    <div class="box"><b>Loan application app</b><span>web / android / ios</span></div>
    <div class="box"><b>Analyst console</b><span>React + Vite</span></div>
    <div class="box"><b>Any other API client</b><span>OpenAPI contract</span></div>
  </div></div>
  <div class="arrow">&#9660;</div>
  <div class="band"><div class="band-label">Security layer</div><div class="boxes">
    <div class="box"><b>JWT login</b><span>scrypt passwords, roles</span></div>
    <div class="box"><b>Input validation</b><span>unknown fields rejected</span></div>
    <div class="box"><b>Rate limiting</b><span>per client</span></div>
    <div class="box"><b>PII masking</b><span>before saving or prompting</span></div>
  </div></div>
  <div class="arrow">&#9660;</div>
  <div class="band"><div class="band-label">Decision engine<br>about 20 ms</div><div class="boxes">
    <div class="box accent"><b>17 features</b><span>behaviour, device, velocity</span></div>
    <div class="box accent"><b>Rule pack</b><span>11 rules</span></div>
    <div class="box accent"><b>Logistic regression</b><span>gives probability + reasons</span></div>
    <div class="box accent"><b>Isolation forest</b><span>finds unusual patterns</span></div>
    <div class="box accent"><b>Policy</b><span>weights + thresholds</span></div>
  </div></div>
  <div class="arrow">&#9660;&nbsp;&nbsp;decision is returned here&nbsp;&nbsp;&middot;&nbsp;&nbsp;explanation continues in the background</div>
  <div class="band"><div class="band-label">AI layer</div><div class="boxes">
    <div class="box"><b>Fraud typology KB</b><span>vector / semantic search</span></div>
    <div class="box"><b>Claude</b><span>Anthropic API or AWS Bedrock</span></div>
    <div class="box"><b>Guardrails</b><span>masked input, fixed output format</span></div>
  </div></div>
  <div class="arrow">&#9660;</div>
  <div class="band"><div class="band-label">Database</div><div class="boxes">
    <div class="box"><b>PostgreSQL</b><span>applications, users, velocity counts</span></div>
    <div class="box"><b>pgvector</b><span>typology embeddings</span></div>
    <div class="box"><b>Model files</b><span>saved with their metrics</span></div>
  </div></div>
</div>
<p class="small" style="margin-top:12px">The analyst's verdict goes back into the database: the device is denylisted right away, and the case is used the next time the model is trained.</p>
""", 5))

# 6 - decision engine
SLIDES.append(slide("How the score is calculated", "Simple enough to check by hand", """
<div class="cols c2">
  <div>
    <div class="formula">risk = <b>0.55</b> &times; ML model probability<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ <b>0.20</b> &times; anomaly score<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+ <b>0.25</b> &times; rule score</div>
    <table style="margin-top:16px">
      <tr><td><span class="pill p-block">BLOCK</span></td><td>risk &ge; 0.85, or a hard-block rule fires</td></tr>
      <tr><td><span class="pill p-review">REVIEW</span></td><td>risk &ge; 0.60</td></tr>
      <tr><td><span class="pill p-step">STEP UP</span></td><td>risk &ge; 0.35</td></tr>
      <tr><td><span class="pill p-allow">ALLOW</span></td><td>below that</td></tr>
    </table>
  </div>
  <div>
    <div class="card"><h3>Weights and thresholds are config, not code</h3>
      <p>They are read from environment variables, so a risk team can retune them without changing code or redeploying.</p></div>
    <div class="card" style="margin-top:14px"><h3>Rules combine with noisy-OR</h3>
      <p>Several weak rules add up to real suspicion, but they can never reach certainty on their own. Only a hard-block rule &mdash; for example a device an analyst already confirmed as fraud &mdash; forces a BLOCK.</p></div>
    <div class="card" style="margin-top:14px"><h3>Three models, three jobs</h3>
      <p>Rules catch what we already know and explain it. The classifier learns from labelled fraud. The isolation forest flags applications that simply do not look like normal traffic.</p></div>
  </div>
</div>
""", 6))

# 7 - features
SLIDES.append(slide("The 17 signals", "What the model actually looks at", """
<div class="cols c3">
  <div class="card"><h3>Behaviour on the form</h3>
    <p style="margin-top:8px">Time spent &middot; typing speed &middot; paste events &middot; corrections &middot; tab switches &middot; time of day</p>
    <p class="small" style="margin-top:10px">A real applicant hesitates and corrects mistakes. A script does not. Someone filling their fifth form of the morning types unusually fast.</p></div>
  <div class="card"><h3>Device and network</h3>
    <p style="margin-top:8px">Emulator / rooted device &middot; VPN or proxy &middot; IP location vs declared address</p>
    <p class="small" style="margin-top:10px">Weak on their own &mdash; plenty of genuine users have a VPN &mdash; but useful in combination.</p></div>
  <div class="card"><h3>Velocity (counted live)</h3>
    <p style="margin-top:8px">Applications per device in 24h &middot; per IP in 24h &middot; <b>distinct applicant names per device</b></p>
    <p class="small" style="margin-top:10px">These are counted from the database at scoring time, so there is no batch delay.</p></div>
</div>
<div class="cols c2" style="margin-top:16px">
  <div class="card"><h3>Credit and identity</h3><p>Loan-to-income ratio &middot; loan size &middot; account age &middot; email domain age &middot; prior defaults</p></div>
  <div class="card"><h3>Left out on purpose</h3><p>Name, gender, religion, caste, age group, locality. The model looks at behaviour and transaction facts only.</p></div>
</div>
""", 7))

# 8 - walkthrough
SLIDES.append(slide("Example: catching a fraud ring", "Six applications from the same device", """
<p class="sub" style="margin-top:0">Each of these applications looks fine on its own: no emulator, no VPN, normal typing speed, an old account, and a reasonable loan amount. A per-application rule engine would pass all six. Sentinel notices the pattern across them.</p>
<table style="margin-top:18px">
  <thead><tr><th>#</th><th>Applicant</th><th class="right">Risk</th><th>Decision</th><th>Main reason</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>Rahul Verma</td><td class="right mono">0.15</td><td><span class="pill p-allow">&#10003; ALLOW</span></td><td>IP location differs from address (model, +0.27)</td></tr>
    <tr><td>2</td><td>Sneha Rao</td><td class="right mono">0.10</td><td><span class="pill p-allow">&#10003; ALLOW</span></td><td>Account age (model, +0.26)</td></tr>
    <tr><td>3</td><td>Imran Qureshi</td><td class="right mono">0.21</td><td><span class="pill p-allow">&#10003; ALLOW</span></td><td>IP location differs from address (model, +0.27)</td></tr>
    <tr><td>4</td><td>Anita Joshi</td><td class="right mono">0.44</td><td><span class="pill p-step">! STEP UP</span></td><td><b>Same device used by 3 different applicant names in 24h</b></td></tr>
    <tr><td>5</td><td>Vivek Nanda</td><td class="right mono">0.55</td><td><span class="pill p-step">! STEP UP</span></td><td><b>Same device used by 4 different applicant names in 24h</b></td></tr>
    <tr><td>6</td><td>Farah Sheikh</td><td class="right mono">0.59</td><td><span class="pill p-step">! STEP UP</span></td><td><b>Same device used by 5 different applicant names in 24h</b></td></tr>
  </tbody>
</table>
<div class="callout" style="margin-top:16px">It escalates to <b>extra verification</b> rather than a block, because six clean-looking applications are suspicious but not proof. Once the analyst confirms one of them as fraud, the <b>7th application from that device is blocked straight away</b>, with <span class="mono">CONFIRMED_FRAUD_DEVICE</span> as the first reason.</div>
""", 8))

# 9 - explainability
SLIDES.append(slide("Explainability", "Every decision comes with its reasons", """
<div class="cols c2">
  <div>
    <div class="card"><h3><span class="tag">Rule</span>Plain facts</h3>
      <p style="margin-top:8px">"Same device used by 5 different applicant names in 24h"<br>
      "Form filled by paste/automation (9 pastes at 22 chars/s)"<br>
      "Email domain registered 4 days ago"</p>
      <p class="small" style="margin-top:10px">A rule says what happened, not just a number. This is what an auditor would read.</p></div>
    <div class="card" style="margin-top:14px"><h3><span class="tag">Model</span>Real contributions</h3>
      <p style="margin-top:8px">"Typing speed raises risk (contribution +1.35 log-odds)"</p>
      <p class="small" style="margin-top:10px">I used logistic regression on purpose. Because it is linear, each feature's contribution is simply <span class="mono">coefficient &times; scaled value</span> &mdash; the actual maths of the decision, not an estimate from a separate explainer.</p></div>
  </div>
  <div>
    <div class="card"><h3>Matching a known fraud type</h3>
      <p style="margin-top:8px">The case is turned into a vector and matched against a small knowledge base of fraud typologies:</p>
      <p style="margin-top:10px"><b>Device farm / application ring</b> <span class="small">similarity 0.81</span><br>
      <span class="small">Suggested control: bind the device fingerprint, block the device across the portfolio, force video KYC for applications sharing it.</span></p>
      <p class="small" style="margin-top:10px">So the analyst sees what it looks like <i>and</i> what usually stops it.</p></div>
    <div class="card" style="margin-top:14px"><h3>One list of evidence</h3>
      <p style="margin-top:8px">Rule hits and model reasons are merged into a single ranked list, so the API response, the console and the saved record all show the same explanation.</p></div>
  </div>
</div>
""", 9))

# 10 - AI layer
SLIDES.append(slide("AI layer", "The LLM explains the decision, it does not make it", """
<div class="cols c2">
  <div class="card"><h3>Where it fits</h3>
    <p style="margin-top:8px">The decision is already made and sent back before Claude is called. It then receives the decision, the rules that fired, the model reasons and the matched typologies, and writes a short summary plus the checks the analyst should do.</p>
    <p class="small" style="margin-top:10px">Because of this, if the LLM is slow or unavailable, only the wording of the case file changes. The decision itself is never delayed or altered. If there is no API key, a deterministic template is used instead &mdash; that fallback is part of the product, not a placeholder.</p></div>
  <div class="card"><h3>Guardrails</h3>
    <ul style="gap:8px;margin-top:8px">
      <li style="font-size:14px">PAN, Aadhaar, mobile, email and card numbers are <b>masked before the prompt is built</b></li>
      <li style="font-size:14px">The system prompt tells it not to invent facts, not to guess masked values, and not to use protected attributes</li>
      <li style="font-size:14px"><b>Structured output</b> &mdash; it must return fixed fields and one of four allowed actions</li>
      <li style="font-size:14px">The output is masked again on the way back</li>
      <li style="font-size:14px">20 second timeout and one retry, then fall back &mdash; the call can never crash the decision path</li>
    </ul></div>
</div>
<div class="cols c3" style="margin-top:16px">
  <div class="card"><h3>Works on Bedrock too</h3><p class="small" style="margin-top:6px">One environment variable switches between the Anthropic API and the same model on AWS Bedrock. Credentials come from the SDK / IAM role, never from the code.</p></div>
  <div class="card"><h3>Source is always shown</h3><p class="small" style="margin-top:6px">The console displays which model wrote the summary (<span class="mono">anthropic:claude-opus-5</span> or <span class="mono">rule_based_fallback</span>) and says the decision came from the rules and models.</p></div>
  <div class="card"><h3>Vector search</h3><p class="small" style="margin-top:6px">Typology embeddings are stored next to the data (a <span class="mono">pgvector</span> column in production). Switching to Bedrock Titan embeddings only changes one function.</p></div>
</div>
""", 10))

# 11 - learning loop
SLIDES.append(slide("Learning from analysts", "How the system improves over time", """
<div class="cols c3">
  <div class="card"><span class="lbl">Step 1 &mdash; immediate</span><h3 style="margin-top:8px">Analyst confirms fraud</h3>
    <p style="margin-top:8px">The device and IP are denylisted for the whole portfolio starting from the very next application, using a hard-block rule. No retraining or deployment needed.</p></div>
  <div class="card"><span class="lbl">Step 2 &mdash; on demand</span><h3 style="margin-top:8px">Retrain</h3>
    <p style="margin-top:8px">Every labelled case is added to the training data with <b>12&times; the weight</b> of a synthetic sample. Only an admin can trigger it, it is logged, and the response shows the old and new metrics side by side.</p></div>
  <div class="card"><span class="lbl">Step 3 &mdash; safety check</span><h3 style="margin-top:8px">Promote only if it is not worse</h3>
    <p style="margin-top:8px">If the new model loses more than <b>0.01 ROC-AUC</b> compared to the current one, it is <b>not promoted</b>. The API reports this and the old model keeps running.</p></div>
</div>
<div class="callout" style="margin-top:20px">In testing with a single labelled case, ROC-AUC moved from 0.9386 to 0.9339 &mdash; a drop of 0.005, which is what one sample of noise looks like. That is inside the 0.01 tolerance, so the new model was promoted and the API returned both numbers. A larger drop would have kept the old model serving. I added this check after realising a few bad labels could otherwise quietly make the system worse.</div>
""", 11))

# 12 - results
SLIDES.append(slide("Results", "Measured on test data and on the live demo", """
<div class="cols c2">
  <div>
    <table>
      <thead><tr><th>Model quality (1,600 held-out applications)</th><th class="right">Value</th></tr></thead>
      <tbody>
        <tr><td>ROC-AUC</td><td class="right"><b>0.939</b></td></tr>
        <tr><td>PR-AUC</td><td class="right"><b>0.861</b></td></tr>
        <tr><td>Recall at review threshold</td><td class="right"><b>82.2%</b></td></tr>
        <tr><td>Precision at review threshold</td><td class="right"><b>68.2%</b></td></tr>
        <tr><td>False-positive rate</td><td class="right"><b>3.9%</b></td></tr>
      </tbody>
    </table>
    <p class="small" style="margin-top:12px">The training data is synthetic, but deliberately not easy: <b>40% of the fraud cases only show some of the warning signs</b>, there is 1.5% wrong labelling, and genuine users share devices, use VPNs and apply at 3 a.m. My first version of the generator gave AUC 1.00, which just meant the fake data was too obvious.</p>
  </div>
  <div>
    <table>
      <thead><tr><th>Live demo run (on PostgreSQL)</th><th class="right">Value</th></tr></thead>
      <tbody>
        <tr><td>Applications scored</td><td class="right"><b>60</b></td></tr>
        <tr><td>Decision time p50</td><td class="right"><b>29 ms</b></td></tr>
        <tr><td>Decision time p95</td><td class="right"><b>37 ms</b></td></tr>
        <tr><td>Allowed without friction</td><td class="right"><b>66.7%</b></td></tr>
        <tr><td>Review or blocked</td><td class="right"><b>23.3%</b></td></tr>
        <tr><td>Tests passing</td><td class="right"><b>20 / 20</b></td></tr>
      </tbody>
    </table>
    <p class="small" style="margin-top:10px">The demo stream deliberately contains about 15% fraud plus a device-farm burst, so the
    straight-through rate here is much lower than a real portfolio would see. On SQLite the same run
    decides in 18 ms p50; the extra milliseconds above are the hop to the database container.</p>
    <div class="card" style="margin-top:10px"><h3>About the 68% precision</h3>
      <p class="small" style="margin-top:6px">It means roughly one in three reviewed cases turns out to be genuine. Those cases are only <i>reviewed</i>, not blocked. The thresholds are set so that blocking needs strong evidence, while suspicion only adds an extra check.</p></div>
  </div>
</div>
""", 12))

# 13 - screenshot queue
SLIDES.append(f"""<section class="slide">
  <div class="kicker">The console</div>
  <h2>Live application stream</h2>
  <p class="sub">Every decision as it happens, with the main reason next to it. Each decision has an icon and a label, so colour is never the only way to read it.</p>
  <div class="body" style="margin-top:18px"><div class="shot" style="max-height:430px"><img src="{IMAGES['console-queue.png']}" alt="Sentinel console live queue"></div></div>
  <div class="foot"><span>Sentinel &middot; Real-time fraud detection for digital lending</span><span>13</span></div>
</section>""")

# 14 - screenshot case
SLIDES.append(f"""<section class="slide">
  <div class="kicker">The console</div>
  <h2>The case file an analyst sees</h2>
  <p class="sub">Score breakdown, ranked evidence, the matched fraud type with its control, the AI summary with its source, and the two buttons that feed the learning loop.</p>
  <div class="body" style="margin-top:14px;display:flex;justify-content:center">
    <div class="shot" style="width:760px;max-height:420px"><img src="{IMAGES['console-detail.png']}" alt="Sentinel case detail"></div>
  </div>
  <div class="foot"><span>Sentinel &middot; Real-time fraud detection for digital lending</span><span>14</span></div>
</section>""")

# 15 - security
SLIDES.append(slide("Security and responsible AI", "Handled in the code, not just mentioned", """
<div class="cols c2">
  <div class="card"><h3>Security</h3>
    <ul style="gap:7px;margin-top:8px">
      <li style="font-size:14px"><b>Login</b> JWT tokens (HS256, 60 min), passwords hashed with scrypt and a per-user salt, compared in constant time</li>
      <li style="font-size:14px"><b>Roles</b> analyst vs admin; only an admin can retrain the model, and it is logged</li>
      <li style="font-size:14px"><b>Input validation</b> strict schemas &mdash; number ranges, IPv4 check, fixed options, and unknown fields are rejected</li>
      <li style="font-size:14px"><b>Rate limiting</b> per client on login and scoring</li>
      <li style="font-size:14px"><b>No hardcoded secrets</b> everything comes from environment variables; <span class="mono">.env</span> is git-ignored and <span class="mono">.env.example</span> is blank. With no JWT secret set, a random one is generated instead of using a default</li>
      <li style="font-size:14px"><b>CORS</b> a fixed list of allowed origins, never <span class="mono">*</span></li>
    </ul></div>
  <div class="card"><h3>Responsible AI</h3>
    <ul style="gap:7px;margin-top:8px">
      <li style="font-size:14px"><b>The LLM never decides</b> &mdash; rules and models decide, it only explains</li>
      <li style="font-size:14px"><b>PII is masked</b> before anything is saved or sent to a model</li>
      <li style="font-size:14px"><b>No protected attributes</b> in the features, and the prompt forbids using them</li>
      <li style="font-size:14px"><b>Human in the loop</b> &mdash; suspicion leads to extra verification; only an analyst can confirm fraud</li>
      <li style="font-size:14px"><b>Auditable</b> &mdash; features, scores, rules, evidence and the summary are saved per application, so a decision can be explained later</li>
      <li style="font-size:14px"><b>Source shown</b> &mdash; the console names the model that wrote each summary</li>
    </ul></div>
</div>
""", 15))

# 16 - engineering
SLIDES.append(slide("How the code is organised", "Engineering practices I followed", """
<div class="cols c2">
  <div>
    <div class="card"><h3>API first</h3><p class="small" style="margin-top:6px">Every feature is an API endpoint with auto-generated OpenAPI docs at <span class="mono">/docs</span>. The React console is just one client; a loan origination system could be another. Nothing is only reachable through the UI.</p></div>
    <div class="card" style="margin-top:12px"><h3>One file, one job</h3><p class="small" style="margin-top:6px"><span class="mono">features &middot; rules &middot; model &middot; knowledge &middot; llm &middot; decision &middot; security &middot; schemas &middot; db &middot; config</span>. The decision is assembled in one place, and the feature order is defined in one place because the model depends on it.</p></div>
    <div class="card" style="margin-top:12px"><h3>Configuration, not constants</h3><p class="small" style="margin-top:6px">Weights, thresholds, model name, rate limits, database URL and LLM backend all come from the environment. The same code runs on SQLite locally and PostgreSQL + pgvector in the cloud.</p></div>
  </div>
  <div>
    <div class="card"><h3>20 tests</h3>
      <p class="small" style="margin-top:6px">Decision thresholds, rules and their wording, PII masking, login and roles, and input validation (bad IP, negative amount, unknown field). Two of them test the behaviour that matters most:</p>
      <p class="small" style="margin-top:8px">&#9656; six applications from one device <b>must</b> escalate by the last one<br>
      &#9656; after fraud is confirmed, the next clean-looking application from that device <b>must</b> be blocked</p></div>
    <div class="card" style="margin-top:12px"><h3>Easy to run</h3>
      <p class="small mono" style="margin-top:6px">make setup &middot; make api &middot; make web &middot; make demo &middot; make test</p>
      <p class="small" style="margin-top:6px">The first start trains the model and loads the knowledge base automatically. No cloud account or API key is needed to try it &mdash; the AI layer falls back to its offline path.</p></div>
  </div>
</div>
""", 16))

# 17 - limits
SLIDES.append(slide("What is kept simple for now", "Known limitations and how I would fix them", """
<table>
  <thead><tr><th>Simplification</th><th>Why it is okay now</th><th>What to do later</th></tr></thead>
  <tbody>
    <tr><td><b>Vector search runs in Python</b></td><td>The knowledge base has about 10 documents, so a direct cosine calculation is instant</td><td>Move to <span class="mono">pgvector</span> ordering once the KB grows</td></tr>
    <tr><td><b>Local TF-IDF embeddings</b></td><td>Works offline, costs nothing, and is deterministic</td><td>Replace one function with Bedrock Titan or Voyage embeddings</td></tr>
    <tr><td><b>Rate limiting is in memory</b></td><td>Correct for a single API instance</td><td>Use Redis or the API gateway when running more than one</td></tr>
    <tr><td><b>Training data is synthetic</b></td><td>Real lending data is not available to a student project</td><td>Use real labelled history &mdash; the feedback loop is already built</td></tr>
    <tr><td><b>SQLite by default</b></td><td>Anyone can run the project with no setup</td><td>Already supported: set <span class="mono">DATABASE_URL</span>, docker-compose file included</td></tr>
    <tr><td><b>Console refreshes every 2 s</b></td><td>The real-time part is the 22 ms decision, not the dashboard</td><td>Use server-sent events if many analysts use it at once</td></tr>
  </tbody>
</table>
<div class="callout" style="margin-top:18px">Next steps I would work on: linking fraud rings by shared bank accounts and addresses (not just devices), checking loan stacking across lenders, and running a new model in shadow mode before promoting it.</div>
""", 17))

# 18 - summary
SLIDES.append(slide("Summary", "What this prototype shows", """
<div class="cols c2">
  <div class="card"><h3>Against the problem statement</h3>
    <ul style="gap:8px;margin-top:8px">
      <li style="font-size:14px"><b>Real time</b> &mdash; 22 ms p95, fast enough to run inside the application flow</li>
      <li style="font-size:14px"><b>Self-learning</b> &mdash; analyst verdicts block devices instantly and retrain the model, with a safety check before promotion</li>
      <li style="font-size:14px"><b>Fewer false positives</b> &mdash; four outcomes, so suspicion costs an OTP instead of a customer</li>
      <li style="font-size:14px"><b>New fraud patterns</b> &mdash; an anomaly model that does not need labels</li>
      <li style="font-size:14px"><b>Customer trust</b> &mdash; PII masked, no protected attributes, every decision explainable</li>
    </ul></div>
  <div class="card"><h3>How to run it</h3>
    <p class="small mono" style="margin-top:8px">cp .env.example .env<br>make setup<br>make api&nbsp;&nbsp;&nbsp;# port 8000, docs at /docs<br>make web&nbsp;&nbsp;&nbsp;# port 5173, analyst console<br>make demo&nbsp;&nbsp;# simulated traffic with a fraud ring<br>make test&nbsp;&nbsp;# 20 tests</p>
    <p class="small" style="margin-top:14px">The recorded demo shows traffic arriving live, a fraud ring escalating application by application, the case file with its evidence, confirming fraud, and the next application from that device getting blocked.</p></div>
</div>
<p class="sub" style="margin-top:24px">Thank you. Happy to explain any part of the code in more detail.</p>
""", 18))

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Sentinel — Real-Time Fraud Detection in Digital Lending</title>
<style>{CSS}</style></head><body>
{''.join(SLIDES)}
</body></html>"""

(HERE / "slides.html").write_text(HTML)
print(f"wrote {HERE / 'slides.html'} ({len(HTML) // 1024} KB, {len(SLIDES)} slides)")

if "--pdf" in sys.argv:
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    out = HERE / "Sentinel.pdf"
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", str(HERE / "slides.html")], check=True,
                   capture_output=True)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
