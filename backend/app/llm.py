"""AI explanation layer.

Hard rule enforced here: the LLM never decides. The decision is produced by the
rules + models; the model only *explains* it in analyst language and suggests
next steps. That keeps the system deterministic, auditable and safe to run on
regulated credit decisions, and it means an LLM outage degrades the narrative,
never the control.

Backends: Anthropic first-party (default) or the same model on Amazon Bedrock
(LLM_BACKEND=bedrock). Credentials are resolved by the SDK from the environment
or the instance role - never read from, or written to, the codebase.
"""
import logging
import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from . import config
from .security import redact, redact_obj

log = logging.getLogger("sentinel.llm")

SYSTEM_PROMPT = """You are a fraud-analysis assistant for a regulated digital lending platform.

You receive an application that has ALREADY been scored and decided by a deterministic
rules + machine-learning pipeline. Your job is to explain that outcome to a human fraud
analyst, never to change it.

Rules you must follow:
- Base every statement strictly on the evidence provided. Never invent facts, names,
  amounts, or history that is not in the input.
- The input is masked: identifiers appear as XXXX. Never guess the hidden values.
- Do not state or imply that the applicant is guilty. Write in terms of risk indicators
  and what the analyst should verify.
- Never mention or infer protected attributes (religion, caste, gender, ethnicity, age
  as a category, disability). Judge behaviour and transaction facts only.
- If the evidence is weak, say so plainly and recommend release rather than friction.
- Keep the summary under 70 words."""

ACTIONS = ("release", "step_up_authentication", "manual_review", "block_and_report")


class FraudNarrative(BaseModel):
    """Structured output contract - the model cannot return free-form text."""
    summary: str = Field(description="<=70 words explaining the risk indicators to an analyst")
    typology: str = Field(description="Closest matching fraud typology, or 'none apparent'")
    recommended_action: Literal[ACTIONS] = Field(  # type: ignore[valid-type]
        description="Advisory only; the platform decision still governs")
    analyst_checks: list[str] = Field(description="2-4 concrete verification steps")
    confidence: Literal["low", "medium", "high"]


def enabled() -> bool:
    if config.LLM_ENABLED == "off":
        return False
    if config.LLM_ENABLED == "on":
        return True
    if config.LLM_BACKEND == "bedrock":
        return bool(os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")
                    or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"))
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
                or os.path.expanduser("~/.config/anthropic") and
                os.path.isdir(os.path.expanduser("~/.config/anthropic")))


@lru_cache(maxsize=1)
def _client():
    import anthropic
    if config.LLM_BACKEND == "bedrock":
        return anthropic.AnthropicBedrockMantle(aws_region=config.AWS_REGION)
    return anthropic.Anthropic()


def _prompt(case: dict) -> str:
    lines = [
        f"Decision taken by the platform: {case['decision']} (risk score {case['risk_score']:.2f})",
        f"Model probability of fraud: {case['ml_score']:.2f}; novelty/anomaly score: {case['anomaly_score']:.2f}",
        f"Loan requested: {case['amount']:,.0f} INR",
        "",
        "Rules triggered:",
        *([f"- {h['code']}: {h['detail']}" for h in case["rule_hits"]] or ["- none"]),
        "",
        "Top model drivers:",
        *[f"- {c['label']} {c['direction']} (weight {c['contribution']:+.2f})"
          for c in case["contributions"]],
        "",
        "Closest known typologies from the fraud knowledge base:",
        *([f"- {t['title']} (similarity {t['similarity']}) - control: {t['controls']}"
           for t in case["typologies"]] or ["- none"]),
    ]
    return redact("\n".join(lines))


def _fallback(case: dict) -> dict:
    """Deterministic narrative used when the LLM is disabled or unreachable.
    The product never depends on the model being up."""
    drivers = ", ".join(c["label"] for c in case["contributions"][:3]) or "no strong drivers"
    rules = "; ".join(h["detail"] for h in case["rule_hits"][:3]) or "no rules triggered"
    action = {"ALLOW": "release", "STEP_UP": "step_up_authentication",
              "REVIEW": "manual_review", "BLOCK": "block_and_report"}[case["decision"]]
    return {
        "summary": (f"Risk {case['risk_score']:.2f}. {rules}. Main model drivers: {drivers}."),
        "typology": case["typologies"][0]["title"] if case["typologies"] else "none apparent",
        "recommended_action": action,
        "analyst_checks": ["Verify identity documents against the bureau record",
                           "Confirm device ownership with the registered customer",
                           "Check for other applications sharing this device or IP"],
        "confidence": "medium",
        "source": "rule_based_fallback",
    }


def explain(case: dict) -> dict:
    """Return a structured, guardrailed narrative. Never raises - explanation is
    additive, so any failure falls back to the deterministic template."""
    if not enabled():
        return _fallback(case)
    try:
        response = _client().with_options(timeout=config.LLM_TIMEOUT_S, max_retries=1).messages.parse(
            model=config.LLM_MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _prompt(case)}],
            output_format=FraudNarrative,
        )
        parsed = response.parsed_output
        if parsed is None:
            return _fallback(case)
        out = redact_obj(parsed.model_dump())          # output guardrail: mask anything echoed back
        out["summary"] = " ".join(out["summary"].split()[:80])
        out["analyst_checks"] = out["analyst_checks"][:4]
        out["source"] = f"{config.LLM_BACKEND}:{config.LLM_MODEL}"
        return out
    except Exception as exc:                            # noqa: BLE001 - fail open, never block a decision
        log.warning("LLM explanation unavailable (%s); using deterministic fallback", exc)
        out = _fallback(case)
        out["source"] = "rule_based_fallback"
        return out
