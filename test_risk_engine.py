"""
Risk engine regression tests
============================

    python test_risk_engine.py        (after python init_db.py)

These check the properties the engine is *claimed* to have, which is what a
jury will actually probe: that no legacy risk artefact reaches a model, that
scores and weights are well-formed, that every flagged work carries an
explanation, and that the injected validation scenarios rank above normal.
"""

import json
import sqlite3
import sys

import pandas as pd

from backend.app.risk_engine import config

DB = "mplads_prototype.db"
FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}{(' - ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(name)


def main():
    conn = sqlite3.connect(DB)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "risk_scores" not in tables:
        sys.exit("Risk engine not built. Run: python init_db.py")

    risk = pd.read_sql("SELECT * FROM risk_scores", conn)
    layers = list(config.LAYER_WEIGHTS)

    print("\n1. Anti-leakage policy")
    for col in ["d_risk_score", "d_risk_band", "label_rule_band", "fraud_label",
                "d_sig_cost_outlier", "d_peer_robust_z", "ida_mean_risk_loo"]:
        check(f"{col} is blocked", config.is_leaky(col))
    for col in ["amount_disbursed", "work_description", "state", "has_uploaded_image"]:
        check(f"{col} is allowed", not config.is_leaky(col))
    check("no leaky column persisted in risk_scores",
          not [c for c in risk.columns if config.is_leaky(c)])

    print("\n2. Score integrity")
    check("weights sum to 1.0", abs(sum(config.LAYER_WEIGHTS.values()) - 1.0) < 1e-9)
    check("every work scored", len(risk) == pd.read_sql(
        "SELECT COUNT(*) n FROM projects", conn).n[0])
    check("unified score in [0, 100]",
          risk.risk_score.between(0, 100).all(),
          f"min={risk.risk_score.min():.1f} max={risk.risk_score.max():.1f}")
    for layer in layers:
        check(f"{layer} in [0, 100]", risk[layer].between(0, 100).all())
    check("no null scores", risk.risk_score.notna().all())

    recomputed = sum(risk[l] * w for l, w in config.LAYER_WEIGHTS.items())
    check("unified score equals the weighted fusion",
          (recomputed - risk.risk_score).abs().max() < 0.02)

    print("\n3. Bands and priorities")
    check("bands are the expected set",
          set(risk.risk_band) <= {"High", "Medium", "Low"})
    check("High band means score >= 70", risk.loc[risk.risk_band == "High", "risk_score"].min() >= 70)
    check("Low band means score < 45", risk.loc[risk.risk_band == "Low", "risk_score"].max() < 45)
    check("triage funnel is workable (High under 2%)",
          (risk.risk_band == "High").mean() < 0.02,
          f"{(risk.risk_band == 'High').mean() * 100:.2f}% High")

    print("\n4. Explainability")
    flagged = risk[risk.risk_band != "Low"]
    reason_counts = flagged.risk_reasons.map(lambda r: len(json.loads(r)))
    check("every flagged work has at least one reason", (reason_counts > 0).all())
    check("every flagged work has a summary line", flagged.risk_summary.notna().all())
    sample = json.loads(flagged.risk_reasons.iloc[0])
    check("reasons carry layer, severity, message and evidence",
          all({"layer", "severity", "message", "evidence"} <= set(r) for r in sample))

    print("\n5. Peer benchmarking")
    check("no peer group below the minimum size, except the portfolio fallback",
          risk.loc[risk.peer_level != "portfolio", "peer_n"].min() >= config.MIN_PEER_GROUP_SIZE)
    check("most works land on a specific peer group",
          (risk.peer_level == "portfolio").mean() < 0.05)

    print("\n6. Coordinate policy")
    check("all coordinates are constituency centroids",
          set(risk.coordinate_type.dropna().unique()) == {"CONSTITUENCY_CENTROID"},
          str(risk.coordinate_type.dropna().unique()))
    check("latitudes inside India", risk.geo_lat.dropna().between(6, 38).all())
    check("longitudes inside India", risk.geo_lon.dropna().between(67, 98).all())

    print("\n7. Validation smoke test")
    v = pd.read_sql("SELECT * FROM validation_scenario_summary", conn).set_index("scenario")
    normal = v.loc["normal", "mean_risk"]
    for scenario in ["delayed_execution", "spend_ahead", "cost_deviation"]:
        if scenario in v.index:
            check(f"{scenario} ranks above normal",
                  v.loc[scenario, "mean_risk"] > normal,
                  f"{v.loc[scenario, 'mean_risk']:.2f} vs {normal:.2f}")
    if "progress_ahead" in v.index:
        check("progress_ahead is NOT penalised",
              v.loc["progress_ahead", "mean_risk"] < normal,
              f"{v.loc['progress_ahead', 'mean_risk']:.2f} vs {normal:.2f}")

    print("\n8. Independence from the legacy score")
    both = pd.read_sql(
        "SELECT r.risk_score AS new, p.d_risk_score AS legacy "
        "FROM risk_scores r JOIN projects p ON p.work_code = r.work_code", conn)
    corr = both.corr().loc["new", "legacy"]
    check("engine is not a re-skin of the legacy score", corr < 0.6, f"r = {corr:.3f}")

    conn.close()
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("All risk engine checks passed.")


if __name__ == "__main__":
    main()
