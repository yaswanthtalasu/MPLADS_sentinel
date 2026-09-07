"""
MPLADS Sentinel - Core API
==========================

Serves the output of the six-layer Unified Risk Engine. Every endpoint that
returns a risk score also returns the layer breakdown and the explanation
behind it - the UI is never allowed to show a number it cannot justify.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .database import execute_query, execute_update
from .risk_engine import config

router = APIRouter()

LAYER_KEYS = list(config.LAYER_WEIGHTS.keys())


class ReviewStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None


def _loads(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def _layer_breakdown(row: dict) -> list[dict[str, Any]]:
    out = []
    for key in LAYER_KEYS:
        score = row.get(key) or 0.0
        weight = config.LAYER_WEIGHTS[key]
        out.append({
            "key": key,
            "label": config.LAYER_LABELS[key],
            "score": round(float(score), 1),
            "weight": weight,
            "contribution": round(float(score) * weight, 2),
        })
    return sorted(out, key=lambda d: d["contribution"], reverse=True)


# ---------------------------------------------------------------------------
# Engine metadata / methodology
# ---------------------------------------------------------------------------
@router.get("/engine/meta")
def get_engine_meta():
    """Everything a jury or an auditor needs to interrogate the score."""
    try:
        meta = execute_query("SELECT * FROM risk_engine_meta LIMIT 1")[0]
    except (IndexError, Exception):  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="Risk engine has not been built. Run: python -m backend.app.risk_engine.build",
        )
    meta["layer_weights"] = _loads(meta.get("layer_weights"), {})
    meta["band_thresholds"] = _loads(meta.get("band_thresholds"), [])
    meta["excluded_leakage_columns"] = _loads(meta.get("excluded_leakage_columns"), [])
    meta["leakage_prefixes"] = _loads(meta.get("leakage_prefixes"), [])
    meta["layers"] = [
        {"key": k, "label": config.LAYER_LABELS[k], "weight": w}
        for k, w in config.LAYER_WEIGHTS.items()
    ]
    meta["peer_levels"] = [name for name, _ in config.PEER_LEVELS]
    meta["min_peer_group_size"] = config.MIN_PEER_GROUP_SIZE
    return meta


@router.get("/engine/validation")
def get_engine_validation():
    """
    Smoke-test results against the injected synthetic scenarios.
    Explicitly NOT a fraud-accuracy metric - the source data has no fraud labels.
    """
    try:
        rows = execute_query("SELECT * FROM validation_scenario_summary")
    except Exception:  # noqa: BLE001
        rows = []
    return {
        "disclaimer": (
            "fraud_label is UNAVAILABLE for all 34,449 source records. These figures "
            "measure whether the engine ranks deliberately-injected unusual cases above "
            "normal ones. They are not fraud detection accuracy."
        ),
        "scenarios": rows,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@router.get("/dashboard/summary")
def get_dashboard_summary():
    stats = execute_query("""
        SELECT
            COUNT(*)                                                     AS total_projects,
            SUM(CASE WHEN r.risk_band = 'High'   THEN 1 ELSE 0 END)      AS high_risk,
            SUM(CASE WHEN r.risk_band = 'Medium' THEN 1 ELSE 0 END)      AS medium_risk,
            SUM(CASE WHEN r.risk_band = 'Low'    THEN 1 ELSE 0 END)      AS low_risk,
            SUM(CASE WHEN p.investigation_status != 'Unassigned' THEN 1 ELSE 0 END) AS under_review,
            ROUND(AVG(r.risk_score), 2)                                  AS avg_risk_score,
            SUM(CASE WHEN r.progress_gap_pct >= 25 THEN 1 ELSE 0 END)    AS large_progress_gap,
            SUM(CASE WHEN r.is_near_duplicate = 1 THEN 1 ELSE 0 END)     AS near_duplicates,
            SUM(CASE WHEN r.is_strong_duplicate = 1 THEN 1 ELSE 0 END)   AS strong_duplicates,
            SUM(CASE WHEN r.q_no_image = 1 THEN 1 ELSE 0 END)            AS missing_evidence,
            SUM(r.f_expenditure)                                         AS total_expenditure
        FROM risk_scores r
        JOIN projects p ON p.work_code = r.work_code
    """)[0]

    layer_means = execute_query(f"""
        SELECT {', '.join(f'ROUND(AVG({k}), 2) AS {k}' for k in LAYER_KEYS)}
        FROM risk_scores
    """)[0]
    layer_profile = [
        {"key": k, "label": config.LAYER_LABELS[k],
         "mean_score": layer_means.get(k) or 0,
         "weight": config.LAYER_WEIGHTS[k]}
        for k in LAYER_KEYS
    ]

    top_layer = execute_query("""
        SELECT top_risk_layer AS layer, COUNT(*) AS n
        FROM risk_scores WHERE risk_band != 'Low'
        GROUP BY top_risk_layer ORDER BY n DESC
    """)

    # Expenditure vs physical progress - the headline chart.
    scatter = execute_query("""
        SELECT work_code, risk_band, risk_score,
               physical_progress_pct, fund_utilization_pct, progress_gap_pct
        FROM risk_scores
        WHERE physical_progress_pct IS NOT NULL AND fund_utilization_pct IS NOT NULL
        ORDER BY RANDOM() LIMIT 2500
    """)

    states = execute_query("""
        SELECT p.state,
               COUNT(*) AS n,
               ROUND(AVG(r.risk_score), 2) AS avg_risk,
               SUM(CASE WHEN r.risk_band = 'High' THEN 1 ELSE 0 END) AS high_risk
        FROM risk_scores r JOIN projects p ON p.work_code = r.work_code
        GROUP BY p.state HAVING n >= 50
        ORDER BY avg_risk DESC LIMIT 10
    """)

    return {
        "kpis": stats,
        "layer_profile": layer_profile,
        "top_layer_distribution": top_layer,
        "scatter_data": scatter,
        "state_leaderboard": states,
        "methodology_note": (
            "Six independent layers are scored separately and fused. No single model "
            "decides. Legacy rule-based scores from the source dataset are excluded "
            "from every model input."
        ),
    }


# ---------------------------------------------------------------------------
# Alert queue
# ---------------------------------------------------------------------------
@router.get("/projects")
def get_projects(
    limit: int = Query(50, le=500),
    offset: int = 0,
    risk_band: Optional[str] = None,
    priority: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    layer: Optional[str] = Query(None, description="Filter by dominant risk layer key"),
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = Query("risk_score", pattern="^(risk_score|progress_gap_pct|financial_anomaly|execution_risk|context_deviation|semantic_similarity|spatial_risk|data_quality)$"),
):
    where, params = ["1=1"], []
    if risk_band:
        where.append("r.risk_band = ?"); params.append(risk_band)
    if priority:
        where.append("r.risk_priority = ?"); params.append(priority)
    if state:
        where.append("p.state = ?"); params.append(state)
    if category:
        where.append("p.work_category = ?"); params.append(category)
    if layer:
        if layer not in config.LAYER_LABELS:
            raise HTTPException(status_code=400, detail="Unknown layer")
        where.append("r.top_risk_layer = ?"); params.append(config.LAYER_LABELS[layer])
    if status:
        where.append("p.investigation_status = ?"); params.append(status)
    if search:
        where.append("(p.work_code LIKE ? OR p.work_description LIKE ? OR p.constituency LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    total = execute_query(
        f"SELECT COUNT(*) AS n FROM risk_scores r JOIN projects p ON p.work_code = r.work_code "
        f"WHERE {' AND '.join(where)}", tuple(params)
    )[0]["n"]

    rows = execute_query(f"""
        SELECT p.work_code, p.work_category, p.activity_name, p.state, p.constituency,
               p.ida, p.recommend_fy, p.investigation_status,
               r.risk_score, r.risk_band, r.risk_priority, r.top_risk_layer,
               r.risk_summary, r.reason_count,
               r.financial_anomaly, r.execution_risk, r.context_deviation,
               r.semantic_similarity, r.spatial_risk, r.data_quality,
               r.progress_gap_pct, r.physical_progress_pct, r.fund_utilization_pct,
               r.f_sanctioned_amount, r.f_expenditure
        FROM risk_scores r JOIN projects p ON p.work_code = r.work_code
        WHERE {' AND '.join(where)}
        ORDER BY r.{sort} DESC
        LIMIT ? OFFSET ?
    """, tuple(params + [limit, offset]))

    for row in rows:
        row["layer_breakdown"] = _layer_breakdown(row)

    return {"total": total, "limit": limit, "offset": offset, "results": rows}


@router.get("/projects/filters")
def get_project_filters():
    return {
        "states": [r["state"] for r in execute_query(
            "SELECT DISTINCT state FROM projects WHERE state IS NOT NULL ORDER BY state")],
        "categories": [r["work_category"] for r in execute_query(
            "SELECT DISTINCT work_category FROM projects WHERE work_category IS NOT NULL ORDER BY work_category")],
        "risk_bands": ["High", "Medium", "Low"],
        "priorities": ["P1", "P2", "P3", "P4"],
        "layers": [{"key": k, "label": v} for k, v in config.LAYER_LABELS.items()],
        "statuses": ["Unassigned", "Under Investigation", "Resolved", "Explained / No Issue"],
    }


# ---------------------------------------------------------------------------
# Single project investigation view
# ---------------------------------------------------------------------------
# NOTE: MPLADS work codes contain forward slashes ("WS/MP18222/2025-2026/171129"),
# so they cannot travel as path parameters. Every project-specific endpoint
# takes the code as a query parameter instead.
@router.get("/projects/detail")
def get_project_details(work_code: str = Query(..., description="Full MPLADS work code")):
    res = execute_query("""
        SELECT p.*, r.*
        FROM projects p JOIN risk_scores r ON r.work_code = p.work_code
        WHERE p.work_code = ?
    """, (work_code,))
    if not res:
        raise HTTPException(status_code=404, detail="Project not found")
    project = res[0]

    project["risk_reasons"] = _loads(project.get("risk_reasons"), [])
    project["layer_breakdown"] = _layer_breakdown(project)

    # Layer 3 / 4 - the works this one looks like, and how far away they are
    similar = execute_query("""
        SELECT s.similar_work_code AS work_code, s.similarity, s.rank,
               s.same_ida, s.same_constituency, s.same_activity,
               p.work_description, p.activity_name, p.state, p.constituency, p.ida,
               p.amount_disbursed, r.risk_score, r.risk_band,
               r.geo_lat, r.geo_lon
        FROM project_similarity s
        JOIN projects p ON p.work_code = s.similar_work_code
        LEFT JOIN risk_scores r ON r.work_code = s.similar_work_code
        WHERE s.work_code = ?
        ORDER BY s.similarity DESC LIMIT 5
    """, (work_code,))
    project["top_similar_projects"] = similar
    project["spatial_resolution_note"] = config.SPATIAL_RESOLUTION_NOTE

    # Layer 2 - what it was actually benchmarked against
    project["peer_comparison"] = {
        "peer_key": project.get("peer_key"),
        "peer_level": project.get("peer_level"),
        "peer_n": project.get("peer_n"),
        "peer_confidence": project.get("peer_confidence"),
        "metrics": [
            {"metric": "Sanctioned Cost", "unit": "INR",
             "value": project.get("f_sanctioned_amount"),
             "peer_median": project.get("peer_median_cost_inr"),
             "deviation": project.get("deviation_cost_pct"),
             "deviation_unit": "%",
             "concerning": (project.get("deviation_cost_pct") or 0) > 20},
            {"metric": "Physical Progress", "unit": "%",
             "value": project.get("physical_progress_pct"),
             "peer_median": project.get("peer_median_progress"),
             "deviation": project.get("deviation_progress_pt"),
             "deviation_unit": "pts",
             "concerning": (project.get("deviation_progress_pt") or 0) < -15},
            {"metric": "Fund Utilization", "unit": "%",
             "value": project.get("fund_utilization_pct"),
             "peer_median": project.get("peer_median_utilization"),
             "deviation": project.get("deviation_utilization_pt"),
             "deviation_unit": "pts",
             "concerning": (project.get("deviation_utilization_pt") or 0) > 15},
            {"metric": "Delay", "unit": "days",
             "value": project.get("f_delay_days"),
             "peer_median": project.get("peer_median_delay"),
             "deviation": project.get("deviation_delay_days"),
             "deviation_unit": "days",
             "concerning": (project.get("deviation_delay_days") or 0) > 60},
        ],
    }

    # Independent legacy score, shown for comparison only.
    project["legacy_benchmark"] = {
        "d_risk_score": project.get("d_risk_score"),
        "d_risk_band": project.get("d_risk_band"),
        "note": ("Legacy rule-based score shipped with the source dataset. It is "
                 "excluded from every input of the Sentinel engine and is displayed "
                 "purely as an independent comparison."),
    }
    return project


@router.get("/projects/similar")
def get_similar_projects(work_code: str = Query(...), limit: int = 10):
    return execute_query("""
        SELECT s.similar_work_code AS work_code, s.similarity, s.same_ida,
               s.same_constituency, s.same_activity,
               p.work_description, p.activity_name, p.state, p.constituency,
               p.amount_disbursed, r.risk_score, r.risk_band
        FROM project_similarity s
        JOIN projects p ON p.work_code = s.similar_work_code
        LEFT JOIN risk_scores r ON r.work_code = s.similar_work_code
        WHERE s.work_code = ?
        ORDER BY s.similarity DESC LIMIT ?
    """, (work_code, limit))


@router.post("/projects/review")
def update_review_status(update: ReviewStatusUpdate, work_code: str = Query(...)):
    valid = ["Unassigned", "Under Investigation", "Resolved", "Explained / No Issue"]
    if update.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Expected one of {valid}")
    execute_update(
        "UPDATE projects SET investigation_status = ? WHERE work_code = ?",
        (update.status, work_code),
    )
    return {"message": "Status updated", "work_code": work_code, "status": update.status}


@router.get("/map/projects")
def get_map_projects(limit: int = Query(5000, le=20000)):
    """Constituency-centroid points for the risk map. No synthetic coordinates."""
    return {
        "coordinate_policy": config.SPATIAL_RESOLUTION_NOTE,
        "points": execute_query("""
            SELECT r.work_code, r.geo_lat AS latitude, r.geo_lon AS longitude,
                   r.risk_band, r.risk_score, r.top_risk_layer,
                   r.coordinate_type, r.geo_source, r.pc_name,
                   p.work_category, p.state
            FROM risk_scores r JOIN projects p ON p.work_code = r.work_code
            WHERE r.geo_lat IS NOT NULL AND r.geo_lon IS NOT NULL
            ORDER BY r.risk_score DESC LIMIT ?
        """, (limit,)),
    }
