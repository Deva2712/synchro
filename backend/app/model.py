"""The learning layer: a supervised scorer, an unsupervised novelty detector, and
the plumbing to retrain both from analyst feedback.

Why two models: logistic regression is calibrated and linear, so every score
decomposes into per-feature contributions an analyst (or a regulator) can read.
Isolation Forest sees no labels at all, so it still fires on fraud vectors that
have never been labelled - the "adapts to new patterns" half of the brief.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from . import config
from .features import FEATURE_LABELS, FEATURE_NAMES, build_features, to_vector

BASE_SAMPLES = 8000
FEEDBACK_WEIGHT = 12.0  # one analyst-confirmed case is worth many synthetic ones
# A candidate model may not be promoted if it loses more ROC-AUC than this against
# the incumbent - retraining a live credit control is not allowed to regress it.
PROMOTION_TOLERANCE = 0.01


@dataclass
class ScoredModel:
    scaler: StandardScaler
    clf: LogisticRegression
    forest: IsolationForest
    anomaly_lo: float
    anomaly_hi: float
    metrics: dict = field(default_factory=dict)
    trained_at: str = ""
    feature_names: list = field(default_factory=lambda: list(FEATURE_NAMES))

    # -- inference --------------------------------------------------------
    def score(self, features: dict) -> dict:
        x = np.array([to_vector(features)], dtype=float)
        z = self.scaler.transform(x)
        prob = float(self.clf.predict_proba(z)[0, 1])
        raw = float(-self.forest.score_samples(z)[0])
        spread = max(self.anomaly_hi - self.anomaly_lo, 1e-9)
        anomaly = float(np.clip((raw - self.anomaly_lo) / spread, 0.0, 1.0))
        return {"ml_score": round(prob, 4), "anomaly_score": round(anomaly, 4),
                "contributions": self._contributions(z[0])}

    def _contributions(self, z_row: np.ndarray, top_k: int = 4) -> list[dict]:
        """Exact per-feature log-odds contribution - not a post-hoc approximation."""
        parts = self.clf.coef_[0] * z_row
        order = np.argsort(-np.abs(parts))[:top_k]
        return [{
            "feature": FEATURE_NAMES[i],
            "label": FEATURE_LABELS[FEATURE_NAMES[i]],
            "contribution": round(float(parts[i]), 4),
            "direction": "raises risk" if parts[i] > 0 else "lowers risk",
        } for i in order if abs(parts[i]) > 1e-6]


def _matrix(rows):
    return np.array([to_vector(build_features(e, e.get("_velocity"))) for e, _ in rows], dtype=float), \
           np.array([y for _, y in rows], dtype=int)


def train(feedback: list[tuple[dict, int]] | None = None, seed: int = 7) -> ScoredModel:
    """Fit on synthetic base traffic plus any analyst-labelled cases."""
    from ..data.generate import dataset  # local import keeps the training data optional at runtime

    rows = dataset(BASE_SAMPLES, seed=seed)
    rng = random.Random(seed)
    rng.shuffle(rows)
    split = int(len(rows) * 0.8)
    train_rows, test_rows = rows[:split], rows[split:]

    X, y = _matrix(train_rows)
    weights = np.ones(len(y))
    if feedback:
        Xf, yf = _matrix(feedback)
        X, y = np.vstack([X, Xf]), np.concatenate([y, yf])
        weights = np.concatenate([weights, np.full(len(yf), FEEDBACK_WEIGHT)])

    scaler = StandardScaler().fit(X)
    Z = scaler.transform(X)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Z, y, sample_weight=weights)
    forest = IsolationForest(n_estimators=200, contamination=0.07,
                             random_state=seed).fit(Z[y == 0])

    raw = -forest.score_samples(Z)
    lo, hi = float(np.percentile(raw, 5)), float(np.percentile(raw, 99))

    Xt, yt = _matrix(test_rows)
    p = clf.predict_proba(scaler.transform(Xt))[:, 1]
    flagged = p >= config.T_REVIEW
    tp = int(((flagged == 1) & (yt == 1)).sum())
    metrics = {
        "samples": int(len(y)),
        "feedback_samples": len(feedback or []),
        "roc_auc": round(float(roc_auc_score(yt, p)), 4),
        "pr_auc": round(float(average_precision_score(yt, p)), 4),
        "precision_at_review": round(tp / max(int(flagged.sum()), 1), 4),
        "recall_at_review": round(tp / max(int((yt == 1).sum()), 1), 4),
        "false_positive_rate": round(float(((flagged == 1) & (yt == 0)).sum() / max(int((yt == 0).sum()), 1)), 4),
    }
    return ScoredModel(scaler, clf, forest, lo, hi, metrics,
                       datetime.now(timezone.utc).isoformat(timespec="seconds"))


def save(model: ScoredModel, path: str | None = None):
    joblib.dump(model, path or config.MODEL_PATH)


def load_or_train(path: str | None = None) -> ScoredModel:
    path = path or config.MODEL_PATH
    try:
        model = joblib.load(path)
        if model.feature_names == FEATURE_NAMES:
            return model
    except (FileNotFoundError, AttributeError, ModuleNotFoundError):
        pass
    model = train()
    save(model, path)
    return model
