"""
MPLADS Sentinel - database bootstrap
====================================

    python init_db.py

Steps
  1. Load the enriched prototype dataset into SQLite.
  2. Build the geography table from the official ECI 2019 boundaries.
  3. Run the six-layer Unified Risk Engine.

Nothing in step 3 reads the legacy d_risk_score / d_risk_band / label_* /
fraud_label columns. They stay in the table only so the UI can show an
independent comparison.
"""

import os
import sqlite3
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mplads_prototype.db")
CSV_PATH = os.path.join(BASE_DIR, "mplads_enriched_prototype_dataset.csv")
GEO_DIR = os.path.join(BASE_DIR, "backend", "app", "geo_data")


def load_projects():
    print("[1/3] Loading enriched dataset...")
    df = pd.read_csv(CSV_PATH)

    # Workflow state lives on the row; the risk engine owns everything else.
    if "investigation_status" not in df.columns:
        df["investigation_status"] = "Unassigned"

    conn = sqlite3.connect(DB_PATH)
    df.to_sql("projects", conn, if_exists="replace", index=False)

    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_projects_work_code ON projects(work_code)",
        "CREATE INDEX IF NOT EXISTS idx_projects_state ON projects(state)",
        "CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(work_category)",
        "CREATE INDEX IF NOT EXISTS idx_projects_fy ON projects(recommend_fy)",
        "CREATE INDEX IF NOT EXISTS idx_projects_activity ON projects(activity_name)",
        "CREATE INDEX IF NOT EXISTS idx_projects_constituency ON projects(constituency)",
    ]:
        conn.execute(stmt)
    conn.commit()
    conn.close()
    print(f"      {len(df):,} works loaded.")


def geography_is_built() -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"project_geography", "constituencies_master"} <= names:
            return False
        return conn.execute("SELECT COUNT(*) FROM project_geography").fetchone()[0] > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def restore_geography_snapshot() -> bool:
    """
    Load the pre-resolved ECI 2019 geography from the committed snapshot.

    Rebuilding geography from the raw boundary files needs shapely + requests,
    which are heavier than the API's runtime dependencies and are not needed
    once the entity resolution has been done. The snapshot is the resolved
    output of `geo_preprocessing.run_preprocessing()`, so the project stays
    fully reproducible on a plain install.
    """
    files = {
        "project_geography": os.path.join(GEO_DIR, "project_geography.csv.gz"),
        "constituencies_master": os.path.join(GEO_DIR, "constituencies_master.csv.gz"),
    }
    if not all(os.path.exists(f) for f in files.values()):
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        for table, path in files.items():
            df = pd.read_csv(path, compression="gzip")
            df.to_sql(table, conn, if_exists="replace", index=False)
            print(f"      restored {table}: {len(df):,} rows")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_geo_work_code "
                     "ON project_geography(work_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_geo_pc_id "
                     "ON project_geography(pc_id)")
        conn.commit()
    finally:
        conn.close()
    return True


def build_geography(force: bool = False):
    """
    Order of preference:
      --rebuild-geo  -> full entity resolution from the ECI boundary files
      already built  -> leave it alone
      otherwise      -> restore the committed snapshot
      last resort    -> full entity resolution (needs shapely + requests)
    """
    if force:
        from backend.app.geo_preprocessing import run_preprocessing
        run_preprocessing()
        return

    if geography_is_built():
        print("      ECI geography already present - skipping "
              "(pass --rebuild-geo to re-resolve from boundary files).")
        return

    if restore_geography_snapshot():
        print("      Restored from the committed ECI 2019 snapshot.")
        return

    try:
        from backend.app.geo_preprocessing import run_preprocessing
    except ImportError as exc:
        print(f"      Skipped: {exc}")
        print("      Install the geo extras to build it: pip install shapely requests")
        print("      WARNING: without geography the map and the spatial layer stay empty.")
        return
    run_preprocessing()


def main():
    force_geo = "--rebuild-geo" in sys.argv

    if not os.path.exists(CSV_PATH):
        sys.exit(f"Dataset not found: {CSV_PATH}")

    load_projects()

    print("[2/3] Geography (official ECI 2019 delimitation)...")
    build_geography(force=force_geo)

    print("[3/3] Running the Unified Risk Engine...")
    from backend.app.risk_engine.build import main as build_risk
    build_risk()

    print("\nReady. Start the API with:")
    print("    uvicorn backend.app.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
