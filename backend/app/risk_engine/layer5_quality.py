"""
Layer 5 - Data Quality & Evidence Intelligence
==============================================

Missing evidence is not fraud. It is, however, the reason an auditor cannot
rule fraud out, and it is the cheapest thing for an administration to fix.
Scored separately so the dashboard can distinguish "this looks wrong" from
"we cannot tell whether this is wrong".

All flags here are recomputed by us from raw columns. None of the upstream
d_sig_* flags are used.
"""

from __future__ import annotations

import pandas as pd

from .features import QUALITY_FLAGS


def run(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    total_weight = sum(w for w, _ in QUALITY_FLAGS.values())

    score = pd.Series(0.0, index=df.index)
    for flag, (weight, _msg) in QUALITY_FLAGS.items():
        col = df[flag] if flag in df.columns else pd.Series(0, index=df.index)
        out[flag] = col.astype(int)
        score += col.astype(float) * weight

    out["data_quality"] = ((score / total_weight) * 100).round(2)
    out["data_quality_flag_count"] = out[[f for f in QUALITY_FLAGS if f in out.columns]].sum(axis=1)
    return out
