"""
Layer 0 - Feature Engineering
=============================

Reads ONLY raw / observational columns from the projects table and derives
every feature the downstream models use. Nothing produced by the upstream
rule-based risk pipeline enters here (see config.is_leaky).

Public entry point:  build_feature_frame(conn) -> pandas.DataFrame
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _safe_div(a, b, fill=np.nan):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    out = a / b.replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan).fillna(fill) if fill is not np.nan else out.replace([np.inf, -np.inf], np.nan)


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _date(s):
    return pd.to_datetime(s, errors="coerce")


def log1p_safe(s):
    v = _num(s).clip(lower=0)
    return np.log1p(v)


def cost_scale_bucket(amount: float) -> str:
    if pd.isna(amount):
        return "unknown"
    for lo, hi, name in config.COST_SCALE_BUCKETS:
        if lo <= amount < hi:
            return name
    return "very_large"


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_raw(conn) -> pd.DataFrame:
    """Load only the whitelisted raw columns, then hard-assert no leakage."""
    wanted = (
        config.IDENTITY_COLUMNS
        + config.RAW_FINANCIAL_COLUMNS
        + config.RAW_EXECUTION_COLUMNS
        + config.RAW_QUALITY_COLUMNS
    )
    available = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    cols = [c for c in dict.fromkeys(wanted) if c in available]

    leaked = [c for c in cols if config.is_leaky(c)]
    if leaked:
        raise RuntimeError(f"Leakage policy violation - refusing to load: {leaked}")

    df = pd.read_sql(f"SELECT {', '.join(cols)} FROM projects", conn)
    return df


# ---------------------------------------------------------------------------
# feature blocks
# ---------------------------------------------------------------------------
def add_financial_features(df: pd.DataFrame) -> pd.DataFrame:
    sanctioned = _num(df["sanctioned_amount_syn"])
    estimated = _num(df["estimated_cost_syn"])
    spent = _num(df["expenditure_to_date_syn"])
    disbursed = _num(df["amount_disbursed"])

    df["f_sanctioned_amount"] = sanctioned
    df["f_estimated_cost"] = estimated
    df["f_expenditure"] = spent
    df["f_amount_disbursed"] = disbursed

    df["f_log_sanctioned"] = log1p_safe(sanctioned)
    df["f_log_estimated"] = log1p_safe(estimated)
    df["f_log_expenditure"] = log1p_safe(spent)
    df["f_log_disbursed"] = log1p_safe(disbursed)

    # Fund utilisation recomputed by us from the raw amounts, not copied.
    df["f_fund_utilization_pct"] = (_safe_div(spent, sanctioned) * 100).clip(0, 300)

    # Cost posture
    df["f_cost_overrun_ratio"] = _safe_div(estimated, sanctioned)
    df["f_disbursed_share"] = _safe_div(disbursed, sanctioned)
    df["f_expenditure_vs_estimate"] = _safe_div(spent, estimated)

    # Payment behaviour
    pay_n = _num(df["payment_count_syn"]).fillna(0)
    df["f_payment_count"] = pay_n
    df["f_avg_payment_size"] = _safe_div(spent, pay_n.replace(0, np.nan))
    df["f_log_avg_payment_size"] = log1p_safe(df["f_avg_payment_size"])
    df["f_payment_velocity"] = _num(df["payment_velocity_inr_per_day_syn"])
    df["f_log_payment_velocity"] = log1p_safe(df["f_payment_velocity"])
    df["f_days_since_last_payment"] = _num(df["days_since_last_payment_syn"])

    # Round-number heuristics (our own, derived from the raw amount)
    amt = disbursed.fillna(sanctioned)
    df["q_round_100k"] = ((amt > 0) & (amt % 100_000 == 0)).astype(int)
    df["q_round_50k"] = ((amt > 0) & (amt % 50_000 == 0)).astype(int)
    df["q_round_10k"] = ((amt > 0) & (amt % 10_000 == 0)).astype(int)
    df["q_round_amount"] = df[["q_round_100k", "q_round_50k"]].max(axis=1)
    return df


def add_execution_features(df: pd.DataFrame) -> pd.DataFrame:
    start = _date(df["start_date_syn"])
    planned_end = _date(df["expected_completion_date_syn"])
    snapshot = _date(df["monitoring_snapshot_date_syn"])

    progress = _num(df["physical_progress_pct_syn"]).clip(0, 100)
    df["f_physical_progress_pct"] = progress

    # THE headline signal: money out of the door vs work on the ground.
    df["f_progress_gap_pct"] = (df["f_fund_utilization_pct"] - progress)

    planned_days = (planned_end - start).dt.days
    elapsed_days = (snapshot - start).dt.days

    # 10% of rows in the source data carry an expected completion date that
    # falls BEFORE the start date. A negative planned duration would poison
    # the schedule ratio (it produced values up to 188x), so those durations
    # are voided and imputed, and the inconsistency is recorded as a data
    # quality flag instead of being silently modelled.
    df["q_impossible_schedule"] = (planned_days <= 0).fillna(False).astype(int)
    planned_days = planned_days.where(planned_days > 0)

    df["f_planned_duration_days"] = planned_days
    df["f_elapsed_days"] = elapsed_days
    df["f_schedule_elapsed_ratio"] = _safe_div(elapsed_days, planned_days).clip(upper=10)

    # How much progress per unit of time actually consumed.
    df["f_progress_per_elapsed_pct"] = progress - (df["f_schedule_elapsed_ratio"] * 100).clip(0, 200)
    df["f_progress_rate_per_100d"] = _safe_div(progress, elapsed_days) * 100

    df["f_delay_days"] = _num(df["delay_days_syn"])
    df["f_is_delayed"] = (df["project_status_syn"].astype(str).str.lower() == "delayed").astype(int)

    upd = _num(df["progress_update_count_syn"]).fillna(0)
    df["f_progress_update_count"] = upd
    df["f_days_per_progress_update"] = _safe_div(elapsed_days, upd.replace(0, np.nan))

    # Stalled: substantial money spent, little movement, nothing reported lately.
    df["f_stall_index"] = (
        (df["f_fund_utilization_pct"].fillna(0) / 100.0)
        * (1 - progress.fillna(0) / 100.0)
        * np.log1p(df["f_days_since_last_payment"].fillna(0))
    )
    return df


def add_quality_features(df: pd.DataFrame) -> pd.DataFrame:
    desc = df["work_description"].fillna("").astype(str)
    df["f_desc_len"] = desc.str.len()
    df["f_desc_word_count"] = desc.str.split().str.len().fillna(0)

    df["q_no_image"] = (_num(df.get("has_uploaded_image", 0)).fillna(0) == 0).astype(int)
    df["q_thin_description"] = (df["f_desc_len"] < 40).astype(int)
    df["q_missing_description"] = (df["f_desc_len"] == 0).astype(int)
    df["q_missing_amount"] = _num(df["amount_disbursed"]).isna().astype(int)
    df["q_missing_completion_date"] = (
        df.get("completion_date", pd.Series([""] * len(df))).astype(str)
        .str.strip().isin(["", "nan", "None", "UNAVAILABLE", "NaT"]).astype(int)
    )
    return df


def add_context_keys(df: pd.DataFrame) -> pd.DataFrame:
    basis = df["f_sanctioned_amount"].fillna(df["f_amount_disbursed"])
    df["cost_scale_bucket"] = basis.map(cost_scale_bucket)
    df["semantic_text"] = (
        df["activity_name"].fillna("").astype(str) + " . " +
        df["work_category"].fillna("").astype(str) + " . " +
        df["work_description"].fillna("").astype(str)
    ).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    return df


# ---------------------------------------------------------------------------
# feature groups consumed by the models
# ---------------------------------------------------------------------------
FINANCIAL_MODEL_FEATURES = [
    "f_log_sanctioned",
    "f_log_estimated",
    "f_log_expenditure",
    "f_log_disbursed",
    "f_fund_utilization_pct",
    "f_cost_overrun_ratio",
    "f_disbursed_share",
    "f_expenditure_vs_estimate",
    "f_payment_count",
    "f_log_avg_payment_size",
    "f_log_payment_velocity",
    "f_days_since_last_payment",
]

EXECUTION_MODEL_FEATURES = [
    "f_physical_progress_pct",
    "f_progress_gap_pct",
    "f_schedule_elapsed_ratio",
    "f_progress_per_elapsed_pct",
    "f_progress_rate_per_100d",
    "f_delay_days",
    "f_is_delayed",
    "f_progress_update_count",
    "f_days_per_progress_update",
    "f_stall_index",
    "f_elapsed_days",
    "f_planned_duration_days",
]

QUALITY_FLAGS = {
    "q_no_image":               (0.30, "No photographic evidence uploaded for the work"),
    "q_thin_description":       (0.20, "Work description is too thin to identify the asset"),
    "q_missing_description":    (0.15, "Work description is missing entirely"),
    "q_round_amount":           (0.15, "Amount is a suspiciously round figure"),
    "q_missing_amount":         (0.10, "Disbursed amount is not recorded"),
    "q_missing_completion_date":(0.10, "No completion date recorded"),
    "q_impossible_schedule":    (0.15, "Expected completion date falls before the start date"),
}


def build_feature_frame(conn) -> pd.DataFrame:
    df = load_raw(conn)
    df = add_financial_features(df)
    df = add_execution_features(df)
    df = add_quality_features(df)
    df = add_context_keys(df)
    return df
