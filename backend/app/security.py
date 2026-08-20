"""Auth, rate limiting and PII handling - the trust boundary of the service."""
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)
_bearer = HTTPBearer(auto_error=False)

# A missing secret must not silently become a well-known default: generate an
# ephemeral one so dev works and every restart invalidates old tokens.
JWT_SECRET = config.JWT_SECRET or secrets.token_urlsafe(32)
SECRET_IS_EPHEMERAL = not config.JWT_SECRET


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(dk.hex(), dk_hex)


def issue_token(email: str, role: str) -> str:
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_TTL_MIN),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


_hits: dict[str, deque] = defaultdict(deque)


async def rate_limit(request: Request):
    """Fixed-window-free sliding counter per client IP.
    ponytail: in-process only; move to Redis/API-gateway when running >1 replica."""
    now = time.monotonic()
    key = request.client.host if request.client else "unknown"
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MIN:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
    q.append(now)


# --- PII -----------------------------------------------------------------
# Masked at the edge, before anything is persisted or shown to a model.
_PATTERNS = [
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), lambda m: m.group()[:3] + "XXXXX" + m.group()[-1]),  # PAN
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), lambda m: "XXXX XXXX " + m.group()[-4:]),            # Aadhaar
    (re.compile(r"\b(?:\+91[- ]?)?[6-9]\d{9}\b"), lambda m: "XXXXXX" + m.group()[-4:]),             # mobile
    (re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"), lambda m: m.group()[0] + "***@" + m.group().split("@")[1]),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), lambda m: "**** **** **** " + re.sub(r"\D", "", m.group())[-4:]),
]


def redact(text: str) -> str:
    """Mask identifiers in free text. Applied to every payload leaving for the LLM."""
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj
