import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ZAxis, ReferenceLine, BarChart, Bar, Cell,
} from 'recharts';
import { api, riskColor, formatINR, formatPct, LAYER_COLORS } from '../lib/api';
import { LayerBreakdown, RiskBadge, LayerChip, PriorityChip } from '../components/RiskPrimitives';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([api.dashboard(), api.projects({ limit: 12 })])
      .then(([s, p]) => { setSummary(s); setProjects(p.results); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading portfolio...</div>;
  if (error) {
    return (
      <div className="callout excluded">
        <strong>Could not reach the risk engine.</strong>
        <div style={{ marginTop: 8 }}>{error}</div>
        <div style={{ marginTop: 8 }}>
          Build it with <code className="col">python init_db.py</code>, then start the API with{' '}
          <code className="col">uvicorn backend.app.main:app --reload --port 8000</code>.
        </div>
      </div>
    );
  }

  const { kpis, layer_profile, top_layer_distribution, scatter_data, state_leaderboard } = summary;
  const layers = layer_profile.map((l) => ({ ...l, score: l.mean_score, contribution: l.mean_score * l.weight }));

  const ScatterTip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="card" style={{ padding: 12, margin: 0 }}>
        <div style={{ fontWeight: 600 }}>{d.work_code}</div>
        <div className="muted">Physical progress: {formatPct(d.physical_progress_pct)}</div>
        <div className="muted">Fund utilisation: {formatPct(d.fund_utilization_pct)}</div>
        <div style={{ marginTop: 4, fontWeight: 600, color: riskColor(d.risk_band) }}>
          Gap {formatPct(d.progress_gap_pct)} · Risk {Math.round(d.risk_score)}/100
        </div>
      </div>
    );
  };

  return (
    <div>
      <div className="flex-between mb-4">
        <div>
          <h1 className="card-title" style={{ fontSize: '1.5rem', marginBottom: 2 }}>Portfolio Overview</h1>
          <div className="muted">
            Six-layer unified risk engine · {kpis.total_projects.toLocaleString('en-IN')} works ·
            {' '}{formatINR(kpis.total_expenditure)} expenditure tracked
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/alerts')}>
          Open Alert Queue
        </button>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-title">High Risk (P1/P2)</div>
          <div className="kpi-value text-high">{kpis.high_risk.toLocaleString('en-IN')}</div>
          <div className="muted">{formatPct((kpis.high_risk / kpis.total_projects) * 100, 2)} of portfolio</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Medium Risk</div>
          <div className="kpi-value text-medium">{kpis.medium_risk.toLocaleString('en-IN')}</div>
          <div className="muted">queued for review</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Expenditure &gt; Progress</div>
          <div className="kpi-value" style={{ color: 'var(--secondary-color)' }}>
            {kpis.large_progress_gap.toLocaleString('en-IN')}
          </div>
          <div className="muted">gap of 25 points or more</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Duplicate Descriptions</div>
          <div className="kpi-value" style={{ color: '#db2777' }}>
            {kpis.strong_duplicates.toLocaleString('en-IN')}
          </div>
          <div className="muted">identical text, same agency</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Missing Photo Evidence</div>
          <div className="kpi-value" style={{ color: 'var(--text-secondary)' }}>
            {kpis.missing_evidence.toLocaleString('en-IN')}
          </div>
          <div className="muted">cannot be verified remotely</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-title">Under Investigation</div>
          <div className="kpi-value" style={{ color: 'var(--primary-color)' }}>
            {kpis.under_review.toLocaleString('en-IN')}
          </div>
          <div className="muted">assigned to a reviewer</div>
        </div>
      </div>

      {/* The headline chart: money out of the door vs work on the ground. */}
      <div className="card">
        <h2 className="card-title">Fund Utilisation vs Physical Progress</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          Points below the diagonal have spent more than they have built. The further
          below the line, the wider the expenditure-to-progress gap. Click any point to investigate.
        </p>
        <div style={{ height: 380 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                type="number" dataKey="physical_progress_pct" domain={[0, 100]}
                label={{ value: 'Physical Progress (%)', position: 'insideBottom', offset: -15, fontSize: 12 }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                type="number" dataKey="fund_utilization_pct" domain={[0, 100]}
                label={{ value: 'Fund Utilisation (%)', angle: -90, position: 'insideLeft', fontSize: 12 }}
                tick={{ fontSize: 11 }}
              />
              <ZAxis range={[26, 26]} />
              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]}
                stroke="#94a3b8" strokeDasharray="6 4"
              />
              <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: '3 3' }} />
              {['Low', 'Medium', 'High'].map((band) => (
                <Scatter
                  key={band}
                  name={band}
                  data={scatter_data.filter((d) => d.risk_band === band)}
                  fill={riskColor(band)}
                  fillOpacity={band === 'Low' ? 0.28 : 0.85}
                  onClick={(e) => navigate(`/projects/${e.work_code}`)}
                  style={{ cursor: 'pointer' }}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div className="card">
          <h2 className="card-title">Average Signal Strength by Layer</h2>
          <p className="muted" style={{ marginBottom: 16 }}>
            Each layer scores independently before the engine fuses them. No single model decides.
          </p>
          <LayerBreakdown layers={layers} mode="score" />
        </div>

        <div className="card">
          <h2 className="card-title">What is Driving the Flags</h2>
          <p className="muted" style={{ marginBottom: 16 }}>
            Dominant layer for each non-Low work &mdash; where an investigator's time should go.
          </p>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={top_layer_distribution} layout="vertical" margin={{ left: 40, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="layer" width={130} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="n" radius={[0, 4, 4, 0]}>
                  {top_layer_distribution.map((d, i) => (
                    <Cell key={i} fill={Object.values(LAYER_COLORS)[i % 6]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex-between mb-4">
          <h2 className="card-title" style={{ margin: 0 }}>Highest Risk Works</h2>
          <button className="btn btn-outline" onClick={() => navigate('/alerts')}>View all</button>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Work Code</th>
                <th>Location</th>
                <th>Why it is flagged</th>
                <th>Driver</th>
                <th style={{ textAlign: 'right' }}>Score</th>
                <th>Band</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.work_code} onClick={() => navigate(`/projects/${p.work_code}`)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontWeight: 500, color: 'var(--primary-color)', whiteSpace: 'nowrap' }}>
                    {p.work_code}
                  </td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{p.constituency}, {p.state}</td>
                  <td style={{ maxWidth: 420, fontSize: '0.8125rem' }}>{p.risk_summary}</td>
                  <td><LayerChip label={p.top_risk_layer} /></td>
                  <td className="mono-num" style={{ textAlign: 'right', fontWeight: 700 }}>
                    {p.risk_score?.toFixed(0)}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <RiskBadge band={p.risk_band} /> <PriorityChip priority={p.risk_priority} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">States by Average Risk</h2>
        <div className="table-container">
          <table>
            <thead>
              <tr><th>State</th><th style={{ textAlign: 'right' }}>Works</th>
                <th style={{ textAlign: 'right' }}>Avg risk</th>
                <th style={{ textAlign: 'right' }}>High risk</th></tr>
            </thead>
            <tbody>
              {state_leaderboard.map((s) => (
                <tr key={s.state}>
                  <td style={{ fontWeight: 500 }}>{s.state}</td>
                  <td className="mono-num" style={{ textAlign: 'right' }}>{s.n.toLocaleString('en-IN')}</td>
                  <td className="mono-num" style={{ textAlign: 'right' }}>{s.avg_risk?.toFixed(1)}</td>
                  <td className="mono-num" style={{ textAlign: 'right', color: 'var(--risk-high)', fontWeight: 600 }}>
                    {s.high_risk}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="callout" style={{ marginTop: 24 }}>
        {summary.methodology_note}
      </div>
    </div>
  );
}
