"""
Layer 4 - Spatial Intelligence
==============================

Coordinate policy
-----------------
This layer uses ONLY the coordinates in `project_geography`, which are
official ECI 2019 constituency centroids matched to each work. There are no
invented per-project GPS points anywhere in the risk engine.

The consequence is stated honestly everywhere it is surfaced: two works in
the same constituency share a centroid, so the distance between them is 0 m.
That is evidence of *co-location within a constituency*, not proof of two
works at the same physical site. Layer 4 therefore measures:

    functional overlap  =  semantic similarity
                        x  same activity
                        x  same constituency
                        x  overlapping time period

which is a defensible signal, and it flags constituency-level saturation
(an unusual concentration of one activity in one constituency in one year).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .scoring import score_0_100

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def load_geography(conn) -> pd.DataFrame:
    try:
        geo = pd.read_sql(
            "SELECT work_code, pc_id, pc_name, geo_lat, geo_lon, "
            "coordinate_type, geo_source, mapping_status FROM project_geography",
            conn,
        )
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["work_code", "pc_id", "geo_lat", "geo_lon"])
    geo["geo_lat"] = pd.to_numeric(geo["geo_lat"], errors="coerce")
    geo["geo_lon"] = pd.to_numeric(geo["geo_lon"], errors="coerce")
    return geo


def run(df: pd.DataFrame, neighbours: pd.DataFrame, conn) -> pd.DataFrame:
    geo = load_geography(conn)
    base = df[["work_code", "state", "constituency", "activity_name", "recommend_fy"]].copy()
    base = base.merge(geo, on="work_code", how="left")
    base = base.set_index(df.index)

    out = pd.DataFrame(index=df.index)
    out["pc_id"] = base["pc_id"]
    out["pc_name"] = base["pc_name"]
    out["geo_lat"] = base["geo_lat"]
    out["geo_lon"] = base["geo_lon"]
    out["coordinate_type"] = base["coordinate_type"]
    out["geo_source"] = base["geo_source"]

    # ---------------------------------------------------------------
    # A. Constituency x activity x year saturation
    # ---------------------------------------------------------------
    key = (
        base["constituency"].fillna("?").astype(str) + "|" +
        base["activity_name"].fillna("?").astype(str) + "|" +
        base["recommend_fy"].fillna("?").astype(str)
    )
    cluster_size = key.map(key.value_counts())
    out["constituency_activity_cluster_size"] = cluster_size

    const_total = base["constituency"].fillna("?").map(
        base["constituency"].fillna("?").value_counts()
    )
    out["constituency_activity_share"] = (cluster_size / const_total.replace(0, np.nan)).round(4)

    # ---------------------------------------------------------------
    # B. Functional overlap with semantic neighbours
    # ---------------------------------------------------------------
    lookup = base.reset_index(drop=True)[
        ["work_code", "geo_lat", "geo_lon", "constituency", "recommend_fy"]
    ]
    nb = neighbours.merge(lookup, on="work_code", how="left")
    nb = nb.merge(
        lookup.rename(columns={
            "work_code": "similar_work_code",
            "geo_lat": "nb_lat",
            "geo_lon": "nb_lon",
            "constituency": "nb_constituency",
            "recommend_fy": "nb_fy",
        }),
        on="similar_work_code",
        how="left",
    )

    nb["distance_m"] = haversine_m(
        nb["geo_lat"], nb["geo_lon"], nb["nb_lat"], nb["nb_lon"]
    )
    # Proximity weight: 1.0 inside the same constituency, decaying to 0 by 50 km.
    nb["proximity_weight"] = np.where(
        nb["same_constituency"] == 1,
        1.0,
        np.clip(1.0 - (nb["distance_m"].fillna(1e9) / 50_000.0), 0.0, 1.0),
    )
    nb["same_fy"] = (nb["recommend_fy"] == nb["nb_fy"]).astype(int)
    nb["overlap_score"] = (
        nb["similarity"]
        * nb["proximity_weight"]
        * np.where(nb["same_activity"] == 1, 1.0, 0.55)
        * np.where(nb["same_fy"] == 1, 1.0, 0.75)
    )

    agg = nb.groupby("work_code").agg(
        spatial_overlap_score=("overlap_score", "max"),
        nearest_similar_distance_m=("distance_m", "min"),
        nearby_similar_project_count=(
            "overlap_score",
            lambda s: int((s >= config.SPATIAL_OVERLAP_SIM_THRESHOLD).sum()),
        ),
    )

    codes = df["work_code"]
    for col in ["spatial_overlap_score", "nearest_similar_distance_m", "nearby_similar_project_count"]:
        out[col] = codes.map(agg[col]).astype(float)

    out["spatial_overlap_score"] = out["spatial_overlap_score"].fillna(0).round(4)
    out["nearby_similar_project_count"] = out["nearby_similar_project_count"].fillna(0).astype(int)

    # ---------------------------------------------------------------
    # C. Combine
    # ---------------------------------------------------------------
    saturation = (score_0_100(cluster_size) / 100.0)
    overlap = out["spatial_overlap_score"].clip(0, 1)
    raw = (0.70 * overlap) + (0.30 * saturation)
    out["spatial_risk_raw"] = raw.round(4)
    out["spatial_risk"] = score_0_100(raw)

    out["spatial_resolution_note"] = config.SPATIAL_RESOLUTION_NOTE
    return out
