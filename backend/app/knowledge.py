"""Fraud typology knowledge base + semantic retrieval.

The retrieved typology is what turns a score into an explanation an analyst can
act on: not just "0.91 risk" but "this matches a device-farm ring, here is the
control that stops it". Vectors live in the database (a `vector` column under
pgvector in production; a JSON array on SQLite here) and the embedder is a local
TF-IDF+SVD model so the prototype runs with no network and no per-query cost.
Swapping in Bedrock Titan / Voyage embeddings means replacing `_fit_embedder`
and `embed` only - storage and retrieval are unchanged.
"""
import json
import os

import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline

from . import config
from .db import Typology

EMBEDDER_PATH = os.getenv("EMBEDDER_PATH", "./sentinel_embedder.joblib")
EMBED_DIM = 48

KNOWLEDGE_BASE = [
    {"title": "Device farm / application ring",
     "body": "A single handset or emulator submits applications under many different applicant "
             "names within hours. Sessions are short, fields are pasted, VPN or proxy hides the "
             "true network. Losses cluster because the same operator repeats the pattern.",
     "controls": "Bind the device fingerprint, block the device across the portfolio, force "
                 "video KYC for every application sharing the fingerprint."},
    {"title": "Synthetic identity",
     "body": "A fabricated applicant built from a real PAN or mobile plus invented attributes. "
             "The credit file is thin or newly created, the email domain is freshly registered, "
             "and the requested amount is far above what the declared income supports.",
     "controls": "Bureau thin-file check, PAN-name-DOB triangulation, income verification via "
                 "bank statement analysis before disbursal."},
    {"title": "Bust-out fraud",
     "body": "An aged account in good standing suddenly maximises exposure across products, "
             "often at night and from a new geography, then defaults with no intent to repay.",
     "controls": "Velocity limits on credit-line increases, step-up authentication on sudden "
                 "exposure jumps, cross-product exposure ceiling."},
    {"title": "Bot / scripted application",
     "body": "Automation fills the form: superhuman typing speed, no corrections, no tab "
             "switching, several paste events, submission in under a minute.",
     "controls": "Behavioural biometrics challenge, invisible CAPTCHA, rate limits per device "
                 "and per IP subnet."},
    {"title": "Account takeover at application",
     "body": "A genuine customer profile is used from an unrecognised device and geography, "
             "usually after a credential leak. Prior behaviour and current session disagree.",
     "controls": "Out-of-band OTP to the registered number, device re-binding flow, cooling "
                 "period on beneficiary and contact changes."},
    {"title": "Income document forgery",
     "body": "Declared income is inconsistent with spending, employer or bank-statement "
             "patterns. Loan-to-income sits far outside the portfolio distribution.",
     "controls": "Account aggregator pull, payslip tamper detection, employer registry match."},
    {"title": "Mule account funnelling",
     "body": "Multiple approved loans disburse into a small set of destination accounts, or the "
             "same beneficiary details recur across unrelated applicants.",
     "controls": "Beneficiary graph analysis before disbursal, payout hold on repeat "
                 "beneficiaries, penny-drop name match."},
    {"title": "Geo-velocity impossibility",
     "body": "The applicant's network geography is inconsistent with the declared address or "
             "with their own previous session minutes earlier - typical of proxy rotation.",
     "controls": "Impossible-travel rule, residential-proxy detection, address proofing."},
    {"title": "First-party friendly fraud",
     "body": "A genuine borrower applies with the intent never to repay, often stacking loans "
             "across several lenders in a short window before any of them report to the bureau.",
     "controls": "Real-time bureau enquiry-velocity check, loan stacking consortium feed, "
                 "reduced first-cycle limit."},
    {"title": "Promo and subvention abuse",
     "body": "Many thin applications from one household or device chase an origination "
             "incentive, each individually small and individually plausible.",
     "controls": "Household de-duplication, incentive cap per device and per address, "
                 "post-disbursal cohort review."},
]


def _fit_embedder(corpus: list[str]):
    embedder = make_pipeline(
        TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1),
        TruncatedSVD(n_components=min(EMBED_DIM, max(len(corpus) - 1, 2)), random_state=7),
    )
    embedder.fit(corpus)
    joblib.dump(embedder, EMBEDDER_PATH)
    return embedder


_EMBEDDER = None


def _load_embedder(corpus: list[str]):
    """Held in process memory - reloading the embedder per request dominated the
    scoring latency budget."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            _EMBEDDER = joblib.load(EMBEDDER_PATH)
        except (FileNotFoundError, ModuleNotFoundError):
            _EMBEDDER = _fit_embedder(corpus)
    return _EMBEDDER


def embed(embedder, texts: list[str]) -> np.ndarray:
    vectors = np.asarray(embedder.transform(texts), dtype=float)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-9, None)


def seed(session) -> None:
    """Idempotent: build the KB and its vectors once, reuse them afterwards."""
    corpus = [f"{d['title']}. {d['body']} {d['controls']}" for d in KNOWLEDGE_BASE]
    global _EMBEDDER
    _EMBEDDER = embedder = _fit_embedder(corpus)
    vectors = embed(embedder, corpus)
    session.query(Typology).delete()
    for doc, vector in zip(KNOWLEDGE_BASE, vectors):
        session.add(Typology(title=doc["title"], body=doc["body"],
                             controls=doc["controls"], embedding=json.dumps(vector.tolist())))


def ensure_seeded(session) -> None:
    if session.query(Typology).count() != len(KNOWLEDGE_BASE) or not os.path.exists(EMBEDDER_PATH):
        seed(session)


def search(session, query: str, k: int = 2) -> list[dict]:
    """Cosine top-k over the stored vectors.

    ponytail: the KB is ~10 docs, so an in-Python dot product is exact and instant.
    Move to `ORDER BY embedding <=> :q LIMIT k` on pgvector once the KB is large.
    """
    rows = session.query(Typology).all()
    if not rows:
        return []
    corpus = [f"{r.title}. {r.body} {r.controls}" for r in rows]
    embedder = _load_embedder(corpus)
    q = embed(embedder, [query])[0]
    matrix = np.array([r.vector() for r in rows], dtype=float)
    if matrix.shape[1] != q.shape[0]:  # embedder changed under us - rebuild
        seed(session)
        session.commit()
        return search(session, query, k)
    scores = matrix @ q
    order = np.argsort(-scores)[:k]
    return [{"title": rows[i].title, "controls": rows[i].controls,
             "similarity": round(float(scores[i]), 3)} for i in order]


def query_text(features: dict, rule_hits: list[dict]) -> str:
    """Turn a scored application into the sentence we search the KB with."""
    parts = [hit["detail"] for hit in rule_hits[:4]]
    if features.get("amount_to_income", 0) > 1.0:
        parts.append("loan requested is far above declared annual income")
    if features.get("account_age_days", 9999) < 30:
        parts.append("newly created customer account with thin file")
    if features.get("is_emulator") or features.get("is_vpn_or_proxy"):
        parts.append("emulator or VPN hides the true device and network")
    if features.get("geo_mismatch"):
        parts.append("network geography differs from declared address")
    return " ".join(parts) or "ordinary digital lending application with no anomalies"
