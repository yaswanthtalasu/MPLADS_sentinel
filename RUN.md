# Running MPLADS Sentinel locally (Windows)

Open two terminals in the project root:
`C:\Users\yaswanthtalasu\Desktop\sih-mplads-prototype`

## Terminal 1 - backend

```powershell
.\backend\venv\Scripts\activate

# Rebuild the database + risk engine (~2 min, only needed once)
python init_db.py

# Optional: verify the engine
python test_risk_engine.py

# Start the API
uvicorn backend.app.main:app --reload --port 8000
```

Check it: http://localhost:8000/  and  http://localhost:8000/docs

## Terminal 2 - frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

## Notes

* `init_db.py` rebuilds `projects` from the CSV, restores the ECI 2019
  geography from the committed snapshot, then runs the six-layer engine.
  It resets `investigation_status` back to `Unassigned`.
* Geography rebuild from the raw boundary files needs `shapely` and
  `requests`, which are not installed in the venv. It is not required -
  the committed snapshot covers all 34,449 works. To force a full
  re-resolution: `pip install shapely requests` then
  `python init_db.py --rebuild-geo`.
* To swap Layer 3 to sentence-transformers (already in the venv):
  ```powershell
  $env:MPLADS_EMBEDDING_BACKEND="sbert"
  python -m backend.app.risk_engine.build
  ```
  Re-calibrate `NEAR_DUPLICATE_THRESHOLD` in
  `backend/app/risk_engine/config.py` first - dense embeddings compress
  similarity upward, and the current 0.90 is calibrated for sparse TF-IDF.
* `_stale_sqlite_journal.bak` in the project root is a leftover SQLite
  rollback journal from an interrupted build. It is safe to delete.
