# MPLADS Sentinel

Risk triage for MPLADS works. The system reads 34,449 recommended works,
scores each one across six independent layers of evidence, and hands an
investigator a ranked queue where **every alert carries the sentence that
explains it**.

> **Scope.** This is anomaly detection and risk triage, not fraud prediction.
> `fraud_label` is `UNAVAILABLE` for every record in the source dataset, so
> there is nothing honest to train a supervised fraud classifier on. The
> engine finds *unusual*; a human decides whether unusual means wrong.

---

## Quick start

```bash
# 1. Build the database, the geography and the risk engine (~2 minutes)
python init_db.py

# 2. Start the API
uvicorn backend.app.main:app --reload --port 8000

# 3. Start the UI
cd frontend && npm install && npm run dev
```

Optional: use sentence-transformer embeddings instead of TF-IDF for Layer 3.

```bash
# Windows PowerShell
$env:MPLADS_EMBEDDING_BACKEND="sbert"; python -m backend.app.risk_engine.build
# bash
MPLADS_EMBEDDING_BACKEND=sbert python -m backend.app.risk_engine.build
```

Point the UI at a non-default API with `VITE_API_BASE` in `frontend/.env`.

---

## Architecture

```
                    34,449 MPLADS WORKS
                            |
                  OUR FEATURE ENGINEERING
             (raw columns only - see anti-leakage)
                            |
   +--------+--------+------+------+--------+---------+
   |        |        |             |        |         |
FINANCIAL EXECUTION CONTEXT    SEMANTIC  SPATIAL   DATA
 ANOMALY    RISK    DEVIATION  SIMILARITY  RISK    QUALITY
 IForest   IForest  peer group  TF-IDF    ECI      evidence
                    benchmark   cosine    centroid  gaps
   |        |        |             |        |         |
   +--------+--------+------+------+--------+---------+
                            |
                   UNIFIED RISK ENGINE
                   weighted fusion 0-100
                            |
            Risk Score + Priority + Explanation
                            |
                 ASSIGN -> REVIEW -> RESOLVE
```

### The six layers

| Layer | Weight | Method | Answers |
|---|---|---|---|
| Financial Anomaly | 22% | Isolation Forest on log-scaled money features | Is the money shape of this work unusual? |
| Execution Risk | 20% | Isolation Forest + directional gap and stall signals | Has spending run ahead of delivery? |
| Peer Deviation | 20% | Hierarchical peer groups + robust (MAD) z-scores | Is it out of line with *comparable* works? |
| Semantic Similarity | 13% | Sparse TF-IDF cosine over descriptions | Is this work a duplicate of another? |
| Spatial Concern | 13% | ECI constituency centroids + functional overlap | Are similar works stacked in one place? |
| Data Quality | 12% | Evidence-gap flags derived from raw columns | Can this work even be verified? |

Weights, thresholds and peer rules all live in
`backend/app/risk_engine/config.py` and are exposed at `GET /engine/meta`,
so the scoring is inspectable rather than buried in code.

---

## The three decisions that make this defensible

### 1. Anti-leakage: the legacy score never enters a model

The source dataset ships with `d_risk_score`, `d_risk_band`,
`label_rule_band` and a set of `d_sig_*` / `d_peer_*` flags. These are the
**output of an earlier rule-based risk detector**. Feeding them into a new
risk model means training a risk detector on the output of a risk detector:
the new score re-learns the old rules and looks accurate for entirely the
wrong reason.

`config.is_leaky()` blocks every one of them, and `features.load_raw()`
raises rather than loading a column that fails the check:

```
excluded: d_*   *_loo   label_*   fraud_label
pipeline: RAW DATA -> OUR FEATURES -> OUR MODELS -> RISK ENGINE
```

The legacy score is still stored, and every investigation page shows it
beside the Sentinel score as an independent comparison. Across the portfolio
the two correlate at only **r = 0.34**, which is the point: this is a
different and richer signal, not a re-skin of the old one.

### 2. Nothing is compared against "all projects"

A 5-lakh village road and a 5-crore building are not peers. Each work is
matched on **activity + geography + cost band + financial year**, walking
this ladder until a group has at least 25 members:

```
activity+state+fy+scale -> activity+state+scale -> activity+state+fy
-> activity+state -> activity+fy -> activity -> category+state -> category
```

71% of works resolve at the most specific level. Deviations are measured
with median-absolute-deviation z-scores (resistant to the long INR tail),
and small peer groups are shrunk towards zero because a deviation from 26
peers is weaker evidence than a deviation from 700. The investigation page
states exactly which group was used.

### 3. Coordinates are real or they are not claimed

`project_geography` holds official **ECI 2019 constituency centroids**. There
are no invented per-project GPS points anywhere in the engine. The honest
consequence is stated in the API response and in the UI: two works in the
same constituency share a centroid, so co-location is evidence of *possible
functional overlap within a constituency*, not proof of two works at the same
site. Layer 4 therefore scores

```
functional overlap = semantic similarity
                   x same activity
                   x same constituency
                   x overlapping period
```

plus constituency-level saturation of one activity in one year.

---

## Two things the data itself taught us

**Template descriptions defeat naive similarity.** MPLADS descriptions are
formulaic. A dimensionality-reduced embedding scored *"MID DAY Meal Shed in
Govt Primary school Bajakhana"* and *"...school Dana Romana"* at 0.99 - two
different schools - because the reduction discarded the village names that
tell them apart. That flagged 98% of the portfolio as duplicates, which is
the same as flagging nothing. Layer 3 keeps the full sparse TF-IDF matrix
with `min_df=1` so rare village and landmark tokens carry high IDF weight and
become the discriminator. Separation is now clean: ~1.00 identical text,
~0.87 same template different village, ~0.73 same activity type. A duplicate
is only reported when it sits inside the same implementing agency or
constituency.

**10% of works have an impossible schedule.** 3,540 rows carry an expected
completion date that falls *before* the start date, which produced schedule
ratios up to 188x. Those durations are voided and imputed, and the
inconsistency is recorded as the `q_impossible_schedule` data-quality flag
rather than being silently modelled.

---

## Does the engine find anything?

The dataset carries `synthetic_scenario_for_validation` - deliberately
injected unusual cases. This is a **smoke test of the detector, not fraud
accuracy**:

| Injected scenario | n | Mean risk | % flagged Medium/High |
|---|---:|---:|---:|
| delayed_execution | 802 | 47.2 | 53.1% |
| spend_ahead | 1,031 | 34.7 | 20.6% |
| cost_deviation | 395 | 32.6 | 19.0% |
| **normal** | **31,693** | **28.4** | **13.3%** |
| progress_ahead | 528 | 26.5 | 9.5% |

Injected anomalies rank above normal works, and `progress_ahead` ranks
*below* normal - a work running ahead of its spending is correctly not
treated as a risk.

Resulting triage funnel: **101 High** (0.3%), **4,855 Medium** (14%),
**29,493 Low** (86%). A caseload an investigator can actually work through.

### Regression tests

```bash
python test_risk_engine.py     # 40 checks on the engine's claimed properties
python test_map_validation.py  # geography and map aggregation
```

`test_risk_engine.py` asserts the things a reviewer will actually probe: that
no legacy artefact reaches a model, that the unified score really is the
weighted fusion of the six layers, that bands match their thresholds, that
**every flagged work carries at least one explanation**, that no peer group is
smaller than it claims, that all coordinates are constituency centroids inside
India, and that the injected scenarios rank correctly.

---

## Layout

```
backend/app/
  risk_engine/
    config.py             weights, thresholds, peer ladder, leakage policy
    features.py           raw -> engineered features (leakage gate lives here)
    scoring.py            percentile + convex curve shaping, bands, priorities
    layer1_financial.py   Isolation Forests (financial / execution)
    layer2_context.py     hierarchical peer groups + robust deviations
    layer3_semantic.py    embeddings + chunked exact top-k neighbours
    layer4_spatial.py     ECI centroids, haversine, functional overlap
    layer5_quality.py     evidence-gap scoring
    explain.py            score -> sentences an investigator can act on
    engine.py             layer fusion, unified score, priority
    build.py              CLI build step, writes all engine tables
  api.py                  dashboard, alert queue, investigation, review
  map_api.py              choropleth, boundaries, constituency intelligence
  geo_preprocessing.py    ECI 2019 boundary matching
frontend/src/
  lib/api.js              API client + formatting helpers
  components/RiskPrimitives.jsx   score block, layer bars, reason list
  pages/Dashboard.jsx     KPIs, utilisation-vs-progress, layer profile
  pages/AlertQueue.jsx    filterable, sortable investigator queue
  pages/ProjectInvestigation.jsx  full explanation + peer + similar + workflow
  pages/RiskMap.jsx       geospatial intelligence
  pages/Methodology.jsx   the engine explaining itself to a reviewer
init_db.py                one-command bootstrap
```

### Tables written by the engine

| Table | Contents |
|---|---|
| `risk_scores` | one row per work: unified score, band, priority, all six layer scores, every piece of evidence, JSON explanations |
| `project_similarity` | ~207k top-k neighbour pairs with similarity and context flags |
| `peer_benchmarks` | 913 peer groups with medians and risk profile |
| `risk_engine_meta` | build provenance: weights, thresholds, excluded columns, backend |
| `validation_scenario_summary` | the smoke-test table above |

The source `projects` table is left intact; a small set of headline columns
is mirrored onto it so the map queries stay fast.

---

## API

| Endpoint | Purpose |
|---|---|
| `GET /engine/meta` | weights, thresholds, peer ladder, excluded columns |
| `GET /engine/validation` | scenario smoke test |
| `GET /dashboard/summary` | KPIs, layer profile, scatter, state leaderboard |
| `GET /projects` | alert queue with filters, sort by any layer |
| `GET /projects/filters` | filter option lists |
| `GET /projects/detail?work_code=` | full investigation record |
| `GET /projects/similar?work_code=` | Layer 3 neighbours |
| `POST /projects/review?work_code=` | workflow status |
| `GET /map/projects` | constituency-centroid points |
| `GET /api/map/*` | choropleth, boundaries, constituency intelligence |

MPLADS work codes contain forward slashes (`WS/MP18222/2025-2026/171129`), so
project-specific endpoints take the code as a **query parameter**, and the UI
route is a splat (`/projects/*`).
