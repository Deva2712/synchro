"""Decision orchestration - the one place a risk decision is made.

Order: features -> rules -> models -> policy -> (async) explanation.
Everything before the explanation is deterministic and takes single-digit
milliseconds, which is what lets this sit inline in the application flow.
"""
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select

from . import config, knowledge, llm, rules
from .db import Application, velocity_counts
from .features import build_features, window_start
from .security import redact_obj

DECISIONS = ("ALLOW", "STEP_UP", "REVIEW", "BLOCK")
ACTION_TEXT = {
    "ALLOW": "Proceed with the application",
    "STEP_UP": "Challenge with OTP / liveness before proceeding",
    "REVIEW": "Hold for manual fraud review",
    "BLOCK": "Block and raise a fraud case",
}


def decide(risk: float, hard_block: bool) -> str:
    if hard_block or risk >= config.T_BLOCK:
        return "BLOCK"
    if risk >= config.T_REVIEW:
        return "REVIEW"
    if risk >= config.T_STEP_UP:
        return "STEP_UP"
    return "ALLOW"


def _denylisted(session, device_id: str, ip: str) -> bool:
    """Analyst-confirmed fraud on this device or IP - the response loop closing."""
    return session.scalar(
        select(Application.id).where(
            Application.label == 1,
            or_(Application.device_id == device_id, Application.ip == ip),
        ).limit(1)
    ) is not None


def _reasons(rule_hits: list[dict], contributions: list[dict]) -> list[dict]:
    """One ranked evidence list, so the UI and the audit log tell the same story."""
    out = [{"type": "rule", "code": h["code"], "weight": h["weight"], "detail": h["detail"]}
           for h in rule_hits]
    out += [{"type": "model", "code": c["feature"], "weight": round(abs(c["contribution"]) / 10, 3),
             "detail": f"{c['label'].capitalize()} {c['direction']} "
                       f"(contribution {c['contribution']:+.2f} log-odds)"}
            for c in contributions if c["contribution"] > 0]
    return sorted(out, key=lambda r: -r["weight"])[:6]


def score_application(session, event: dict, model) -> Application:
    started = time.perf_counter()
    event = redact_obj(event)  # mask at the trust boundary: nothing unmasked is ever stored

    device = event.get("device", {})
    device_id, ip = device.get("device_id", "unknown"), device.get("ip", "0.0.0.0")

    velocity = velocity_counts(session, device_id, ip, window_start(24))
    features = build_features(event, velocity)
    event["_denylisted"] = _denylisted(session, device_id, ip)

    rule_score, rule_hits, hard_block = rules.evaluate(features, event)
    scores = model.score(features)

    risk = min(round(config.W_ML * scores["ml_score"]
                     + config.W_ANOMALY * scores["anomaly_score"]
                     + config.W_RULES * rule_score, 4), 1.0)
    decision = decide(risk, hard_block)
    typologies = knowledge.search(session, knowledge.query_text(features, rule_hits), k=2)

    record = Application(
        id=event.get("application_id") or f"APP-{uuid.uuid4().hex[:10].upper()}",
        created_at=datetime.now(timezone.utc),
        applicant_name=event.get("applicant", {}).get("name"),
        amount=float(event.get("loan", {}).get("amount") or 0),
        device_id=device_id, ip=ip,
        event=event, features=features,
        ml_score=scores["ml_score"], anomaly_score=scores["anomaly_score"],
        rule_score=rule_score, risk_score=risk, decision=decision,
        reasons=_reasons(rule_hits, scores["contributions"]),
        typologies=typologies,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    record.narrative = None
    session.add(record)
    session.flush()
    record._case = {                      # handed to the explanation step, not persisted
        "decision": decision, "risk_score": risk, "ml_score": scores["ml_score"],
        "anomaly_score": scores["anomaly_score"], "amount": record.amount,
        "rule_hits": rule_hits, "contributions": scores["contributions"],
        "typologies": typologies,
    }
    return record


def explain_case(session, application_id: str, case: dict) -> dict:
    """Runs after the response is returned - a slow or missing LLM cannot delay a decision."""
    narrative = llm.explain(case)
    record = session.get(Application, application_id)
    if record is not None:
        record.narrative = narrative
        session.commit()
    return narrative
