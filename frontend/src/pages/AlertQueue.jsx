import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { api, formatINR, formatPct } from '../lib/api';
import { RiskBadge, PriorityChip, LayerChip } from '../components/RiskPrimitives';

const PAGE_SIZE = 25;

const SORTS = [
  { value: 'risk_score', label: 'Unified risk score' },
  { value: 'progress_gap_pct', label: 'Expenditure-to-progress gap' },
  { value: 'financial_anomaly', label: 'Financial anomaly' },
  { value: 'execution_risk', label: 'Execution risk' },
  { value: 'context_deviation', label: 'Peer deviation' },
  { value: 'semantic_similarity', label: 'Semantic similarity' },
  { value: 'spatial_risk', label: 'Spatial concern' },
  { value: 'data_quality', label: 'Data quality' },
];

export default function AlertQueue() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState(null);
  const [query, setQuery] = useState({
    risk_band: '', priority: '', state: '', category: '',
    layer: '', status: '', search: '', sort: 'risk_score',
  });
  const [searchDraft, setSearchDraft] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, results: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.filters().then(setFilters).catch(() => {}); }, []);

  const load = useCallback(() => {
    setLoading(true);
    const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
    Object.entries(query).forEach(([k, v]) => { if (v) params[k] = v; });
    api.projects(params).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [query, page]);

  useEffect(load, [load]);

  const set = (key) => (e) => {
    setPage(0);
    setQuery((q) => ({ ...q, [key]: e.target.value }));
  };

  const pages = Math.ceil(data.total / PAGE_SIZE);

  return (
    <div>
      <h1 className="card-title" style={{ fontSize: '1.5rem', marginBottom: 2 }}>Alert Queue</h1>
      <p className="muted" style={{ marginBottom: 20 }}>
        Every row carries the reason it was surfaced. The engine produces leads;
        the decision stays with the reviewer.
      </p>

      <div className="card">
        <div className="filter-bar">
          <div className="filter-field">
            <label>Risk band</label>
            <select value={query.risk_band} onChange={set('risk_band')}>
              <option value="">All bands</option>
              {(filters?.risk_bands || []).map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Priority</label>
            <select value={query.priority} onChange={set('priority')}>
              <option value="">All</option>
              {(filters?.priorities || []).map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Dominant layer</label>
            <select value={query.layer} onChange={set('layer')}>
              <option value="">Any layer</option>
              {(filters?.layers || []).map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>State</label>
            <select value={query.state} onChange={set('state')}>
              <option value="">All states</option>
              {(filters?.states || []).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Category</label>
            <select value={query.category} onChange={set('category')}>
              <option value="">All categories</option>
              {(filters?.categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Review status</label>
            <select value={query.status} onChange={set('status')}>
              <option value="">Any status</option>
              {(filters?.statuses || []).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Rank by</label>
            <select value={query.sort} onChange={set('sort')}>
              {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Search</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={searchDraft}
                placeholder="code, description, constituency"
                onChange={(e) => setSearchDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { setPage(0); setQuery((q) => ({ ...q, search: searchDraft })); }
                }}
              />
              <button
                className="btn btn-outline"
                onClick={() => { setPage(0); setQuery((q) => ({ ...q, search: searchDraft })); }}
              >
                <Search size={15} />
              </button>
            </div>
          </div>
        </div>

        <div className="muted" style={{ marginBottom: 12 }}>
          {loading ? 'Loading...' : `${data.total.toLocaleString('en-IN')} works match`}
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Work Code</th>
                <th>Activity / Location</th>
                <th>Lead</th>
                <th>Driver</th>
                <th style={{ textAlign: 'right' }}>Gap</th>
                <th style={{ textAlign: 'right' }}>Spend</th>
                <th style={{ textAlign: 'right' }}>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((p) => (
                <tr key={p.work_code} onClick={() => navigate(`/projects/${p.work_code}`)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontWeight: 500, color: 'var(--primary-color)', whiteSpace: 'nowrap' }}>
                    {p.work_code}
                  </td>
                  <td style={{ fontSize: '0.8125rem' }}>
                    <div>{p.activity_name}</div>
                    <div className="muted">{p.constituency}, {p.state}</div>
                  </td>
                  <td style={{ maxWidth: 380, fontSize: '0.8125rem' }}>{p.risk_summary}</td>
                  <td><LayerChip label={p.top_risk_layer} /></td>
                  <td className="mono-num" style={{ textAlign: 'right', color: p.progress_gap_pct >= 25 ? 'var(--risk-high)' : 'inherit' }}>
                    {formatPct(p.progress_gap_pct)}
                  </td>
                  <td className="mono-num" style={{ textAlign: 'right' }}>{formatINR(p.f_expenditure)}</td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span className="mono-num" style={{ fontWeight: 700, marginRight: 6 }}>
                      {p.risk_score?.toFixed(0)}
                    </span>
                    <RiskBadge band={p.risk_band} />
                    {' '}<PriorityChip priority={p.risk_priority} />
                  </td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{p.investigation_status}</td>
                </tr>
              ))}
              {!loading && !data.results.length && (
                <tr><td colSpan={8} className="muted" style={{ textAlign: 'center', padding: 32 }}>
                  No works match these filters.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button className="btn btn-outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span className="muted">Page {page + 1} of {Math.max(pages, 1)}</span>
          <button className="btn btn-outline" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
