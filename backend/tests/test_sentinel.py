"""Test coverage for the parts that would silently cost money if they broke:
the decision policy, the rule pack, PII masking, auth, and the scoring endpoint.
"""
import os
import random

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sentinel.db")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "test-admin-pass-123")
os.environ.setdefault("SEED_ANALYST_PASSWORD", "test-analyst-pass-123")
os.environ.setdefault("MODEL_PATH", "./test_sentinel_model.joblib")
os.environ.setdefault("EMBEDDER_PATH", "./test_sentinel_embedder.joblib")
os.environ.setdefault("LLM_ENABLED", "off")

import pytest
from fastapi.testclient import TestClient

from backend.app import decision, rules, security
from backend.app.features import FEATURE_NAMES, build_features
from backend.app.main import app
from backend.data.generate import make_event


@pytest.fixture(scope="module")
def client():
    for path in ("./test_sentinel.db", "./test_sentinel_model.joblib", "./test_sentinel_embedder.joblib"):
        if os.path.exists(path):
            os.remove(path)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def auth(client):
    response = client.post("/v1/auth/login", json={"email": "analyst@sentinel.local",
                                                   "password": "test-analyst-pass-123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def event_payload(fraud=False, kind=None, seed=3):
    event, _ = make_event(random.Random(seed), fraud=fraud, kind=kind)
    return {k: v for k, v in event.items() if not k.startswith("_")}


# --- policy --------------------------------------------------------------
def test_decision_thresholds_are_monotonic():
    assert decision.decide(0.05, False) == "ALLOW"
    assert decision.decide(0.40, False) == "STEP_UP"
    assert decision.decide(0.70, False) == "REVIEW"
    assert decision.decide(0.95, False) == "BLOCK"


def test_hard_block_overrides_a_low_score():
    assert decision.decide(0.01, True) == "BLOCK"


# --- rules ---------------------------------------------------------------
def test_device_farm_rule_fires_and_is_explained():
    features = build_features(event_payload(), {"device_distinct_names": 5,
                                                "device_velocity_24h": 5, "ip_velocity_24h": 6})
    score, hits, hard = rules.evaluate(features, {})
    codes = [h["code"] for h in hits]
    assert "DEVICE_FARM" in codes and score > 0.9 and not hard
    assert "5 different applicant names" in hits[0]["detail"]


def test_clean_application_trips_no_high_weight_rule():
    features = build_features(event_payload(), {"device_distinct_names": 1})
    score, hits, hard = rules.evaluate(features, {})
    assert not hard and all(h["weight"] < 0.6 for h in hits), hits


def test_confirmed_fraud_device_hard_blocks():
    features = build_features(event_payload(), {})
    _, _, hard = rules.evaluate(features, {"_denylisted": True})
    assert hard


# --- features ------------------------------------------------------------
def test_feature_vector_is_complete_and_deterministic():
    payload = event_payload()
    first = build_features(payload, {})
    assert set(first) == set(FEATURE_NAMES)
    assert first == build_features(payload, {})


# --- PII -----------------------------------------------------------------
@pytest.mark.parametrize("raw,must_not_contain", [
    ("PAN ABCDE1234F on file", "ABCDE1234F"),
    ("call 9876543210 now", "9876543210"),
    ("aadhaar 1234 5678 9012", "5678"),
    ("mail rahul.sharma@example.com", "rahul.sharma"),
])
def test_redaction_removes_identifiers(raw, must_not_contain):
    assert must_not_contain not in security.redact(raw)


def test_redaction_walks_nested_payloads():
    masked = security.redact_obj({"a": {"b": ["PAN ABCDE1234F"]}})
    assert "ABCDE1234F" not in masked["a"]["b"][0]


# --- auth ----------------------------------------------------------------
def test_scoring_requires_a_token(client):
    assert client.post("/v1/applications/score", json=event_payload()).status_code == 401


def test_bad_password_is_rejected(client):
    assert client.post("/v1/auth/login",
                       json={"email": "analyst@sentinel.local",
                             "password": "wrong-password-value"}).status_code == 401


def test_analyst_cannot_retrain(client, auth):
    assert client.post("/v1/model/retrain", headers=auth).status_code == 403


# --- API ------------------------------------------------------------------
def test_score_endpoint_returns_an_explained_decision(client, auth):
    response = client.post("/v1/applications/score", json=event_payload(), headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in decision.DECISIONS
    assert 0.0 <= body["risk_score"] <= 1.0
    assert body["typologies"], "every decision must retrieve a typology for context"


def test_invalid_input_is_rejected_at_the_edge(client, auth):
    payload = event_payload()
    payload["device"]["ip"] = "999.1.1.1"
    assert client.post("/v1/applications/score", json=payload, headers=auth).status_code == 422
    payload = event_payload()
    payload["loan"]["amount"] = -5000
    assert client.post("/v1/applications/score", json=payload, headers=auth).status_code == 422
    payload = event_payload()
    payload["surprise"] = "unexpected field"
    assert client.post("/v1/applications/score", json=payload, headers=auth).status_code == 422


def test_ring_traffic_escalates_to_review_or_block(client, auth):
    """Six applications from one device under six names must not all sail through."""
    device = {"device_id": "dev-ring-001", "ip": "49.10.10.10"}
    decisions = []
    for seed in range(6):
        payload = event_payload(fraud=True, kind="ring", seed=100 + seed)
        payload["device"] |= device
        payload["applicant"]["name"] = f"Ring Member {seed}"
        decisions.append(client.post("/v1/applications/score", json=payload,
                                     headers=auth).json()["decision"])
    assert decisions[-1] in ("REVIEW", "BLOCK"), decisions


def test_feedback_denylists_the_device_for_the_next_application(client, auth):
    payload = event_payload(fraud=True, kind="bot", seed=55)
    payload["device"] |= {"device_id": "dev-denylist-1", "ip": "49.20.20.20"}
    first = client.post("/v1/applications/score", json=payload, headers=auth).json()
    client.post(f"/v1/applications/{first['application_id']}/feedback",
                json={"label": 1, "note": "confirmed mule"}, headers=auth).raise_for_status()

    payload2 = event_payload(seed=56)  # a clean-looking application from the same device
    payload2["device"] |= {"device_id": "dev-denylist-1", "ip": "49.20.20.20"}
    second = client.post("/v1/applications/score", json=payload2, headers=auth).json()
    assert second["decision"] == "BLOCK"
    assert any(r["code"] == "CONFIRMED_FRAUD_DEVICE" for r in second["reasons"])


def test_metrics_report_the_live_window(client, auth):
    body = client.get("/v1/metrics", headers=auth).json()
    assert body["total_applications"] > 0
    assert body["p95_latency_ms"] < 500, "the synchronous path must stay real time"
    assert set(body["by_decision"]) <= set(decision.DECISIONS)


def test_retrain_reports_promotion_and_never_regresses_silently(client):
    admin = client.post("/v1/auth/login", json={"email": "admin@sentinel.local",
                                                "password": "test-admin-pass-123"})
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    body = client.post("/v1/model/retrain", headers=headers).json()
    assert body["labelled_cases"] >= 1, "the earlier feedback test must have produced a label"
    assert "promoted" in body and isinstance(body["promoted"], bool)
    if body["promoted"]:
        assert body["new_metrics"]["roc_auc"] >= body["previous_metrics"]["roc_auc"] - body["promotion_tolerance"]
