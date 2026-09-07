"""
MPLADS Sentinel - Risk Engine Configuration
===========================================

Single source of truth for:
  * which columns the engine is ALLOWED to see (anti-leakage policy)
  * peer-group construction rules
  * layer weights for the Unified Risk Engine
  * score-to-band thresholds

Design rule (defensibility):
    RAW DATA -> OUR FEATURE ENGINEERING -> OUR MODELS -> RISK ENGINE
No pre-existing risk artefact from the source dataset is ever used as a model
input. They are retained only as an independent benchmark for comparison.
"""

# ---------------------------------------------------------------------------
# 1. ANTI-LEAKAGE POLICY
# ---------------------------------------------------------------------------
# These columns exist in the source dataset but are OUTPUTS of a previous
# rule-based risk detector (or unusable labels). Feeding them into a new risk
# model would mean training a risk detector on the output of a risk detector.
#
# They are kept in the database purely so the UI can show
# "our engine vs. the legacy rule-based score" side by side.

LEAKAGE_TARGET_COLUMNS = [
    "d_risk_score",        # legacy composite risk score
    "d_risk_band",         # legacy risk band
    "label_rule_band",     # derived from the same rules
    "label_human_review",  # derived from the same rules
    "label_no_photo",      # derived from the same rules
    "fraud_label",         # UNAVAILABLE for all 34,449 rows - cannot supervise
]

# Everything with these prefixes is a pre-computed anomaly/benchmark artefact
# from the upstream pipeline. Excluded under the strict policy.
LEAKAGE_PREFIXES = ("d_",)

# Leave-one-out aggregate risk statistics - same problem.
LEAKAGE_SUFFIXES = ("_loo",)

def is_leaky(column: str) -> bool:
    """True if `column` must never reach a model as an input feature."""
    if column in LEAKAGE_TARGET_COLUMNS:
        return True
    if column.startswith(LEAKAGE_PREFIXES):
        return True
    if column.endswith(LEAKAGE_SUFFIXES):
        return True
    return False


# ---------------------------------------------------------------------------
# 2. RAW COLUMNS THE ENGINE IS ALLOWED TO READ
# ---------------------------------------------------------------------------
IDENTITY_COLUMNS = [
    "work_code", "state", "constituency", "mp_name", "ida",
    "work_category", "activity_name", "work_description", "recommend_fy",
    "district_syn",
]

RAW_FINANCIAL_COLUMNS = [
    "amount_disbursed",
    "sanctioned_amount_syn",
    "estimated_cost_syn",
    "expenditure_to_date_syn",
    "payment_count_syn",
    "payment_velocity_inr_per_day_syn",
    "days_since_last_payment_syn",
]

RAW_EXECUTION_COLUMNS = [
    "physical_progress_pct_syn",
    "fund_utilization_pct_syn",
    "start_date_syn",
    "expected_completion_date_syn",
    "monitoring_snapshot_date_syn",
    "project_status_syn",
    "delay_days_syn",
    "progress_update_count_syn",
]

RAW_QUALITY_COLUMNS = [
    "has_uploaded_image",
    "image_published",
    "completion_date",
]

# Retained for benchmark display only - NEVER passed to a model.
BENCHMARK_ONLY_COLUMNS = ["d_risk_score", "d_risk_band"]

# Ground-truth-ish field used ONLY to validate the engine after the fact.
VALIDATION_COLUMN = "synthetic_scenario_for_validation"


# ---------------------------------------------------------------------------
# 3. PEER GROUP HIERARCHY (Layer 2 - Context Intelligence)
# ---------------------------------------------------------------------------
# A project is never compared against "all projects". It is compared against
# projects that share activity, geography, scale and time period.
# We walk this ladder from most-specific to least-specific and stop at the
# first level with at least MIN_PEER_GROUP_SIZE members.

PEER_LEVELS = [
    ("activity+state+fy+scale", ["activity_name", "state", "recommend_fy", "cost_scale_bucket"]),
    ("activity+state+scale",    ["activity_name", "state", "cost_scale_bucket"]),
    ("activity+state+fy",       ["activity_name", "state", "recommend_fy"]),
    ("activity+state",          ["activity_name", "state"]),
    ("activity+fy",             ["activity_name", "recommend_fy"]),
    ("activity",                ["activity_name"]),
    ("category+state",          ["work_category", "state"]),
    ("category",                ["work_category"]),
]

MIN_PEER_GROUP_SIZE = 25

# Cost-scale buckets (INR). Keeps a 5-lakh road from being benchmarked
# against a 5-crore building.
COST_SCALE_BUCKETS = [
    (0,          250_000,      "micro"),
    (250_000,    750_000,      "small"),
    (750_000,    2_500_000,    "medium"),
    (2_500_000,  10_000_000,   "large"),
    (10_000_000, float("inf"), "very_large"),
]


# ---------------------------------------------------------------------------
# 4. UNIFIED RISK ENGINE
# ---------------------------------------------------------------------------
# No single model decides. Six independent signals are fused.
# Weights must sum to 1.0.

LAYER_WEIGHTS = {
    "financial_anomaly":  0.22,   # Layer 1a - Isolation Forest on money features
    "execution_risk":     0.20,   # Layer 1b - Isolation Forest on progress/time
    "context_deviation":  0.20,   # Layer 2  - deviation from peer group
    "semantic_similarity":0.13,   # Layer 3  - duplicate / near-duplicate work
    "spatial_risk":       0.13,   # Layer 4  - co-located functional overlap
    "data_quality":       0.12,   # Layer 5  - evidence & documentation gaps
}

LAYER_LABELS = {
    "financial_anomaly":   "Financial Anomaly",
    "execution_risk":      "Execution Risk",
    "context_deviation":   "Peer Deviation",
    "semantic_similarity": "Semantic Similarity",
    "spatial_risk":        "Spatial Concern",
    "data_quality":        "Data Quality",
}

# Percentile scores are pushed through x**CURVE so that the bulk of projects
# sit near zero and only genuine outliers climb. Without this every project
# would land near 50/100 and the score would be meaningless.
SCORE_CURVE = 2.2

# Unified score -> band
BAND_THRESHOLDS = [
    (70, "High"),
    (45, "Medium"),
    (0,  "Low"),
]

# Unified score -> investigator priority
PRIORITY_THRESHOLDS = [
    (80, "P1"),
    (65, "P2"),
    (45, "P3"),
    (0,  "P4"),
]

# A layer must reach this score before it is quoted as a reason.
REASON_THRESHOLD = 55.0

# ---------------------------------------------------------------------------
# 5. LAYER 3 / 4 TUNING
# ---------------------------------------------------------------------------
SEMANTIC_BACKEND_ENV = "MPLADS_EMBEDDING_BACKEND"     # "tfidf" | "sbert"
SBERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SEMANTIC_DIMENSIONS = 128          # only used by dense/experimental backends
SEMANTIC_NEIGHBOURS = 6            # top-k neighbours retained per project
# Calibrated against the actual distribution of sparse TF-IDF cosine on this
# corpus: ~1.00 is byte-identical text, ~0.87 is the same template with a
# different village, ~0.73 is merely the same activity type.
NEAR_DUPLICATE_THRESHOLD = 0.90
STRONG_DUPLICATE_THRESHOLD = 0.97

# Layer 4 - constituency centroids are the only real coordinates we have.
# Distances are therefore constituency-level, not project-level. This is
# stated explicitly in the API response so the map is never over-claimed.
SPATIAL_OVERLAP_SIM_THRESHOLD = 0.75
SPATIAL_RESOLUTION_NOTE = (
    "Distances are computed between official ECI 2019 constituency centroids, "
    "not surveyed project locations. Co-location is therefore evidence of "
    "possible functional overlap within a constituency, not proof of two works "
    "at the same site."
)
