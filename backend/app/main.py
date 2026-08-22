"""Sentinel - real-time fraud detection API for digital lending.

API-first: every capability in the product is a documented endpoint here
(OpenAPI at /docs). The React console is only one consumer; the loan
origination system is the other.
"""
import logging
import os
import pathlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from . import config, decision, knowledge, llm, model as model_layer, security
from .db import Application, User, init_db, session_scope
from .schemas import (
    ApplicationEvent, DecisionResponse, FeedbackRequest, LoginRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("sentinel")

STATE: dict = {}


def _seed_users(session):
    """Bootstrap accounts come from the environment. If none is supplied we mint a
    random password and print it once - a deployment is never left with a known default."""
    if session.query(User).count():
        return
    for email_key, pwd_key, role, default_email in (
        ("SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD", "admin", "admin@sentinel.local"),
        ("SEED_ANALYST_EMAIL", "SEED_ANALYST_PASSWORD", "analyst", "analyst@sentinel.local"),
    ):
        email = os.getenv(email_key, default_email)
        password = os.getenv(pwd_key) or secrets.token_urlsafe(12)
        if not os.getenv(pwd_key):
            log.warning("No %s set - generated password for %s: %s", pwd_key, email, password)
        session.add(User(email=email, password_hash=security.hash_password(password), role=role))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as session:
        _seed_users(session)
        knowledge.ensure_seeded(session)
    STATE["model"] = model_layer.load_or_train()
    log.info("Model ready: %s", STATE["model"].metrics)
    if security.SECRET_IS_EPHEMERAL:
        log.warning("JWT_SECRET not set - using an ephemeral secret; tokens die on restart.")
    yield


app = FastAPI(
    title="Sentinel Fraud Detection API",
    version="1.0.0",
    description="Real-time fraud detection and prevention for digital lending.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,          # explicit origins, never "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- auth ----------------------------------------------------------------
@app.post("/v1/auth/login", tags=["auth"])
async def login(body: LoginRequest, _=Depends(security.rate_limit)):
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == body.email))
        # constant-time compare inside verify_password; identical error either way
        if user is None or not security.verify_password(body.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        return {"access_token": security.issue_token(user.email, user.role),
                "token_type": "bearer", "role": user.role,
                "expires_in_min": config.JWT_TTL_MIN}


@app.get("/v1/me", tags=["auth"])
async def me(user: dict = Depends(security.current_user)):
    return {"email": user["sub"], "role": user["role"]}


# --- scoring -------------------------------------------------------------
def _explain_later(application_id: str, case: dict):
    with session_scope() as session:
        decision.explain_case(session, application_id, case)


@app.post("/v1/applications/score", response_model=DecisionResponse, tags=["scoring"])
async def score(event: ApplicationEvent, background: BackgroundTasks,
                user: dict = Depends(security.current_user),
                _=Depends(security.rate_limit)):
    """Score one application. Returns the decision synchronously; the natural-language
    explanation is generated afterwards so LLM latency never sits in the customer path."""
    with session_scope() as session:
        record = decision.score_application(session, event.model_dump(), STATE["model"])
        case, application_id = record._case, record.id
        payload = DecisionResponse(
            application_id=application_id,
            decision=record.decision,
            action=decision.ACTION_TEXT[record.decision],
            risk_score=record.risk_score, ml_score=record.ml_score,
            anomaly_score=record.anomaly_score, rule_score=record.rule_score,
            reasons=record.reasons, typologies=record.typologies,
            latency_ms=record.latency_ms, explanation_pending=True,
        )
    background.add_task(_explain_later, application_id, case)
    return payload


# --- case management -----------------------------------------------------
def _summary(record: Application) -> dict:
    return {
        "application_id": record.id,
        "created_at": record.created_at.isoformat(),
        "applicant_name": record.applicant_name,
        "amount": record.amount,
        "device_id": record.device_id,
        "risk_score": record.risk_score,
        "decision": record.decision,
        "top_reason": (record.reasons or [{}])[0].get("detail", ""),
        "label": record.label,
        "latency_ms": record.latency_ms,
    }


@app.get("/v1/applications", tags=["cases"])
async def list_applications(user: dict = Depends(security.current_user),
                            decision_filter: str | None = Query(None, alias="decision"),
                            limit: int = Query(50, ge=1, le=200)):
    with session_scope() as session:
        query = select(Application).order_by(Application.created_at.desc()).limit(limit)
        if decision_filter:
            query = query.where(Application.decision == decision_filter.upper())
        return [_summary(r) for r in session.scalars(query)]


@app.get("/v1/applications/{application_id}", tags=["cases"])
async def get_application(application_id: str, user: dict = Depends(security.current_user)):
    with session_scope() as session:
        record = session.get(Application, application_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown application")
        return _summary(record) | {
            "features": record.features, "reasons": record.reasons,
            "typologies": record.typologies, "narrative": record.narrative,
            "ml_score": record.ml_score, "anomaly_score": record.anomaly_score,
            "rule_score": record.rule_score, "event": record.event,
            "reviewed_by": record.reviewed_by,
        }


@app.post("/v1/applications/{application_id}/feedback", tags=["cases"])
async def feedback(application_id: str, body: FeedbackRequest,
                   user: dict = Depends(security.current_user)):
    """Analyst verdict. This is the input to the learning loop: confirmed fraud both
    trains the next model and denylists the device for every future application."""
    with session_scope() as session:
        record = session.get(Application, application_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown application")
        record.label = body.label
        record.reviewed_by = user["sub"]
        return {"application_id": application_id, "label": record.label,
                "reviewed_by": record.reviewed_by}


# --- model lifecycle -----------------------------------------------------
@app.get("/v1/model/info", tags=["model"])
async def model_info(user: dict = Depends(security.current_user)):
    current = STATE["model"]
    return {"trained_at": current.trained_at, "metrics": current.metrics,
            "features": current.feature_names,
            "weights": {"ml": config.W_ML, "anomaly": config.W_ANOMALY, "rules": config.W_RULES},
            "thresholds": {"step_up": config.T_STEP_UP, "review": config.T_REVIEW,
                           "block": config.T_BLOCK},
            "llm": {"backend": config.LLM_BACKEND, "model": config.LLM_MODEL,
                    "live": llm.enabled()}}


@app.post("/v1/model/retrain", tags=["model"])
async def retrain(user: dict = Depends(security.require_admin)):
    """Self-learning step: fold every analyst-labelled case into a new model.
    Admin-only and fully logged - a model swap is a change to a credit control."""
    with session_scope() as session:
        labelled = [(r.event, int(r.label)) for r in session.scalars(
            select(Application).where(Application.label.isnot(None)))]
    for event, _ in labelled:
        event["_velocity"] = {k: event.get("_velocity", {}).get(k, 0) for k in
                              ("device_velocity_24h", "ip_velocity_24h", "device_distinct_names")}
    previous = STATE["model"].metrics
    fresh = model_layer.train(feedback=labelled)

    # Model governance: a retrain is a change to a live credit control, so a candidate
    # that scores materially worse than the incumbent is not promoted. Thin feedback
    # (a handful of labels) moves ROC-AUC within noise; a real regression does not.
    regression = previous.get("roc_auc", 0) - fresh.metrics["roc_auc"]
    promoted = regression <= model_layer.PROMOTION_TOLERANCE
    if promoted:
        model_layer.save(fresh)
        STATE["model"] = fresh
    log.info("Retrain by %s on %d labelled cases: ROC-AUC %.4f -> %.4f (promoted=%s)",
             user["sub"], len(labelled), previous.get("roc_auc", 0),
             fresh.metrics["roc_auc"], promoted)
    return {"retrained_by": user["sub"], "labelled_cases": len(labelled),
            "previous_metrics": previous, "new_metrics": fresh.metrics,
            "promoted": promoted,
            "promotion_tolerance": model_layer.PROMOTION_TOLERANCE,
            "trained_at": fresh.trained_at if promoted else STATE["model"].trained_at}


# --- operations ----------------------------------------------------------
@app.get("/v1/metrics", tags=["ops"])
async def metrics(user: dict = Depends(security.current_user), hours: int = Query(24, ge=1, le=720)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    with session_scope() as session:
        rows = list(session.scalars(select(Application).where(Application.created_at >= since)))
        by_decision = dict(session.execute(
            select(Application.decision, func.count(Application.id))
            .where(Application.created_at >= since)
            .group_by(Application.decision)).all())
        latencies = sorted(r.latency_ms or 0 for r in rows)
        rule_counts: dict[str, int] = {}
        for record in rows:
            for reason in record.reasons or []:
                if reason["type"] == "rule":
                    rule_counts[reason["code"]] = rule_counts.get(reason["code"], 0) + 1
        total = len(rows) or 1
        return {
            "window_hours": hours,
            "total_applications": len(rows),
            "by_decision": by_decision,
            "frictionless_rate": round(by_decision.get("ALLOW", 0) / total, 4),
            "review_rate": round((by_decision.get("REVIEW", 0) + by_decision.get("BLOCK", 0)) / total, 4),
            "avg_risk": round(sum(r.risk_score for r in rows) / total, 4),
            "p50_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
            "p95_latency_ms": latencies[int(len(latencies) * 0.95)] if latencies else 0,
            "top_rules": sorted(rule_counts.items(), key=lambda kv: -kv[1])[:5],
            "confirmed_fraud": sum(1 for r in rows if r.label == 1),
            "confirmed_legit": sum(1 for r in rows if r.label == 0),
            "model_metrics": STATE["model"].metrics,
        }


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "model_trained_at": STATE.get("model").trained_at if STATE.get("model") else None}


# The built React console, if it is present (it is, in the Docker image). Mounted
# last so every API route above takes precedence over the static files.
_console = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _console.is_dir():
    app.mount("/", StaticFiles(directory=_console, html=True), name="console")
    log.info("Serving the console from %s", _console)
