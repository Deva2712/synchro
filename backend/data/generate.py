"""Synthetic digital-lending traffic.

Real application data cannot leave the bank, so the prototype learns from
generated traffic that encodes four documented fraud archetypes plus realistic
legitimate noise (VPN users, night owls, hesitant form-fillers) so the model is
forced to separate genuine risk from mere unusualness.
"""
import random

STATES = ["MH", "KA", "TN", "DL", "WB", "GJ", "UP", "TS"]
PURPOSES = ["personal", "consumer_durable", "education", "medical", "travel", "business"]
FIRST = ["Aarav", "Diya", "Rohan", "Meera", "Kabir", "Sana", "Vikram", "Nisha", "Arjun", "Priya"]
LAST = ["Sharma", "Iyer", "Khan", "Patel", "Nair", "Bose", "Gupta", "Reddy", "Menon", "Das"]
ARCHETYPES = ["ring", "synthetic_identity", "bust_out", "bot"]


def _name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _base(rng):
    state = rng.choice(STATES)
    income = rng.choice([25_000, 40_000, 60_000, 85_000, 120_000, 180_000])
    return {
        "applicant": {
            "name": _name(rng),
            "state": state,
            "monthly_income": income,
            "email": f"user{rng.randint(1000, 9999)}@mail.com",
            "phone": f"9{rng.randint(100000000, 999999999)}",
        },
        "loan": {
            # a genuine tail of over-asking customers, so leverage alone is not proof of fraud
            "amount": round(income * rng.uniform(1.0, 6.0 if rng.random() < 0.88 else 13.0), -3),
            "tenure_months": rng.choice([12, 24, 36, 48]),
            "purpose": rng.choice(PURPOSES),
        },
        "device": {
            "device_id": f"dev-{rng.randint(100000, 999999)}",
            "ip": f"49.{rng.randint(1, 250)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}",
            "ip_state": state,
            "os": rng.choice(["android", "ios", "web"]),
            "is_emulator": False,
            "vpn_or_proxy": rng.random() < 0.06,
        },
        "session": {
            "duration_s": rng.randint(180, 900),
            "typing_speed_cps": round(rng.uniform(2.0, 6.5), 2),
            "paste_events": rng.choice([0, 0, 0, 1, 1, 2]),
            "form_corrections": rng.randint(1, 9),
            "tab_switches": rng.randint(0, 5),
            "hour_of_day": rng.choice([9, 10, 11, 13, 14, 16, 18, 20, 21, 22, 2]),
        },
        "history": {
            "email_domain_age_days": rng.choice([1200, 2500, 4000, 6000]),
            "account_age_days": rng.randint(45, 2500),
            "prior_defaults": 0 if rng.random() < 0.94 else 1,
        },
        # shared handsets and agent-assisted onboarding create legitimate velocity
        "_velocity": ({"device_velocity_24h": rng.randint(2, 5), "ip_velocity_24h": rng.randint(3, 9),
                       "device_distinct_names": rng.randint(2, 4)} if rng.random() < 0.07 else
                      {"device_velocity_24h": rng.choice([0, 0, 0, 1]),
                       "ip_velocity_24h": rng.choice([0, 0, 1, 2]),
                       "device_distinct_names": rng.choice([1, 1, 1, 2])}),
    }


def _apply_archetype(event, kind, rng):
    a, d, s, h, v = (event["applicant"], event["device"], event["session"],
                     event["history"], event["_velocity"])
    if kind == "ring":                       # one device farm, many stolen identities
        v.update(device_velocity_24h=rng.randint(3, 9), ip_velocity_24h=rng.randint(4, 14),
                 device_distinct_names=rng.randint(3, 8))
        d.update(is_emulator=rng.random() < 0.7, vpn_or_proxy=True,
                 ip_state=rng.choice([x for x in STATES if x != a["state"]]))
        s.update(duration_s=rng.randint(40, 150), paste_events=rng.randint(3, 8),
                 typing_speed_cps=round(rng.uniform(9, 22), 2), form_corrections=rng.randint(0, 1))
        h["email_domain_age_days"] = rng.randint(2, 45)
    elif kind == "synthetic_identity":       # fabricated but internally consistent profile
        h.update(account_age_days=rng.randint(1, 12), email_domain_age_days=rng.randint(3, 60),
                 prior_defaults=0)
        event["loan"]["amount"] = round(a["monthly_income"] * rng.uniform(7, 14), -3)
        s.update(duration_s=rng.randint(120, 400), paste_events=rng.randint(2, 5),
                 form_corrections=rng.randint(0, 2))
    elif kind == "bust_out":                 # aged account suddenly maximising exposure
        h.update(account_age_days=rng.randint(200, 900), prior_defaults=rng.choice([0, 1, 1]))
        event["loan"]["amount"] = round(a["monthly_income"] * rng.uniform(8, 15), -3)
        s.update(hour_of_day=rng.choice([1, 2, 3, 4]), tab_switches=rng.randint(6, 14))
        d.update(ip_state=rng.choice([x for x in STATES if x != a["state"]]),
                 vpn_or_proxy=rng.random() < 0.5)
        v["ip_velocity_24h"] = rng.randint(2, 6)
    elif kind == "bot":                      # scripted submission, no human hesitation
        s.update(duration_s=rng.randint(15, 60), typing_speed_cps=round(rng.uniform(14, 40), 2),
                 paste_events=rng.randint(4, 10), form_corrections=0, tab_switches=0)
        d.update(is_emulator=True, vpn_or_proxy=rng.random() < 0.8)
        v.update(device_velocity_24h=rng.randint(2, 6), ip_velocity_24h=rng.randint(3, 10))
    return event


def _stealth(base: dict, event: dict, rng: random.Random) -> dict:
    """Sophisticated fraud does not trip every signal at once.

    Restore a random subset of tell-tale fields to normal values, leaving only a
    partial fingerprint. These are the cases rules miss and the model must earn.
    """
    for section in ("device", "session", "history", "_velocity"):
        for key, value in base[section].items():
            if rng.random() < 0.55:
                event[section][key] = value
    return event


def make_event(rng: random.Random, fraud: bool = False, kind: str | None = None) -> tuple[dict, int]:
    event = _base(rng)
    base_snapshot = {k: dict(v) for k, v in event.items() if isinstance(v, dict)}
    if not fraud:
        # legitimate-but-unusual traffic: the false-positive pressure test
        if rng.random() < 0.18:
            event["session"]["hour_of_day"] = rng.choice([2, 3])
        if rng.random() < 0.12:
            event["device"]["ip_state"] = rng.choice(STATES)
        if rng.random() < 0.10:
            event["session"]["paste_events"] = rng.randint(3, 6)
        return event, 0
    event = _apply_archetype(event, kind or rng.choice(ARCHETYPES), rng)
    if rng.random() < 0.40:
        event = _stealth(base_snapshot, event, rng)
    return event, 1


def dataset(n: int = 8000, fraud_rate: float = 0.07, seed: int = 7):
    """Returns [(event, label)] - callers build features so training and serving share code."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        event, label = make_event(rng, fraud=rng.random() < fraud_rate)
        if rng.random() < 0.015:  # label noise: real fraud tags are never perfect
            label = 1 - label
        rows.append((event, label))
    return rows
