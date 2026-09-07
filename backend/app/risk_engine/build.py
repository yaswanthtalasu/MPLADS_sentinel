"""
Risk Engine build step
======================

Run after init_db.py has loaded the enriched dataset:

    python -m backend.app.risk_engine.build

Optional:
    MPLADS_EMBEDDING_BACKEND=sbert  python -m backend.app.risk_engine.build

Writes four tables and leaves the source `projects` table untouched apart
from a small set of engine-owned columns that the map API reads.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import pandas as pd

from . import config
from .engine import RISK_TABLE_COLUMNS, compute

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "mplads_prototype.db")

# Columns mirrored onto `projects` so existing map queries keep working.
MIRROR_COLUMNS = [
    ("risk_score", "REAL"),
    ("risk_band", "TEXT"),
    ("risk_priority", "TEXT"),
    ("top_risk_layer", "TEXT"),
    ("q_round_amount", "INTEGER"),
    ("q_no_image", "INTEGER"),
    ("q_thin_description", "INTEGER"),
    ("is_near_duplicate", "INTEGER"),
    ("progress_gap_pct", "REAL"),
    ("fund_utilization_pct", "REAL"),
    ("physical_progress_pct", "REAL"),
]


def _ensure_columns(conn, table, columns):
    existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    for name, sqltype in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}")


def write_results(conn, scored: pd.DataFrame, neighbours: pd.DataFrame, backend: str):
    cols = [c for c in RISK_TABLE_COLUMNS if c in scored.columns]
    scored[cols].to_sql("risk_scores", conn, if_exists="replace", index=False)
    neighbours.to_sql("project_similarity", conn, if_exists="replace", index=False)

    peer = (
        scored.groupby(["peer_key", "peer_level"], as_index=False)
        .agg(
            peer_n=("work_code", "count"),
            median_cost_inr=("peer_median_cost_inr", "first"),
            median_progress=("peer_median_progress", "first"),
            median_utilization=("peer_median_utilization", "first"),
            median_delay=("peer_median_delay", "first"),
            mean_risk_score=("risk_score", "mean"),
            high_risk_count=("risk_band", lambda s: int((s == "High").sum())),
        )
    )
    peer.to_sql("peer_benchmarks", conn, if_exists="replace", index=False)

    meta = pd.DataFrame([{
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_projects": len(scored),
        "embedding_backend": backend,
        "layer_weights": json.dumps(config.LAYER_WEIGHTS),
        "band_thresholds": json.dumps(config.BAND_THRESHOLDS),
        "score_curve": config.SCORE_CURVE,
        "min_peer_group_size": config.MIN_PEER_GROUP_SIZE,
        "excluded_leakage_columns": json.dumps(config.LEAKAGE_TARGET_COLUMNS),
        "leakage_prefixes": json.dumps(list(config.LEAKAGE_PREFIXES)),
        "spatial_resolution_note": config.SPATIAL_RESOLUTION_NOTE,
        "supervised": 0,
        "note": ("Unsupervised anomaly detection and transparent rule-based scoring. "
                 "fraud_label is UNAVAILABLE for every row in the source data, so no "
                 "supervised fraud classifier is claimed or trained."),
    }])
    meta.to_sql("risk_engine_meta", conn, if_exists="replace", index=False)

    _ensure_columns(conn, "projects", MIRROR_COLUMNS)
    mirror_cols = [c for c, _ in MIRROR_COLUMNS if c in scored.columns]
    conn.execute("DROP TABLE IF EXISTS _mirror")
    scored[["work_code"] + mirror_cols].to_sql("_mirror", conn, if_exists="replace", index=False)
    # Without this index the correlated UPDATE below degenerates into a full
    # scan of _mirror per column per row (34k x 11 x 34k) and never finishes.
    conn.execute("CREATE UNIQUE INDEX idx_mirror_wc ON _mirror(work_code)")
    set_list = ", ".join(mirror_cols)
    select_list = ", ".join(f"m.{c}" for c in mirror_cols)
    conn.execute(
        f"UPDATE projects SET ({set_list}) = "
        f"(SELECT {select_list} FROM _mirror m WHERE m.work_code = projects.work_code)"
    )
    conn.execute("DROP TABLE _mirror")

    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_risk_work_code ON risk_scores(work_code)",
        "CREATE INDEX IF NOT EXISTS idx_risk_score ON risk_scores(risk_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_risk_band2 ON risk_scores(risk_band)",
        "CREATE INDEX IF NOT EXISTS idx_sim_work_code ON project_similarity(work_code)",
        "CREATE INDEX IF NOT EXISTS idx_peer_key ON peer_benchmarks(peer_key)",
        "CREATE INDEX IF NOT EXISTS idx_projects_risk_band_new ON projects(risk_band)",
        "CREATE INDEX IF NOT EXISTS idx_projects_risk_score_new ON projects(risk_score)",
    ]:
        conn.execute(stmt)
    conn.commit()


def validate(conn, scored: pd.DataFrame):
    """
    Sanity check, not an accuracy claim.

    The dataset carries `synthetic_scenario_for_validation` - deliberately
    injected unusual cases. If the engine works, those rows should score
    higher on average than 'normal' rows. This is a smoke test of the
    detector, NOT evidence that it detects real fraud.
    """
    try:
        truth = pd.read_sql(
            "SELECT work_code, synthetic_scenario_for_validation AS scenario FROM projects",
            conn,
        )
    except Exception:  # noqa: BLE001
        return None
    m = scored[["work_code", "risk_score", "risk_band"]].merge(truth, on="work_code")
    summary = (
        m.groupby("scenario")
        .agg(
            n=("work_code", "count"),
            mean_risk=("risk_score", "mean"),
            pct_flagged_med_or_high=("risk_band", lambda s: 100.0 * (s != "Low").mean()),
        )
        .round(2)
        .sort_values("mean_risk", ascending=False)
    )
    summary.to_sql("validation_scenario_summary", conn, if_exists="replace")
    return summary


def main():
    if not os.path.exists(DB_PATH):
        sys.exit(f"Database not found at {DB_PATH}. Run init_db.py first.")

    t0 = time.time()
    print("=" * 68)
    print("MPLADS SENTINEL - UNIFIED RISK ENGINE BUILD")
    print("=" * 68)
    print(f"database : {DB_PATH}")
    print("policy   : strict - no d_* / *_loo / label_* column reaches a model")
    print("-" * 68)

    conn = sqlite3.connect(DB_PATH)
    try:
        result = compute(conn)
        scored = result["scored"]
        neighbours = result["neighbours"]
        backend = result["backend"]

        print("-" * 68)
        print("Risk band distribution:")
        for band, n in scored["risk_band"].value_counts().items():
            print(f"   {band:<8} {n:>7,}  ({100 * n / len(scored):5.2f}%)")
        print("\nMean layer scores:")
        for layer in config.LAYER_WEIGHTS:
            print(f"   {config.LAYER_LABELS[layer]:<22} {scored[layer].mean():6.2f}")

        print("\nWriting tables...")
        write_results(conn, scored, neighbours, backend)

        summary = validate(conn, scored)
        if summary is not None:
            print("\nValidation smoke test (injected scenarios should outrank 'normal'):")
            print(summary.to_string())

        print("-" * 68)
        print(f"Done in {time.time() - t0:.1f}s")
        print("Tables written: risk_scores, project_similarity, peer_benchmarks,")
        print("                risk_engine_meta, validation_scenario_summary")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
