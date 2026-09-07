/**
 * Thin API client for the MPLADS Sentinel backend.
 *
 * MPLADS work codes contain forward slashes ("WS/MP18222/2025-2026/171129"),
 * so project-specific endpoints take the code as a query parameter rather
 * than a path segment.
 */

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_BASE ||
  'http://localhost:8000';

async function get(path, params) {
  const qs = params ? `?${new URLSearchParams(params)}` : '';
  const res = await fetch(`${API_BASE}${path}${qs}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  engineMeta: () => get('/engine/meta'),
  validation: () => get('/engine/validation'),
  dashboard: () => get('/dashboard/summary'),
  filters: () => get('/projects/filters'),
  projects: (params) => get('/projects', params),
  project: (workCode) => get('/projects/detail', { work_code: workCode }),
  similar: (workCode, limit = 10) =>
    get('/projects/similar', { work_code: workCode, limit }),
  mapPoints: (limit = 5000) => get('/map/projects', { limit }),

  async setReviewStatus(workCode, status) {
    const res = await fetch(
      `${API_BASE}/projects/review?${new URLSearchParams({ work_code: workCode })}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      },
    );
    if (!res.ok) throw new Error('Failed to update review status');
    return res.json();
  },
};

/* ------------------------------------------------------------------ */
/* Shared presentation helpers                                         */
/* ------------------------------------------------------------------ */

export const RISK_COLORS = {
  High: '#ef4444',
  Medium: '#f59e0b',
  Low: '#10b981',
};

export const LAYER_COLORS = {
  financial_anomaly: '#0f4c81',
  execution_risk: '#0891b2',
  context_deviation: '#7c3aed',
  semantic_similarity: '#db2777',
  spatial_risk: '#ea580c',
  data_quality: '#64748b',
};

export const riskColor = (band) => RISK_COLORS[band] || '#94a3b8';

export function formatINR(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
  const v = Number(value);
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
  return Number(value).toFixed(digits);
}

export const formatPct = (value, digits = 0) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? '--'
    : `${Number(value).toFixed(digits)}%`;
