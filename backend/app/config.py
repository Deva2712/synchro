"""Runtime configuration. Everything comes from the environment - no secrets in code."""
import os

from dotenv import load_dotenv

load_dotenv()


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# --- storage -------------------------------------------------------------
# sqlite by default so the prototype runs with zero setup; point DATABASE_URL at
# postgresql+psycopg://... (see docker-compose.yml) for the production shape.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
MODEL_PATH = os.getenv("MODEL_PATH", "./sentinel_model.joblib")

# --- security ------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "")  # required outside dev; see security.py
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "60"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))

# --- AI layer ------------------------------------------------------------
# Anthropic first-party by default; set LLM_BACKEND=bedrock to route the same
# calls through Amazon Bedrock (AWS creds resolved by the SDK, never stored here).
LLM_BACKEND = os.getenv("LLM_BACKEND", "anthropic")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-5")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LLM_TIMEOUT_S = _f("LLM_TIMEOUT_S", 20.0)
LLM_ENABLED = os.getenv("LLM_ENABLED", "auto")  # auto | on | off

# --- decision policy -----------------------------------------------------
# Weights and cut-offs are policy, not code. Risk teams tune these per portfolio.
W_ML = _f("W_ML", 0.55)
W_ANOMALY = _f("W_ANOMALY", 0.20)
W_RULES = _f("W_RULES", 0.25)
T_STEP_UP = _f("T_STEP_UP", 0.35)
T_REVIEW = _f("T_REVIEW", 0.60)
T_BLOCK = _f("T_BLOCK", 0.85)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
