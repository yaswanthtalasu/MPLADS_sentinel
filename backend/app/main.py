"""MPLADS Sentinel - FastAPI application entry point."""

import os
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .database import DB_PATH
from .map_api import router as map_router
from .risk_engine import config

app = FastAPI(
    title="MPLADS Sentinel API",
    description=(
        "Anomaly detection, contextual benchmarking and risk triage for MPLADS "
        "works. The engine surfaces leads for human investigation; it does not "
        "predict fraud and makes no such claim."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(map_router)


def _engine_built() -> bool:
    if not os.path.exists(DB_PATH):
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        return bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='risk_scores'"
        ).fetchone())
    finally:
        conn.close()


@app.on_event("startup")
def check_engine():
    if not _engine_built():
        print("\n" + "!" * 70)
        print("Risk engine tables are missing. The API will return 503 for risk")
        print("endpoints until you run:  python init_db.py")
        print("!" * 70 + "\n")


@app.get("/")
def root():
    return {
        "service": "MPLADS Sentinel API",
        "version": "2.0.0",
        "risk_engine_built": _engine_built(),
        "layers": [
            {"key": k, "label": config.LAYER_LABELS[k], "weight": w}
            for k, w in config.LAYER_WEIGHTS.items()
        ],
        "scope_note": (
            "Unsupervised anomaly detection. The source dataset has no fraud "
            "labels, so nothing here is a fraud prediction."
        ),
    }
