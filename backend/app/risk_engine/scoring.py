"""Shared score-shaping helpers used by every layer."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def to_percentile(values: pd.Series) -> pd.Series:
    """Rank-transform to [0, 1]. Higher input -> higher output. NaN -> 0."""
    v = pd.to_numeric(values, errors="coerce")
    if v.notna().sum() == 0:
        return pd.Series(np.zeros(len(v)), index=v.index)
    pct = v.rank(pct=True, method="average", na_option="keep")
    return pct.fillna(0.0)


def curve(pct: pd.Series, exponent: float | None = None) -> pd.Series:
    """
    Convex shaping so the mass of ordinary projects sits near zero.
    Without it a percentile score puts the median project at 50/100, which
    would make 'medium risk' the default state of the entire portfolio.
    """
    e = config.SCORE_CURVE if exponent is None else exponent
    return np.power(pct.clip(0, 1), e)


def score_0_100(values: pd.Series, exponent: float | None = None) -> pd.Series:
    """Raw signal -> shaped 0-100 layer score."""
    return (curve(to_percentile(values), exponent) * 100).round(2)


def robust_z(values: pd.Series, median: pd.Series, mad: pd.Series) -> pd.Series:
    """Median-absolute-deviation z score; resistant to the long INR tail."""
    scale = (mad * 1.4826).replace(0, np.nan)
    z = (values - median) / scale
    return z.replace([np.inf, -np.inf], np.nan)


def band_for(score: float) -> str:
    for cutoff, name in config.BAND_THRESHOLDS:
        if score >= cutoff:
            return name
    return "Low"


def priority_for(score: float) -> str:
    for cutoff, name in config.PRIORITY_THRESHOLDS:
        if score >= cutoff:
            return name
    return "P4"
