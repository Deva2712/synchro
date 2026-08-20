"""Deterministic rule pack.

Rules are the fast, auditable, regulator-explainable half of the system. They also
give the ML layer a cold-start floor on day one. Each hit carries evidence text so
the analyst never sees a bare score.
"""

# (code, predicate, weight, human explanation). Weight 1.0 == hard block.
RULES = [
    ("DEVICE_FARM", lambda f, e: f["device_distinct_names"] >= 3,
     0.90, "Same device used by {device_distinct_names:.0f} different applicant names in 24h"),
    ("IP_VELOCITY", lambda f, e: f["ip_velocity_24h"] >= 5,
     0.70, "{ip_velocity_24h:.0f} applications from this IP in the last 24h"),
    ("DEVICE_VELOCITY", lambda f, e: f["device_velocity_24h"] >= 3,
     0.60, "{device_velocity_24h:.0f} applications from this device in the last 24h"),
    ("CLOAKED_DEVICE", lambda f, e: f["is_emulator"] and f["is_vpn_or_proxy"],
     0.65, "Emulator/rooted device behind a VPN or proxy"),
    ("SCRIPTED_ENTRY", lambda f, e: f["paste_events"] >= 4 and f["typing_speed_cps"] >= 12,
     0.60, "Form filled by paste/automation ({paste_events:.0f} pastes at {typing_speed_cps:.0f} chars/s)"),
    ("FRESH_IDENTITY", lambda f, e: f["email_domain_age_days"] < 30,
     0.50, "Email domain registered {email_domain_age_days:.0f} days ago"),
    ("THIN_FILE_LARGE_ASK", lambda f, e: f["account_age_days"] < 7 and f["amount_to_income"] > 0.5,
     0.55, "Account {account_age_days:.0f} days old asking for {amount_to_income:.1f}x annual income"),
    ("SPEED_RUN", lambda f, e: f["session_duration_s"] < 45 and f["amount_to_income"] > 0.3,
     0.45, "High-value form completed in {session_duration_s:.0f}s"),
    ("NIGHT_GEO_MISMATCH", lambda f, e: f["night_application"] and f["geo_mismatch"],
     0.35, "Night-time application from a state that differs from the declared address"),
    ("PRIOR_DEFAULTS", lambda f, e: f["prior_defaults"] >= 1,
     0.40, "{prior_defaults:.0f} prior default(s) on record"),
    ("CONFIRMED_FRAUD_DEVICE", lambda f, e: bool(e.get("_denylisted")),
     1.00, "Device or IP previously confirmed as fraud by an analyst"),
]


def evaluate(features: dict, event: dict) -> tuple[float, list[dict], bool]:
    """Return (rule_score, hits, hard_block).

    Scores combine with noisy-OR: several weak signals add up, none can exceed 1.
    """
    hits, combined, hard_block = [], 1.0, False
    for code, predicate, weight, template in RULES:
        try:
            fired = bool(predicate(features, event))
        except KeyError:
            fired = False
        if not fired:
            continue
        hits.append({"code": code, "weight": weight, "detail": template.format(**features)})
        combined *= (1 - weight)
        hard_block = hard_block or weight >= 1.0
    hits.sort(key=lambda h: -h["weight"])
    return round(min(1 - combined, 0.99), 4), hits, hard_block
