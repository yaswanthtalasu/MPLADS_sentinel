# Deployment Guide: MPLADS Sentinel

This repository is pre-configured for automated one-click deployment:
- **Backend API**: [Render](https://render.com) (Python 3.11 + FastAPI + SQLite Spatial Engine)
- **Frontend**: [Vercel](https://vercel.com) (React 19 + Vite + MapLibre GL JS)

---

## 1. Deploy Backend on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) and click **New +** $\to$ **Web Service**.
2. Connect your GitHub repository: `https://github.com/yaswanthtalasu/MPLADS_sentinel`.
3. Configure the service settings:
   - **Name**: `mplads-sentinel-api`
   - **Region**: Oregon (US West) or Singapore / Frankfurt
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python init_db.py
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`
4. Add Environment Variables (under *Advanced* / *Environment Variables*):
   - `PYTHON_VERSION`: `3.11.9`
   - `MPLADS_EMBEDDING_BACKEND`: `tfidf`
5. Click **Create Web Service**.
6. Once deployed, copy your Render public URL (e.g. `https://mplads-sentinel-api.onrender.com`).

---

## 2. Deploy Frontend on Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and import `yaswanthtalasu/MPLADS_sentinel`.
2. In the configuration dialog:
   - **Root Directory**: Click *Edit* and select **`frontend`**.
   - **Framework Preset**: `Vite` (auto-detected).
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Add Environment Variable:
   - **Key**: `VITE_API_BASE`
   - **Value**: Your Render Backend URL from Step 1 (e.g., `https://mplads-sentinel-api.onrender.com` without trailing slash).
4. Click **Deploy**.

---

## 3. Post-Deployment Verification

1. **Backend Health Check**:
   Open `https://<your-render-app>.onrender.com/` in your browser. You should see:
   ```json
   {
     "service": "MPLADS Sentinel API",
     "version": "2.0.0",
     "risk_engine_built": true
   }
   ```
2. **Interactive Swagger Docs**:
   Open `https://<your-render-app>.onrender.com/docs`.
3. **Frontend Application**:
   Open your Vercel URL (e.g. `https://mplads-sentinel.vercel.app/map`).
   - The **MPLADS Intelligence Map** renders choropleths, heatmap layers, and constituency centroid dots with live data streamed directly from your Render backend.
