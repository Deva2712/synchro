"""Persistence layer. SQLAlchemy Core keeps the same code working on SQLite and PostgreSQL."""
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Column, DateTime, Float, Integer, String, Text, create_engine, func, select,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

Base = declarative_base()
_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="analyst")  # analyst | admin


class Application(Base):
    """One credit application scored in real time, plus its audit trail."""
    __tablename__ = "applications"
    id = Column(String(40), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    applicant_name = Column(String(120))
    amount = Column(Float)
    device_id = Column(String(80), index=True)
    ip = Column(String(45), index=True)
    event = Column(JSON)          # raw request, PII already masked
    features = Column(JSON)       # engineered features fed to the models
    ml_score = Column(Float)
    anomaly_score = Column(Float)
    rule_score = Column(Float)
    risk_score = Column(Float, index=True)
    decision = Column(String(16), index=True)
    reasons = Column(JSON)        # ranked, human-readable evidence
    typologies = Column(JSON)     # vector-search hits
    narrative = Column(JSON)      # LLM explanation (advisory only)
    latency_ms = Column(Float)
    label = Column(Integer)       # analyst feedback: 1 fraud, 0 legit, None unreviewed
    reviewed_by = Column(String(120))


class Typology(Base):
    """Fraud typology knowledge base + its embedding (pgvector in production)."""
    __tablename__ = "typologies"
    id = Column(Integer, primary_key=True)
    title = Column(String(160))
    body = Column(Text)
    controls = Column(Text)
    embedding = Column(Text)  # JSON float array; swap for vector(384) under pgvector

    def vector(self):
        return json.loads(self.embedding)


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    Base.metadata.create_all(engine)


def velocity_counts(s, device_id: str, ip: str, since):
    """Real-time velocity straight off the write path - no batch job, no feature store."""
    dev = s.scalar(select(func.count(Application.id)).where(
        Application.device_id == device_id, Application.created_at >= since)) or 0
    ip_n = s.scalar(select(func.count(Application.id)).where(
        Application.ip == ip, Application.created_at >= since)) or 0
    names = s.scalar(select(func.count(func.distinct(Application.applicant_name))).where(
        Application.device_id == device_id, Application.created_at >= since)) or 0
    return {"device_velocity_24h": dev, "ip_velocity_24h": ip_n, "device_distinct_names": names}
