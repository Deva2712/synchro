"""API contracts. Validation happens here, at the edge, before anything reaches the models."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are rejected, not ignored


class Applicant(Strict):
    name: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=3)
    monthly_income: float = Field(gt=0, le=100_000_000)
    email: str = Field(max_length=160)
    phone: str = Field(max_length=20)


class Loan(Strict):
    amount: float = Field(gt=0, le=100_000_000)
    tenure_months: int = Field(ge=1, le=120)
    purpose: str = Field(max_length=40)


class Device(Strict):
    device_id: str = Field(min_length=3, max_length=80)
    ip: str = Field(max_length=45)
    ip_state: str = Field(default="", max_length=3)
    os: Literal["android", "ios", "web"] = "web"
    is_emulator: bool = False
    vpn_or_proxy: bool = False

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str) -> str:
        if not IP_RE.match(v) or any(int(p) > 255 for p in v.split(".")):
            raise ValueError("ip must be a dotted-quad IPv4 address")
        return v


class SessionSignals(Strict):
    duration_s: float = Field(ge=0, le=86_400)
    typing_speed_cps: float = Field(ge=0, le=200)
    paste_events: int = Field(ge=0, le=500)
    form_corrections: int = Field(ge=0, le=500)
    tab_switches: int = Field(ge=0, le=500)
    hour_of_day: int = Field(ge=0, le=23)


class History(Strict):
    email_domain_age_days: int = Field(ge=0, le=20_000)
    account_age_days: int = Field(ge=0, le=20_000)
    prior_defaults: int = Field(ge=0, le=50)


class ApplicationEvent(Strict):
    application_id: str | None = Field(default=None, max_length=40)
    applicant: Applicant
    loan: Loan
    device: Device
    session: SessionSignals
    history: History


class DecisionResponse(BaseModel):
    application_id: str
    decision: Literal["ALLOW", "STEP_UP", "REVIEW", "BLOCK"]
    action: str
    risk_score: float
    ml_score: float
    anomaly_score: float
    rule_score: float
    reasons: list[dict]
    typologies: list[dict]
    latency_ms: float
    explanation_pending: bool


class LoginRequest(Strict):
    email: str = Field(max_length=160)
    password: str = Field(min_length=8, max_length=200)


class FeedbackRequest(Strict):
    label: Literal[0, 1]
    note: str = Field(default="", max_length=500)
