"""
Layer 1 - Financial & Execution Anomaly Detection
=================================================

Two Isolation Forests instead of one, so the dashboard can say *which kind*
of anomaly was found rather than emitting a single opaque number:

    1a  financial_anomaly  - the money shape of the project
    1b  execution_risk     - the delivery shape of the project

Unsupervised by necessity: fraud_label is UNAVAILABLE for all 34,449 rows,
so there is nothing honest to train a classifier on. We detect *unusual*,
and a human decides whether unusual means wrong.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import EXECUTION_MODEL_FEATURES, FINANCIAL_MODEL_FEATURES
from .scoring import score_0_100

RANDOM_STATE = 42


def _fit_isolation_forest(X: pd.DataFrame, contamination: float = 0.04):
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("iforest", IsolationForest(
            n_estimators=300,
            max_samples=min(4096, len(X)),
            contamination=contamination,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ])
    pipe.fit(X)
    # score_samples: higher = more normal. Negate so higher = more anomalous.
    raw = -pipe.named_steps["iforest"].score_samples(
        pipe.named_steps["scale"].transform(
            pipe.named_steps["impute"].transform(X)
        )
    )
    return pipe, pd.Series(raw, index=X.index)


def run(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a frame indexed like df with the Layer 1 outputs."""
    out = pd.DataFrame(index=df.index)

    fin_cols = [c for c in FINANCIAL_MODEL_FEATURES if c in df.columns]
    exe_cols = [c for c in EXECUTION_MODEL_FEATURES if c in df.columns]

    _, fin_raw = _fit_isolation_forest(df[fin_cols].replace([np.inf, -np.inf], np.nan))
    _, exe_raw = _fit_isolation_forest(df[exe_cols].replace([np.inf, -np.inf], np.nan))

    out["financial_anomaly_raw"] = fin_raw
    out["execution_anomaly_raw"] = exe_raw
    out["financial_anomaly"] = score_0_100(fin_raw)

    # Execution risk blends the unsupervised signal with the two directional
    # facts an auditor actually cares about: money ahead of work, and stall.
    gap = df["f_progress_gap_pct"].clip(lower=0).fillna(0)
    stall = df["f_stall_index"].fillna(0)
    exe_pct = score_0_100(exe_raw) / 100.0
    gap_pct = score_0_100(gap) / 100.0
    stall_pct = score_0_100(stall) / 100.0
    out["execution_risk"] = ((0.45 * exe_pct + 0.35 * gap_pct + 0.20 * stall_pct) * 100).round(2)

    # Carried through for explanations
    out["progress_gap_pct"] = df["f_progress_gap_pct"].round(2)
    out["fund_utilization_pct"] = df["f_fund_utilization_pct"].round(2)
    out["physical_progress_pct"] = df["f_physical_progress_pct"].round(2)
    out["stall_index"] = stall.round(3)
    return out
