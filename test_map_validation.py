import sqlite3
import pandas as pd
import json
import os
from backend.app.map_api import get_map_summary, get_map_provenance

def run_tests():
    conn = sqlite3.connect('mplads_prototype.db')

    # 1. Reconcile total projects
    total_proj = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    mapped_proj = conn.execute("SELECT COUNT(*) FROM project_geography WHERE mapping_status = 'MATCHED'").fetchone()[0]
    unmapped_proj = conn.execute("SELECT COUNT(*) FROM project_geography WHERE mapping_status != 'MATCHED'").fetchone()[0]
    print(f"1. Total projects in DB: {total_proj} | Mapped: {mapped_proj} | Unmapped: {unmapped_proj}")
    assert total_proj == mapped_proj + unmapped_proj, "Project totals mismatch!"

    # 2. Check synthetic coordinates in geographic tables
    null_syn = conn.execute("SELECT COUNT(*) FROM project_geography WHERE coordinate_type != 'CONSTITUENCY_CENTROID' AND mapping_status = 'MATCHED'").fetchone()[0]
    print(f"2. Non-centroid coords in matched projects: {null_syn} (Must be 0)")
    assert null_syn == 0

    # 3. Check bounding boxes / Centroids inside India geographic bounds [6°N to 38°N, 68°E to 98°E]
    invalid_coords = conn.execute("""
        SELECT COUNT(*) FROM constituencies_master 
        WHERE centroid_lat < 6.0 OR centroid_lat > 38.0 OR centroid_lon < 68.0 OR centroid_lon > 98.0
    """).fetchone()[0]
    print(f"3. Constituencies outside India geographic bounding box: {invalid_coords} (Must be 0)")
    assert invalid_coords == 0

    # 4. Check state association integrity
    orphan_pcs = conn.execute("""
        SELECT COUNT(*) FROM project_geography g
        JOIN constituencies_master c ON g.pc_id = c.pc_id
        JOIN projects p ON g.work_code = p.work_code
        WHERE LOWER(p.state) = 'kerala' AND LOWER(c.st_name) != 'kerala'
    """).fetchone()[0]
    print(f"4. Cross-state mismatch for sample state (Kerala): {orphan_pcs} (Must be 0)")
    assert orphan_pcs == 0

    # 5. Check quality report file exists and columns
    q_df = pd.read_csv('map_data_quality_report.csv')
    print(f"5. Quality report entries: {len(q_df)} | Columns: {list(q_df.columns)}")
    req_cols = ['geographic_entity', 'state', 'constituency', 'mapping_status', 'coordinate_type', 'geo_source', 'validation_status', 'reason']
    for col in req_cols:
        assert col in q_df.columns, f"Missing required column {col}"

    # 6. Check summary API reconciliation with raw queries
    summary = get_map_summary()
    nat = summary['national_summary']
    print(f"6. Summary API Totals: Projects={nat['total_projects']}, Disbursed=INR {nat['total_disbursed_cr']} Cr, HighRisk={nat['high_risk_count']}")
    raw_disbursed = conn.execute("SELECT SUM(amount_disbursed) FROM projects").fetchone()[0] / 1e7
    raw_high_risk = conn.execute("SELECT COUNT(*) FROM projects WHERE risk_band = 'High'").fetchone()[0]
    assert abs(nat['total_disbursed_cr'] - round(raw_disbursed, 2)) < 0.05
    assert nat['high_risk_count'] == raw_high_risk

    # 7. Check Provenance
    prov = get_map_provenance()
    print(f"7. Provenance Report: Boundary={prov['boundary_source']} | Delimitation={prov['derived_from']} | MatchRate={prov['match_rate_pct']}%")
    assert prov['match_rate_pct'] == 100.0

    conn.close()
    print("\n>>> ALL VALIDATION CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == '__main__':
    run_tests()
