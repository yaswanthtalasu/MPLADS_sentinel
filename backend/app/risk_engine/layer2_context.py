"""
Layer 2 - Context Intelligence (Peer-Group Benchmarking)
========================================================

A project is never compared against the whole 34,449-row portfolio. It is
compared against projects that share:

        ACTIVITY  +  GEOGRAPHY  +  COST SCALE  +  TIME PERIOD

We walk config.PEER_LEVELS from most specific to least specific and assign
each project the first peer group that has at least MIN_PEER_GROUP_SIZE
members. That level is recorded, so the UI can state exactly what the
project was benchmarked against - "43 similar road works in Krishna,
2025-26, same cost band" rather than an unexplained deviation number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .scoring import robust_z, score_0_100

METRICS = {
    "cost":        "f_log_sanctioned",
    "progress":    "f_physical_progress_pct",
    "utilization": "f_fund_utilization_pct",
    "delay":       "f_delay_days",
}


def _level_composite(df: pd.DataFrame, keys) -> pd.Series:
    usable = [k for k in keys if k in df.columns]
    return df[usable].astype(str).agg(" | ".join, axis=1)


def _assign_peer_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each row the most specific peer group that is big enough.

    Important: group size is always measured across ALL works sharing the
    composite key, never only across the works still unassigned at that
    level. Counting the leftovers instead would let a row resolve into a
    "group" of five while claiming a group of thirty, and every median it is
    benchmarked against would come from those five.
    """
    peer_key = pd.Series([None] * len(df), index=df.index, dtype=object)
    peer_level = pd.Series([None] * len(df), index=df.index, dtype=object)
    peer_n = pd.Series(0, index=df.index, dtype=int)

    unresolved = pd.Series(True, index=df.index)
    for level_name, keys in config.PEER_LEVELS:
        if not unresolved.any():
            break
        composite = _level_composite(df, keys)
        sizes = composite.map(composite.value_counts())          # over ALL rows
        ok = unresolved & (sizes >= config.MIN_PEER_GROUP_SIZE)
        peer_key.loc[ok] = level_name + " :: " + composite.loc[ok]
        peer_level.loc[ok] = level_name
        peer_n.loc[ok] = sizes.loc[ok]
        unresolved &= ~ok

    # Anything still unresolved falls back to the whole portfolio, flagged.
    peer_key.loc[unresolved] = "portfolio :: all"
    peer_level.loc[unresolved] = "portfolio"
    peer_n.loc[unresolved] = len(df)

    return pd.DataFrame(
        {"peer_key": peer_key, "peer_level": peer_level, "peer_n": peer_n},
        index=df.index,
    )


def run(df: pd.DataFrame) -> pd.DataFrame:
    groups = _assign_peer_groups(df)
    work = df.join(groups)
    out = groups.copy()

    for label, col in METRICS.items():
        out[f"peer_median_{label}"] = np.nan
        out[f"z_{label}"] = np.nan

    # Statistics are computed per level over the FULL frame grouped by that
    # level's keys, then read off for the rows that resolved at that level.
    # Grouping on the assigned peer_key alone would compute each median from
    # the leftovers rather than from the whole peer group.
    levels = dict(config.PEER_LEVELS)
    for level_name in out["peer_level"].unique():
        mask = out["peer_level"] == level_name
        if not mask.any():
            continue
        if level_name == "portfolio":
            grouper = pd.Series("all", index=work.index)
        else:
            grouper = _level_composite(work, levels[level_name])

        grouped = work.groupby(grouper, sort=False)
        for label, col in METRICS.items():
            if col not in work.columns:
                continue
            values = pd.to_numeric(work[col], errors="coerce")
            med = grouped[col].transform("median")
            mad = grouped[col].transform(lambda s: (s - s.median()).abs().median())
            out.loc[mask, f"peer_median_{label}"] = med[mask]
            out.loc[mask, f"z_{label}"] = robust_z(values, med, mad)[mask]

    # Human-readable deviations for the investigation screen
    peer_cost_inr = np.expm1(out["peer_median_cost"])
    out["peer_median_cost_inr"] = peer_cost_inr.round(0)
    actual_cost = df["f_sanctioned_amount"]
    out["deviation_cost_pct"] = (
        ((actual_cost - peer_cost_inr) / peer_cost_inr.replace(0, np.nan)) * 100
    ).round(2)
    out["deviation_progress_pt"] = (
        df["f_physical_progress_pct"] - out["peer_median_progress"]
    ).round(2)
    out["deviation_utilization_pt"] = (
        df["f_fund_utilization_pct"] - out["peer_median_utilization"]
    ).round(2)
    out["deviation_delay_days"] = (
        df["f_delay_days"] - out["peer_median_delay"]
    ).round(1)

    # ------------------------------------------------------------------
    # Directional risk composition.
    # Only deviations in the concerning direction contribute:
    #   cost ABOVE peers, progress BELOW peers, utilisation ABOVE peers,
    #   delay ABOVE peers.
    # ------------------------------------------------------------------
    cost_hi = out["z_cost"].clip(lower=0).fillna(0)
    prog_lo = (-out["z_progress"]).clip(lower=0).fillna(0)
    util_hi = out["z_utilization"].clip(lower=0).fillna(0)
    delay_hi = out["z_delay"].clip(lower=0).fillna(0)

    raw = (0.30 * cost_hi) + (0.35 * prog_lo) + (0.20 * util_hi) + (0.15 * delay_hi)

    # A tiny peer group is weak evidence. Shrink towards zero below n=60.
    confidence = (out["peer_n"] / 60.0).clip(upper=1.0)
    out["peer_confidence"] = confidence.round(3)
    out["context_deviation_raw"] = (raw * confidence).round(4)
    out["context_deviation"] = score_0_100(out["context_deviation_raw"])
    return out
