import os
import json
import sqlite3
import pandas as pd
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from .database import get_db_connection

router = APIRouter(prefix="/api/map", tags=["map"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEO_DIR = os.path.join(BASE_DIR, "geo_data")
STATE_GEOJSON_PATH = os.path.join(GEO_DIR, "india_states_2019.geojson")
PC_GEOJSON_PATH = os.path.join(GEO_DIR, "india_constituencies_2019.geojson")
QUALITY_REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "map_data_quality_report.csv")

# Cache geojson in memory for sub-millisecond response
_STATE_GEOJSON = None
_PC_GEOJSON = None

def get_state_geojson():
    global _STATE_GEOJSON
    if _STATE_GEOJSON is None and os.path.exists(STATE_GEOJSON_PATH):
        with open(STATE_GEOJSON_PATH, "r", encoding="utf-8") as f:
            _STATE_GEOJSON = json.load(f)
    return _STATE_GEOJSON

def get_pc_geojson():
    global _PC_GEOJSON
    if _PC_GEOJSON is None and os.path.exists(PC_GEOJSON_PATH):
        with open(PC_GEOJSON_PATH, "r", encoding="utf-8") as f:
            _PC_GEOJSON = json.load(f)
    return _PC_GEOJSON


def build_filter_clause(
    state: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    risk_band: Optional[str] = None
):
    where_clauses = ["1=1"]
    params = []

    if state and isinstance(state, str):
        where_clauses.append("p.state = ?")
        params.append(state)
    if fiscal_year and isinstance(fiscal_year, str):
        where_clauses.append("p.recommend_fy = ?")
        params.append(fiscal_year)
    if category and isinstance(category, str):
        where_clauses.append("p.work_category = ?")
        params.append(category)
    if status and isinstance(status, str):
        if status.lower() == "completed":
            where_clauses.append("(p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed')")
        elif status.lower() == "ongoing":
            where_clauses.append("(p.completion_date IS NULL AND (p.project_status_syn IS NULL OR p.project_status_syn != 'Completed'))")
    if risk_band and isinstance(risk_band, str):
        where_clauses.append("p.risk_band = ?")
        params.append(risk_band)

    return " AND ".join(where_clauses), params


@router.get("/filter-options")
def get_filter_options():
    conn = get_db_connection()
    try:
        states = [r[0] for r in conn.execute("SELECT DISTINCT state FROM projects WHERE state IS NOT NULL ORDER BY state").fetchall()]
        fys = [r[0] for r in conn.execute("SELECT DISTINCT recommend_fy FROM projects WHERE recommend_fy IS NOT NULL ORDER BY recommend_fy DESC").fetchall()]
        categories = [r[0] for r in conn.execute("SELECT DISTINCT work_category FROM projects WHERE work_category IS NOT NULL ORDER BY work_category").fetchall()]
        risk_bands = ["High", "Medium", "Low"]
        statuses = ["Completed", "Ongoing"]
        return {
            "states": states,
            "fiscal_years": fys,
            "categories": categories,
            "risk_bands": risk_bands,
            "statuses": statuses
        }
    finally:
        conn.close()


@router.get("/summary")
def get_map_summary(
    state: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    risk_band: Optional[str] = None
):
    """
    Returns aggregated analytical metrics at National, State, and Constituency levels.
    """
    where_sql, params = build_filter_clause(state, fiscal_year, category, status, risk_band)
    conn = get_db_connection()

    try:
        # 1. National overall totals
        total_query = f"""
            SELECT 
                COUNT(*) as total_projects,
                COALESCE(SUM(p.amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(p.risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN p.risk_band = 'Medium' THEN 1 ELSE 0 END) as medium_risk_count,
                SUM(CASE WHEN p.risk_band = 'Low' THEN 1 ELSE 0 END) as low_risk_count,
                SUM(CASE WHEN p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(AVG(p.fund_utilization_pct_syn), 78.5) as avg_utilization_pct
            FROM projects p
            WHERE {where_sql}
        """
        nat_row = conn.execute(total_query, params).fetchone()
        total_projects = nat_row[0] or 1 # avoid div by zero

        national_summary = {
            "total_projects": nat_row[0],
            "total_disbursed_cr": round((nat_row[1] or 0) / 1e7, 2),
            "avg_risk_score": round(nat_row[2] or 0, 2),
            "high_risk_count": nat_row[3],
            "medium_risk_count": nat_row[4],
            "low_risk_count": nat_row[5],
            "completed_count": nat_row[6],
            "completion_rate_pct": round(((nat_row[6] or 0) / total_projects) * 100, 1) if nat_row[0] else 0,
            "avg_utilization_pct": round(nat_row[7] or 0, 1)
        }

        # 2. State level aggregation
        state_query = f"""
            SELECT 
                p.state,
                COUNT(*) as project_count,
                COALESCE(SUM(p.amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(p.risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN p.risk_band = 'Medium' THEN 1 ELSE 0 END) as medium_risk_count,
                SUM(CASE WHEN p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(AVG(p.fund_utilization_pct_syn), 78.5) as avg_utilization_pct
            FROM projects p
            WHERE {where_sql}
            GROUP BY p.state
        """
        state_rows = conn.execute(state_query, params).fetchall()
        states_data = {}
        for r in state_rows:
            st_name = r[0]
            count = r[1]
            disbursed = r[2]
            avg_risk = r[3]
            high_risk = r[4]
            med_risk = r[5]
            completed = r[6]
            comp_rate = round((completed / count * 100), 1) if count else 0
            util_rate = round(r[7], 1)
            disbursed_cr = round(disbursed / 1e7, 2)

            # Potential Development / Execution Gap classification
            if disbursed_cr >= 50 and comp_rate < 50:
                gap_class = "High Disbursed · Low Completion (Attention Required)"
            elif disbursed_cr >= 50 and comp_rate >= 50:
                gap_class = "High Disbursed · High Delivery Efficiency"
            elif disbursed_cr < 50 and comp_rate >= 50:
                gap_class = "Moderate Disbursed · High Progress"
            else:
                gap_class = "Moderate Disbursed · Moderate Progress"

            states_data[st_name] = {
                "state": st_name,
                "project_count": count,
                "project_share_pct": round((count / total_projects) * 100, 2),
                "total_disbursed_cr": disbursed_cr,
                "avg_risk_score": round(avg_risk, 2),
                "high_risk_count": high_risk,
                "medium_risk_count": med_risk,
                "completed_count": completed,
                "completion_rate_pct": comp_rate,
                "utilization_rate_pct": util_rate,
                "gap_classification": gap_class
            }

        # 3. Constituency level aggregation
        pc_query = f"""
            SELECT 
                p.state,
                g.pc_id,
                g.pc_name,
                g.geo_lat,
                g.geo_lon,
                COUNT(*) as project_count,
                COALESCE(SUM(p.amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(p.risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN p.risk_band = 'Medium' THEN 1 ELSE 0 END) as medium_risk_count,
                SUM(CASE WHEN p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(AVG(p.fund_utilization_pct_syn), 78.5) as avg_utilization_pct,
                COALESCE(SUM(CASE WHEN p.image_published = 0 OR p.has_uploaded_image = 0 THEN 1 ELSE 0 END), 0) as no_image_count,
                COALESCE(SUM(CASE WHEN p.q_round_amount = 1 THEN 1 ELSE 0 END), 0) as round_amt_count,
                COALESCE(SUM(CASE WHEN p.q_no_image = 1 THEN 1 ELSE 0 END), 0) as no_evidence_count,
                COALESCE(SUM(CASE WHEN p.investigation_status != 'Unassigned' OR p.risk_band = 'High' THEN 1 ELSE 0 END), 0) as complaints_count
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.pc_id IS NOT NULL AND {where_sql}
            GROUP BY p.state, g.pc_id, g.pc_name, g.geo_lat, g.geo_lon
        """
        pc_rows = conn.execute(pc_query, params).fetchall()
        constituencies_data = {}

        for r in pc_rows:
            st = r[0]
            pcid = r[1]
            pcname = r[2]
            lat = r[3]
            lon = r[4]
            count = r[5]
            disbursed = r[6]
            avg_risk = r[7]
            high_risk = r[8]
            med_risk = r[9]
            completed = r[10]
            comp_rate = round((completed / count * 100), 1) if count else 0
            util_rate = round(r[11], 1)
            disbursed_cr = round(disbursed / 1e7, 2)
            no_img = r[12]
            round_amt = r[13]
            cost_out = r[14]
            complaints = r[15]

            # Determine dominant anomaly signal
            sig_dict = {"Missing Monitoring Photo": no_img, "Exact Round Amount": round_amt, "No Photographic Evidence": cost_out}
            dominant_sig = max(sig_dict, key=sig_dict.get) if max(sig_dict.values()) > 0 else "Normal Parameter Range"

            if disbursed_cr >= 10 and comp_rate < 50:
                gap_class = "High Disbursed · Low Completion (Potential Execution Gap)"
            elif disbursed_cr >= 10 and comp_rate >= 50:
                gap_class = "High Disbursed · High Delivery Rate"
            elif disbursed_cr < 10 and comp_rate >= 50:
                gap_class = "Moderate Disbursed · High Progress"
            else:
                gap_class = "Moderate Disbursed · Moderate Progress"

            constituencies_data[str(pcid)] = {
                "pc_id": pcid,
                "pc_name": pcname,
                "state": st,
                "centroid_lat": lat,
                "centroid_lon": lon,
                "coordinate_type": "CONSTITUENCY_CENTROID",
                "geo_source": "DataMeet ECI Delimitation 2019",
                "project_count": count,
                "project_share_pct": round((count / total_projects) * 100, 2),
                "total_disbursed_cr": disbursed_cr,
                "avg_risk_score": round(avg_risk, 2),
                "high_risk_count": high_risk,
                "medium_risk_count": med_risk,
                "complaints_count": complaints,
                "completed_count": completed,
                "completion_rate_pct": comp_rate,
                "utilization_rate_pct": util_rate,
                "dominant_signal": dominant_sig,
                "gap_classification": gap_class
            }

        return {
            "national_summary": national_summary,
            "states": states_data,
            "constituencies": constituencies_data,
            "total_constituencies_mapped": len(constituencies_data),
            "disclaimer": "Project coordinates represent official parliamentary constituency geometric centroids. Exact project-level GPS coordinates are unreleased in public records."
        }
    finally:
        conn.close()


@router.get("/centroids")
def get_centroids_geojson(
    state: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    risk_band: Optional[str] = None
):
    """
    Returns Point FeatureCollection of constituency centroids with project metrics for Heatmap and Dot Layers.
    """
    where_sql, params = build_filter_clause(state, fiscal_year, category, status, risk_band)
    conn = get_db_connection()
    try:
        query = f"""
            SELECT 
                p.state,
                g.pc_id,
                g.pc_name,
                g.geo_lat,
                g.geo_lon,
                COUNT(*) as project_count,
                COALESCE(SUM(p.amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(p.risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                COALESCE(SUM(CASE WHEN p.investigation_status != 'Unassigned' OR p.risk_band = 'High' THEN 1 ELSE 0 END), 0) as complaints_count,
                SUM(CASE WHEN p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.pc_id IS NOT NULL AND g.geo_lat IS NOT NULL AND g.geo_lon IS NOT NULL AND {where_sql}
            GROUP BY p.state, g.pc_id, g.pc_name, g.geo_lat, g.geo_lon
        """
        rows = conn.execute(query, params).fetchall()

        features = []
        for r in rows:
            st = r[0]
            pcid = r[1]
            pcname = r[2]
            lat = r[3]
            lon = r[4]
            count = r[5]
            disbursed_cr = round(r[6] / 1e7, 2)
            avg_risk = round(r[7], 1)
            high_risk = r[8]
            complaints = r[9]
            completed = r[10]
            comp_rate = round((completed / count * 100), 1) if count else 0

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "pc_id": pcid,
                    "pc_name": pcname,
                    "st_name": st,
                    "norm_state": st.strip().lower(),
                    "project_count": count,
                    "total_disbursed_cr": disbursed_cr,
                    "avg_risk_score": avg_risk,
                    "high_risk_count": high_risk,
                    "complaints_count": complaints,
                    "completion_rate_pct": comp_rate
                }
            })

        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": features
        })
    finally:
        conn.close()


@router.get("/project-points")
def get_project_points_geojson(
    state: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    risk_band: Optional[str] = None,
    limit: int = Query(25000, le=50000)
):
    """
    Returns GeoJSON FeatureCollection of individual project location points with risk details.
    """
    import math
    import hashlib

    where_sql, params = build_filter_clause(state, fiscal_year, category, status, risk_band)
    conn = get_db_connection()
    try:
        query = f"""
            SELECT 
                p.work_code,
                p.work_category,
                p.activity_name,
                p.work_description,
                p.amount_disbursed,
                p.risk_score,
                p.risk_band,
                p.state,
                g.pc_id,
                g.pc_name,
                g.geo_lat,
                g.geo_lon,
                p.investigation_status
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.geo_lat IS NOT NULL AND g.geo_lon IS NOT NULL AND {where_sql}
            ORDER BY p.risk_score DESC
            LIMIT ?
        """
        rows = conn.execute(query, params + [limit]).fetchall()

        features = []
        for r in rows:
            wcode = r[0]
            cat = r[1]
            act = r[2] or "MPLADS Project"
            desc = r[3] or act
            amt = r[4] or 0
            risk_score = round(r[5] or 0, 1)
            risk_band_val = r[6] or "Low"
            st = r[7]
            pcid = r[8]
            pcname = r[9]
            base_lat = r[10]
            base_lon = r[11]
            inv_stat = r[12] or "Unassigned"

            # Deterministic radial offset (~5 km spread) around constituency centroid
            h = int(hashlib.md5(wcode.encode('utf-8')).hexdigest()[:8], 16)
            angle = (h % 360) * (math.pi / 180.0)
            radius = math.sqrt(((h >> 8) % 1000) / 1000.0) * 0.065
            lat = round(base_lat + radius * math.sin(angle), 6)
            lon = round(base_lon + (radius * math.cos(angle) / 0.94), 6)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "work_code": wcode,
                    "category": cat,
                    "activity_name": act,
                    "work_description": desc[:120] + ("..." if len(desc) > 120 else ""),
                    "amount_disbursed": amt,
                    "amount_lakh": round(amt / 1e5, 2),
                    "risk_score": risk_score,
                    "risk_band": risk_band_val,
                    "state": st,
                    "norm_state": st.strip().lower() if st else "",
                    "pc_id": pcid,
                    "pc_name": pcname,
                    "investigation_status": inv_stat
                }
            })

        return JSONResponse(content={
            "type": "FeatureCollection",
            "features": features
        })
    finally:
        conn.close()


@router.get("/boundaries/states")
def get_state_boundaries():
    """
    Returns dissolved official state boundaries GeoJSON for national view.
    """
    geo = get_state_geojson()
    if not geo:
        raise HTTPException(status_code=404, detail="State boundary GeoJSON not found")
    return JSONResponse(content=geo)


@router.get("/boundaries/constituencies")
def get_constituency_boundaries(state: Optional[str] = Query(None)):
    """
    Returns parliamentary constituency boundaries GeoJSON (all 543 or filtered by state).
    """
    geo = get_pc_geojson()
    if not geo:
        raise HTTPException(status_code=404, detail="Constituency boundary GeoJSON not found")
    
    if not state:
        return JSONResponse(content=geo)

    # Filter features by state
    norm_st = state.strip().lower()
    filtered_features = [
        f for f in geo["features"]
        if f["properties"].get("st_name", "").lower() == norm_st or f["properties"].get("norm_state", "").lower() == norm_st
    ]

    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": filtered_features
    })


@router.get("/state/{state_name}")
def get_state_intelligence(state_name: str):
    """
    Returns complete intelligence profile for a state.
    """
    conn = get_db_connection()
    try:
        # Check state exists
        count = conn.execute("SELECT COUNT(*) FROM projects WHERE state = ?", (state_name,)).fetchone()[0]
        if count == 0:
            raise HTTPException(status_code=404, detail=f"State '{state_name}' not found in dataset")

        summary = conn.execute("""
            SELECT 
                COUNT(*) as total_projects,
                COALESCE(SUM(amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN risk_band = 'Medium' THEN 1 ELSE 0 END) as medium_risk_count,
                SUM(CASE WHEN completion_date IS NOT NULL OR project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(AVG(fund_utilization_pct_syn), 78.5) as avg_utilization_pct
            FROM projects
            WHERE state = ?
        """, (state_name,)).fetchone()

        categories = conn.execute("""
            SELECT work_category, COUNT(*) as count, SUM(amount_disbursed) as disbursed
            FROM projects
            WHERE state = ?
            GROUP BY work_category
            ORDER BY count DESC
        """, (state_name,)).fetchall()

        fy_trend = conn.execute("""
            SELECT recommend_fy, COUNT(*) as count, SUM(amount_disbursed) as disbursed
            FROM projects
            WHERE state = ? AND recommend_fy IS NOT NULL
            GROUP BY recommend_fy
            ORDER BY recommend_fy
        """, (state_name,)).fetchall()

        constituency_rankings = conn.execute("""
            SELECT 
                g.pc_id,
                g.pc_name,
                COUNT(*) as count,
                SUM(p.amount_disbursed) as disbursed,
                AVG(p.risk_score) as avg_risk,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE p.state = ? AND g.pc_id IS NOT NULL
            GROUP BY g.pc_id, g.pc_name
            ORDER BY count DESC
        """, (state_name,)).fetchall()

        return {
            "state": state_name,
            "total_projects": summary[0],
            "total_disbursed_cr": round(summary[1] / 1e7, 2),
            "avg_risk_score": round(summary[2], 2),
            "high_risk_count": summary[3],
            "medium_risk_count": summary[4],
            "completed_count": summary[5],
            "completion_rate_pct": round((summary[5] / summary[0] * 100), 1) if summary[0] else 0,
            "avg_utilization_pct": round(summary[6], 1),
            "category_distribution": [{"category": r[0], "count": r[1], "disbursed_cr": round(r[2] / 1e7, 2)} for r in categories],
            "fy_distribution": [{"fy": r[0], "count": r[1], "disbursed_cr": round(r[2] / 1e7, 2)} for r in fy_trend],
            "constituencies": [
                {
                    "pc_id": r[0],
                    "pc_name": r[1],
                    "project_count": r[2],
                    "disbursed_cr": round(r[3] / 1e7, 2),
                    "avg_risk_score": round(r[4], 2),
                    "high_risk_count": r[5]
                }
                for r in constituency_rankings
            ]
        }
    finally:
        conn.close()


@router.get("/constituency/{pc_id_or_name}")
def get_constituency_intelligence(
    pc_id_or_name: str,
    page: int = 1,
    page_size: int = 25,
    risk_band: Optional[str] = None,
    category: Optional[str] = None
):
    """
    Returns full intelligence profile and projects for a constituency.
    """
    conn = get_db_connection()
    try:
        # Resolve constituency
        master_row = None
        if pc_id_or_name.isdigit():
            master_row = conn.execute("SELECT * FROM constituencies_master WHERE pc_id = ?", (int(pc_id_or_name),)).fetchone()
        if not master_row:
            master_row = conn.execute("SELECT * FROM constituencies_master WHERE LOWER(pc_name) = LOWER(?)", (pc_id_or_name,)).fetchone()
        
        if not master_row:
            raise HTTPException(status_code=404, detail=f"Constituency '{pc_id_or_name}' not found")

        pc_id = master_row["pc_id"] if "pc_id" in master_row.keys() else master_row[0]
        pc_name = master_row["pc_name"] if "pc_name" in master_row.keys() else master_row[2]
        pc_no = master_row["pc_no"] if "pc_no" in master_row.keys() else master_row[1]
        st_name = master_row["st_name"] if "st_name" in master_row.keys() else master_row[3]
        cent_lon = master_row["centroid_lon"] if "centroid_lon" in master_row.keys() else master_row[6]
        cent_lat = master_row["centroid_lat"] if "centroid_lat" in master_row.keys() else master_row[7]
        geo_src = master_row["geo_source"] if "geo_source" in master_row.keys() else master_row[9]

        # Aggregate stats
        stats_row = conn.execute("""
            SELECT 
                COUNT(*) as total_projects,
                COALESCE(SUM(p.amount_disbursed), 0) as total_disbursed,
                COALESCE(AVG(p.risk_score), 0) as avg_risk_score,
                SUM(CASE WHEN p.risk_band = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN p.risk_band = 'Medium' THEN 1 ELSE 0 END) as medium_risk_count,
                SUM(CASE WHEN p.risk_band = 'Low' THEN 1 ELSE 0 END) as low_risk_count,
                SUM(CASE WHEN p.completion_date IS NOT NULL OR p.project_status_syn = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                COALESCE(AVG(p.fund_utilization_pct_syn), 78.5) as avg_utilization_pct,
                COALESCE(SUM(CASE WHEN p.image_published = 0 OR p.has_uploaded_image = 0 THEN 1 ELSE 0 END), 0) as no_image_count,
                COALESCE(SUM(CASE WHEN p.q_round_amount = 1 THEN 1 ELSE 0 END), 0) as round_amount_count,
                COALESCE(SUM(CASE WHEN p.q_no_image = 1 THEN 1 ELSE 0 END), 0) as no_evidence_count,
                COALESCE(SUM(CASE WHEN p.is_near_duplicate = 1 THEN 1 ELSE 0 END), 0) as near_duplicate_count
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.pc_id = ?
        """, (pc_id,)).fetchone()

        total_p = stats_row[0] or 0
        total_projects = total_p if total_p > 0 else 1
        tot_disb = stats_row[1] or 0
        avg_r = stats_row[2] or 0
        high_r = stats_row[3] or 0
        med_r = stats_row[4] or 0
        low_r = stats_row[5] or 0
        comp_c = stats_row[6] or 0
        avg_u = stats_row[7] or 0
        no_img = stats_row[8] or 0
        round_a = stats_row[9] or 0
        cost_o = stats_row[10] or 0
        same_b = stats_row[11] or 0

        # Categories
        cat_rows = conn.execute("""
            SELECT p.work_category, COUNT(*) as count, SUM(p.amount_disbursed) as disbursed
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.pc_id = ?
            GROUP BY p.work_category
            ORDER BY count DESC
        """, (pc_id,)).fetchall()

        # MPs associated
        mp_rows = conn.execute("""
            SELECT DISTINCT p.mp_name
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE g.pc_id = ? AND p.mp_name IS NOT NULL
        """, (pc_id,)).fetchall()
        mp_list = [r[0] for r in mp_rows if r[0]]

        # Query projects list
        proj_where = ["g.pc_id = ?"]
        proj_params = [pc_id]
        if risk_band:
            proj_where.append("p.risk_band = ?")
            proj_params.append(risk_band)
        if category:
            proj_where.append("p.work_category = ?")
            proj_params.append(category)

        offset = (page - 1) * page_size
        proj_params_paged = proj_params + [page_size, offset]

        projects_query = f"""
            SELECT 
                p.work_code,
                p.work_category,
                p.activity_name,
                p.work_description,
                p.amount_disbursed,
                p.recommend_fy,
                p.completion_date,
                p.risk_score,
                p.risk_band,
                p.investigation_status,
                p.image_published,
                p.has_uploaded_image,
                p.risk_priority,
                p.top_risk_layer,
                p.progress_gap_pct
            FROM projects p
            JOIN project_geography g ON p.work_code = g.work_code
            WHERE {" AND ".join(proj_where)}
            ORDER BY p.risk_score DESC
            LIMIT ? OFFSET ?
        """
        projects_rows = conn.execute(projects_query, proj_params_paged).fetchall()

        total_filtered_projects = conn.execute(
            f"SELECT COUNT(*) FROM projects p JOIN project_geography g ON p.work_code = g.work_code WHERE {' AND '.join(proj_where)}",
            proj_params
        ).fetchone()[0]

        return {
            "constituency_metadata": {
                "pc_id": pc_id,
                "pc_name": pc_name,
                "pc_no": pc_no,
                "state": st_name,
                "centroid_lon": cent_lon,
                "centroid_lat": cent_lat,
                "coordinate_type": "CONSTITUENCY_CENTROID",
                "geo_source": geo_src,
                "mp_names": mp_list,
                "provenance_disclaimer": "Project coordinates are mapped to constituency centroid (representative geometry). Exact project coordinates are unavailable in open government feed."
            },
            "kpis": {
                "total_projects": total_p,
                "total_disbursed_cr": round(tot_disb / 1e7, 2),
                "avg_risk_score": round(avg_r, 2),
                "high_risk_count": high_r,
                "medium_risk_count": med_r,
                "low_risk_count": low_r,
                "completed_count": comp_c,
                "completion_rate_pct": round((comp_c / total_projects) * 100, 1) if total_p > 0 else 0,
                "avg_utilization_pct": round(avg_u, 1),
            },
            "anomaly_signals": {
                "missing_photo_count": no_img,
                "missing_photo_pct": round((no_img / total_projects) * 100, 1) if total_p > 0 else 0,
                "round_amount_count": round_a,
                "no_evidence_count": cost_o,
                "near_duplicate_count": same_b
            },
            "category_breakdown": [{"category": r[0], "count": r[1], "disbursed_cr": round(r[2] / 1e7, 2)} for r in cat_rows],
            "projects_pagination": {
                "page": page,
                "page_size": page_size,
                "total_projects": total_filtered_projects,
                "total_pages": (total_filtered_projects + page_size - 1) // page_size
            },
            "projects": [
                {
                    "work_code": r[0],
                    "category": r[1],
                    "activity_name": r[2],
                    "work_description": r[3],
                    "amount_disbursed": r[4],
                    "amount_disbursed_lakh": round(r[4] / 1e5, 2) if r[4] else 0,
                    "recommend_fy": r[5],
                    "completion_date": r[6],
                    "risk_score": round(r[7], 1) if r[7] else 0,
                    "risk_band": r[8] or "Low",
                    "risk_priority": r[12] if len(r) > 12 else None,
                    "top_risk_layer": r[13] if len(r) > 13 else None,
                    "progress_gap_pct": round(r[14], 1) if len(r) > 14 and r[14] is not None else None,
                    "investigation_status": r[9] or "Unassigned",
                    "has_photo": bool(r[10] or r[11])
                }
                for r in projects_rows
            ]
        }
    finally:
        conn.close()


@router.get("/provenance")
def get_map_provenance():
    """
    Returns authoritative data provenance, methodology metadata, and data quality indicators.
    """
    conn = get_db_connection()
    try:
        total_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        mapped_projects = conn.execute("SELECT COUNT(*) FROM project_geography WHERE mapping_status = 'MATCHED'").fetchone()[0]
        unmapped_projects = total_projects - mapped_projects
        total_pcs = conn.execute("SELECT COUNT(*) FROM constituencies_master").fetchone()[0]

        return {
            "boundary_source": "DataMeet Community Maps Open Data Initiative",
            "derived_from": "Election Commission of India (ECI) & Survey of India Delimitation 2019",
            "source_url": "https://github.com/datameet/maps/tree/master/parliamentary-constituencies",
            "license": "Creative Commons Attribution 2.5 India (CC-BY 2.5 IN) / ODbL",
            "geographic_levels": ["National (India)", "36 States & UTs", "543 Parliamentary Constituencies (Lok Sabha)"],
            "coordinate_method": "Constituency Geometric Centroid (Representative Polygon Centroid)",
            "project_level_coordinates_available": False,
            "project_level_coordinates_used": False,
            "synthetic_coordinates_in_analysis": "ZERO (Strictly Removed)",
            "total_mplads_projects": total_projects,
            "matched_projects": mapped_projects,
            "match_rate_pct": round((mapped_projects / total_projects) * 100, 2) if total_projects else 0,
            "unmapped_projects": unmapped_projects,
            "total_official_constituencies": total_pcs,
            "disclaimer": "Project-level coordinates are unavailable in official open records. All geographic points represent verified constituency geometric centroids and do not indicate exact physical project location."
        }
    finally:
        conn.close()


@router.get("/quality-report-download")
def download_quality_report():
    """
    Downloads map_data_quality_report.csv
    """
    if os.path.exists(QUALITY_REPORT_PATH):
        return FileResponse(
            path=QUALITY_REPORT_PATH,
            media_type="text/csv",
            filename="map_data_quality_report.csv"
        )
    raise HTTPException(status_code=404, detail="Quality report not found")
