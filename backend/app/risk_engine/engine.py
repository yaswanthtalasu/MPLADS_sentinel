"""
Unified Risk Engine
===================

No single model decides. Six independent layers each produce a 0-100 signal
from a different kind of evidence, and this module fuses them into one score,
one band, one priority and one explanation.

    Financial Anomaly   Execution Risk   Peer Deviation
    Semantic Similarity   Spatial Risk   Data Quality
                          |
                    RISK ENGINE
                          |
        Risk Score + Priority + Explanation
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import (config, explain, features, layer1_financial, layer2_context,
               layer3_semantic, layer4_spatial, layer5_quality)
from .scoring import band_for, priority_for


def compute(conn, verbose: bool = True) -> dict:
    def say(msg):
        if verbose:
            print(msg, flush=True)

    say("[0/6] Engineering features from raw columns...")
    df = features.build_feature_frame(conn)
    say(f"      {len(df):,} works, {df.shape[1]} engineered columns")

    say("[1/6] Layer 1  - Financial & Execution anomaly (Isolation Forest x2)...")
    l1 = layer1_financial.run(df)

    say("[2/6] Layer 2  - Context Intelligence (hierarchical peer groups)...")
    l2 = layer2_context.run(df)
    say("      peer levels used: " +
        ", ".join(f"{k}={v}" for k, v in l2["peer_level"].value_counts().items()))

    say("[3/6] Layer 3  - Semantic Intelligence (embeddings + kNN)...")
    l3, neighbours, _emb, backend = layer3_semantic.run(df)

    say("[4/6] Layer 4  - Spatial Intelligence (ECI constituency centroids)...")
    l4 = layer4_spatial.run(df, neighbours, conn)

    say("[5/6] Layer 5  - Data Quality & Evidence...")
    l5 = layer5_quality.run(df)

    say("[6/6] Fusing layers into the unified risk score...")
    merged = pd.concat([df, l1, l2, l3, l4, l5], axis=1)
    merged = merged.loc[:, ~merged.columns.duplicated()]

    unified = pd.Series(0.0, index=merged.index)
    for layer, weight in config.LAYER_WEIGHTS.items():
        unified += merged[layer].fillna(0).astype(float) * weight
    merged["risk_score"] = unified.round(2)
    merged["risk_band"] = merged["risk_score"].map(band_for)
    merged["risk_priority"] = merged["risk_score"].map(priority_for)

    # Which layer contributed most to this particular score
    contrib = pd.DataFrame({
        layer: merged[layer].fillna(0) * weight
        for layer, weight in config.LAYER_WEIGHTS.items()
    })
    merged["top_risk_layer"] = contrib.idxmax(axis=1).map(config.LAYER_LABELS)
    merged["top_risk_contribution"] = contrib.max(axis=1).round(2)

    say("      generating explanations...")
    reason_json, summaries = [], []
    for _, row in merged.iterrows():
        reasons = explain.build_reasons(row)
        reason_json.append(json.dumps(reasons, ensure_ascii=False))
        summaries.append(explain.build_summary(row, reasons))
    merged["risk_reasons"] = reason_json
    merged["risk_summary"] = summaries
    merged["reason_count"] = [len(json.loads(r)) for r in reason_json]

    merged["embedding_backend"] = backend
    return {"scored": merged, "neighbours": neighbours, "backend": backend}


# ---------------------------------------------------------------------------
# columns persisted to the risk_scores table
# ---------------------------------------------------------------------------
RISK_TABLE_COLUMNS = [
    "work_code",
    # unified
    "risk_score", "risk_band", "risk_priority",
    "top_risk_layer", "top_risk_contribution",
    "risk_summary", "risk_reasons", "reason_count",
    # layer scores
    "financial_anomaly", "execution_risk", "context_deviation",
    "semantic_similarity", "spatial_risk", "data_quality",
    # layer 1 evidence
    "fund_utilization_pct", "physical_progress_pct", "progress_gap_pct", "stall_index",
    "f_sanctioned_amount", "f_estimated_cost", "f_expenditure", "f_amount_disbursed",
    "f_payment_count", "f_payment_velocity", "f_days_since_last_payment",
    "f_delay_days", "f_elapsed_days", "f_planned_duration_days",
    "f_schedule_elapsed_ratio", "f_progress_update_count",
    # layer 2 evidence
    "peer_key", "peer_level", "peer_n", "peer_confidence",
    "peer_median_cost_inr", "peer_median_progress", "peer_median_utilization",
    "peer_median_delay",
    "deviation_cost_pct", "deviation_progress_pt", "deviation_utilization_pt",
    "deviation_delay_days",
    # layer 3 evidence
    "semantic_max_similarity", "semantic_near_duplicate_count",
    "semantic_near_duplicate_same_ida", "semantic_near_duplicate_same_constituency",
    "is_near_duplicate", "is_strong_duplicate",
    # layer 4 evidence
    "pc_id", "pc_name", "geo_lat", "geo_lon", "coordinate_type", "geo_source",
    "spatial_overlap_score", "nearest_similar_distance_m",
    "nearby_similar_project_count", "constituency_activity_cluster_size",
    # layer 5 evidence
    "q_no_image", "q_thin_description", "q_missing_description",
    "q_round_amount", "q_missing_amount", "q_missing_completion_date",
    "q_impossible_schedule",
    "data_quality_flag_count",
    # provenance
    "embedding_backend",
]
