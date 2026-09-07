"""
Explanation Generator
=====================

Every flagged project must arrive at a human with a sentence they can act on.
A score with no reason is an accusation; a score with a reason is a lead.

Each reason carries: the layer that produced it, a severity, the sentence,
and the numeric evidence behind the sentence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .features import QUALITY_FLAGS


def _fmt_inr(v):
    if v is None or (isinstance(v, float) and (np.isnan(v))):
        return "n/a"
    v = float(v)
    if v >= 1e7:
        return f"Rs {v / 1e7:.2f} Cr"
    if v >= 1e5:
        return f"Rs {v / 1e5:.2f} L"
    return f"Rs {v:,.0f}"


def _nz(v, default=0.0):
    try:
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def build_reasons(row: pd.Series) -> list[dict]:
    """Produce the ordered 'why was this flagged' list for one project."""
    reasons: list[dict] = []

    def add(layer, severity, message, evidence=None):
        reasons.append({
            "layer": config.LAYER_LABELS.get(layer, layer),
            "layer_key": layer,
            "severity": severity,
            "message": message,
            "evidence": evidence or {},
        })

    def sev(score):
        return "high" if score >= 75 else "medium" if score >= 55 else "low"

    # -- Layer 1b: execution -------------------------------------------------
    gap = _nz(row.get("progress_gap_pct"))
    util = _nz(row.get("fund_utilization_pct"))
    prog = _nz(row.get("physical_progress_pct"))
    if gap >= 25:
        add("execution_risk", sev(_nz(row.get("execution_risk"))),
            f"{util:.0f}% of sanctioned funds spent against only {prog:.0f}% physical "
            f"progress - a {gap:.0f} point expenditure-to-progress gap.",
            {"fund_utilization_pct": util, "physical_progress_pct": prog, "progress_gap_pct": gap})

    if _nz(row.get("f_delay_days")) > 120 and prog < 60:
        add("execution_risk", "medium",
            f"Work is {_nz(row.get('f_delay_days')):.0f} days behind its expected "
            f"completion date with progress still at {prog:.0f}%.",
            {"delay_days": _nz(row.get("f_delay_days"))})

    dslp = _nz(row.get("f_days_since_last_payment"))
    if dslp > 240 and util > 50:
        add("execution_risk", "medium",
            f"No payment recorded for {dslp:.0f} days despite {util:.0f}% of funds "
            f"already utilised - possible stalled work.",
            {"days_since_last_payment": dslp})

    # -- Layer 1a: financial -------------------------------------------------
    fin = _nz(row.get("financial_anomaly"))
    if fin >= config.REASON_THRESHOLD:
        # The score is a percentile, so it can round to a flat 100 - which
        # reads as "more unusual than every work including itself". Cap the
        # wording and gain a decimal at the top of the range instead.
        pct = min(fin, 99.9)
        add("financial_anomaly", sev(fin),
            f"The financial shape of this work (amount, cost, expenditure and "
            f"payment pattern) is more unusual than {pct:.1f}% of the portfolio.",
            {"financial_anomaly_score": fin,
             "sanctioned_amount": _nz(row.get("f_sanctioned_amount")),
             "expenditure": _nz(row.get("f_expenditure"))})

    if _nz(row.get("f_payment_count")) >= 12 and prog < 50:
        add("financial_anomaly", "medium",
            f"{_nz(row.get('f_payment_count')):.0f} separate payments released while "
            f"physical progress is only {prog:.0f}%.",
            {"payment_count": _nz(row.get("f_payment_count"))})

    # -- Layer 2: context ----------------------------------------------------
    ctx = _nz(row.get("context_deviation"))
    if ctx >= config.REASON_THRESHOLD:
        dev_cost = _nz(row.get("deviation_cost_pct"))
        dev_prog = _nz(row.get("deviation_progress_pt"))
        parts = []
        if dev_cost > 15:
            parts.append(f"costs {dev_cost:.0f}% more than the peer median "
                         f"({_fmt_inr(row.get('peer_median_cost_inr'))})")
        if dev_prog < -12:
            parts.append(f"is {abs(dev_prog):.0f} points behind peer progress")
        if _nz(row.get("deviation_utilization_pt")) > 12:
            parts.append(f"has drawn {_nz(row.get('deviation_utilization_pt')):.0f} points "
                         f"more of its funds than peers")
        detail = "; ".join(parts) if parts else "deviates materially from its peer group"
        add("context_deviation", sev(ctx),
            f"Against {int(_nz(row.get('peer_n')))} comparable works "
            f"({row.get('peer_level', 'peer group')}), this project {detail}.",
            {"peer_n": int(_nz(row.get("peer_n"))),
             "peer_level": row.get("peer_level"),
             "deviation_cost_pct": dev_cost,
             "deviation_progress_pt": dev_prog})

    # -- Layer 3: semantic ---------------------------------------------------
    max_sim = _nz(row.get("semantic_max_similarity"))
    same_ida = int(_nz(row.get("semantic_near_duplicate_same_ida")))
    same_const = int(_nz(row.get("semantic_near_duplicate_same_constituency")))
    if max_sim >= config.NEAR_DUPLICATE_THRESHOLD and (same_ida or same_const):
        where = []
        if same_ida:
            where.append(f"{same_ida} under the same implementing agency")
        if same_const:
            where.append(f"{same_const} in the same constituency")
        add("semantic_similarity",
            "high" if (max_sim >= config.STRONG_DUPLICATE_THRESHOLD and same_ida) else "medium",
            f"Work description is {max_sim * 100:.0f}% similar to other recommended "
            f"work(s) - " + " and ".join(where) + ".",
            {"max_similarity": max_sim,
             "near_duplicate_count": int(_nz(row.get("semantic_near_duplicate_count"))),
             "same_ida": same_ida,
             "same_constituency": same_const})

    # -- Layer 4: spatial ----------------------------------------------------
    spa = _nz(row.get("spatial_risk"))
    nearby = int(_nz(row.get("nearby_similar_project_count")))
    if spa >= config.REASON_THRESHOLD and nearby > 0:
        add("spatial_risk", sev(spa),
            f"{nearby} similar work(s) of the same type fall in the same constituency "
            f"in an overlapping period - possible functional duplication.",
            {"nearby_similar_project_count": nearby,
             "constituency_activity_cluster_size": int(_nz(row.get("constituency_activity_cluster_size"))),
             "resolution": config.SPATIAL_RESOLUTION_NOTE})

    # -- Layer 5: data quality ----------------------------------------------
    dq_msgs = [msg for flag, (_w, msg) in QUALITY_FLAGS.items() if int(_nz(row.get(flag))) == 1]
    if dq_msgs:
        add("data_quality",
            "medium" if _nz(row.get("data_quality")) >= 55 else "low",
            "Evidence gaps: " + "; ".join(dq_msgs).lower() + ".",
            {"flags": dq_msgs})

    # An alert with no sentence attached is an accusation without a reason.
    # A work can accumulate enough sub-threshold signal across layers to clear
    # the Medium band without any single rule firing, so the dominant layer
    # always gets the last word.
    if not reasons and _nz(row.get("risk_score")) >= 45:
        layer_key = None
        for key, label in config.LAYER_LABELS.items():
            if label == row.get("top_risk_layer"):
                layer_key = key
                break
        score = _nz(row.get(layer_key)) if layer_key else 0.0
        add(layer_key or "data_quality", "low",
            f"No single rule fired, but this work accumulates moderate signal "
            f"across several layers - {row.get('top_risk_layer', 'the dominant layer')} "
            f"is the strongest at {score:.0f}/100. Review as low-priority context.",
            {"top_layer_score": score, "risk_score": _nz(row.get("risk_score"))})

    order = {"high": 0, "medium": 1, "low": 2}
    reasons.sort(key=lambda r: order.get(r["severity"], 3))
    return reasons


def build_summary(row: pd.Series, reasons: list[dict]) -> str:
    """
    One-line headline for list views.

    Prefers the reason belonging to the layer that actually contributed most
    to the unified score, so the headline and the 'top risk layer' badge in
    the UI never disagree.
    """
    if not reasons:
        return "No material anomaly detected across the six risk layers."
    dominant = row.get("top_risk_layer")
    for r in reasons:
        if r["layer"] == dominant:
            return f"{r['layer']}: {r['message']}"
    top = reasons[0]
    return f"{top['layer']}: {top['message']}"
