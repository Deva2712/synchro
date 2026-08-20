"""Feature engineering: raw application event -> the vector both models consume.

Order matters - it is the model's input contract, so it lives in one place.
"""
from datetime import datetime, timedelta, timezone

FEATURE_NAMES = [
    "amount_to_income",
    "log_amount",
    "session_duration_s",
    "typing_speed_cps",
    "paste_events",
    "form_corrections",
    "tab_switches",
    "device_velocity_24h",
    "ip_velocity_24h",
    "device_distinct_names",
    "is_emulator",
    "is_vpn_or_proxy",
    "geo_mismatch",
    "night_application",
    "email_domain_age_days",
    "account_age_days",
    "prior_defaults",
]

# Plain-English labels used in analyst-facing explanations.
FEATURE_LABELS = {
    "amount_to_income": "loan amount vs declared income",
    "log_amount": "loan size",
    "session_duration_s": "time spent on the application form",
    "typing_speed_cps": "typing speed",
    "paste_events": "pasted fields (vs typed)",
    "form_corrections": "form corrections",
    "tab_switches": "tab switching during the form",
    "device_velocity_24h": "applications from this device in 24h",
    "ip_velocity_24h": "applications from this IP in 24h",
    "device_distinct_names": "distinct applicant names on this device",
    "is_emulator": "emulator / rooted device",
    "is_vpn_or_proxy": "VPN or proxy in use",
    "geo_mismatch": "IP geography vs declared address",
    "night_application": "applied between 01:00-05:00",
    "email_domain_age_days": "age of the email domain",
    "account_age_days": "age of the customer account",
    "prior_defaults": "prior defaults on record",
}


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_features(event: dict, velocity: dict | None = None) -> dict:
    """Deterministic transform. Same event + same velocity always yields the same vector."""
    velocity = velocity or {}
    applicant = event.get("applicant", {})
    loan = event.get("loan", {})
    device = event.get("device", {})
    session = event.get("session", {})
    history = event.get("history", {})

    income = max(_num(applicant.get("monthly_income"), 1.0), 1.0)
    amount = max(_num(loan.get("amount")), 0.0)
    hour = int(_num(session.get("hour_of_day"), datetime.now(timezone.utc).hour))

    return {
        "amount_to_income": round(amount / (income * 12), 4),
        "log_amount": round((amount + 1) ** 0.5 / 100, 4),
        "session_duration_s": _num(session.get("duration_s")),
        "typing_speed_cps": _num(session.get("typing_speed_cps")),
        "paste_events": _num(session.get("paste_events")),
        "form_corrections": _num(session.get("form_corrections")),
        "tab_switches": _num(session.get("tab_switches")),
        "device_velocity_24h": _num(velocity.get("device_velocity_24h")),
        "ip_velocity_24h": _num(velocity.get("ip_velocity_24h")),
        "device_distinct_names": _num(velocity.get("device_distinct_names")),
        "is_emulator": float(bool(device.get("is_emulator"))),
        "is_vpn_or_proxy": float(bool(device.get("vpn_or_proxy"))),
        "geo_mismatch": float(
            bool(device.get("ip_state")) and device.get("ip_state") != applicant.get("state")
        ),
        "night_application": float(1 <= hour <= 5),
        "email_domain_age_days": _num(history.get("email_domain_age_days"), 3650),
        "account_age_days": _num(history.get("account_age_days"), 3650),
        "prior_defaults": _num(history.get("prior_defaults")),
    }


def to_vector(features: dict) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]


def window_start(hours: int = 24):
    return datetime.now(timezone.utc) - timedelta(hours=hours)
