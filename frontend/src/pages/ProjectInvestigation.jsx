import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, CheckCircle, MapPin, Copy, Scale } from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { api, formatINR, formatPct, formatNumber, riskColor } from '../lib/api';
import { LayerBreakdown, ReasonList, ScoreBlock, RiskBadge, LayerChip } from '../components/RiskPrimitives';

export default function ProjectInvestigation() {
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Work codes contain slashes, so the route is a splat and the raw remainder
  // of the path is the code.
  const workCode = decodeURIComponent(
    params['*'] || location.pathname.replace(/^\/projects\//, ''),
  );

  const [project, setProject] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    const resolve = async () => {
      let code = workCode;
      if (code === 'demo') {
        const top = await api.projects({ limit: 1, risk_band: 'High' });
        if (!top.results.length) throw new Error('No high risk works found');
        code = top.results[0].work_code;
      }
      return api.project(code);
    };
    resolve().then(setProject).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [workCode]);

  const updateStatus = async (status) => {
    setSaving(true);
    try {
      await api.setReviewStatus(project.work_code, status);
      setProject((p) => ({ ...p, investigation_status: status }));
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div>Loading investigation file...</div>;
  if (error) return <div className="callout excluded"><strong>Could not load this work.</strong><div>{error}</div></div>;
  if (!project) return <div>Work not found.</div>;

  const p = project;
  const peer = p.peer_comparison;

  return (
    <div>
      <button className="btn btn-outline mb-4" onClick={() => navigate(-1)}>
        <ArrowLeft size={16} /> Back
      </button>

      <div className="flex-between mb-4">
        <div>
          <h1 className="card-title" style={{ fontSize: '1.375rem', marginBottom: 4 }}>{p.work_code}</h1>
          <div className="muted">
            {p.activity_name} &middot; {p.work_category} &middot; {p.constituency}, {p.state}
          </div>
          <div style={{ marginTop: 8 }}>
            <LayerChip label={`Primary driver: ${p.top_risk_layer}`} />
          </div>
        </div>
        <ScoreBlock score={p.risk_score} band={p.risk_band} priority={p.risk_priority} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* ---------------------------------------------------------- */}
          <div className="card">
            <h2 className="card-title">Why was this flagged?</h2>
            <ReasonList reasons={p.risk_reasons} />
          </div>

          {/* ---------------------------------------------------------- */}
          <div className="card">
            <h2 className="card-title">Score Composition</h2>
            <p className="muted" style={{ marginBottom: 16 }}>
              Weighted points each layer contributed to the {formatNumber(p.risk_score, 0)}/100
              headline. No single layer can produce a high score on its own.
            </p>
            <LayerBreakdown layers={p.layer_breakdown} mode="contribution" />
          </div>

          {/* ---------------------------------------------------------- */}
          <div className="card">
            <h2 className="card-title flex-center"><Scale size={18} /> Contextual Peer Comparison</h2>
            <p className="muted" style={{ marginBottom: 16 }}>
              Benchmarked against <strong>{peer.peer_n?.toLocaleString('en-IN')}</strong> comparable works
              matched on <code className="col">{peer.peer_level}</code>
              {peer.peer_confidence < 1 && (
                <> &mdash; peer group is small, so this deviation is down-weighted
                  (confidence {formatNumber(peer.peer_confidence * 100, 0)}%).</>
              )}
            </p>
            <div className="table-container">
              <table>
                <thead>
                  <tr><th>Metric</th><th style={{ textAlign: 'right' }}>This work</th>
                    <th style={{ textAlign: 'right' }}>Peer median</th>
                    <th style={{ textAlign: 'right' }}>Deviation</th></tr>
                </thead>
                <tbody>
                  {peer.metrics.map((m) => (
                    <tr key={m.metric}>
                      <td style={{ fontWeight: 500 }}>{m.metric}</td>
                      <td className="mono-num" style={{ textAlign: 'right' }}>
                        {m.unit === 'INR' ? formatINR(m.value)
                          : m.unit === '%' ? formatPct(m.value, 1)
                            : `${formatNumber(m.value, 0)} d`}
                      </td>
                      <td className="mono-num muted" style={{ textAlign: 'right' }}>
                        {m.unit === 'INR' ? formatINR(m.peer_median)
                          : m.unit === '%' ? formatPct(m.peer_median, 1)
                            : `${formatNumber(m.peer_median, 0)} d`}
                      </td>
                      <td
                        className="mono-num"
                        style={{ textAlign: 'right', fontWeight: 600, color: m.concerning ? 'var(--risk-high)' : 'var(--text-secondary)' }}
                      >
                        {m.deviation > 0 ? '+' : ''}{formatNumber(m.deviation, 1)} {m.deviation_unit}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ---------------------------------------------------------- */}
          <div className="card">
            <h2 className="card-title">Execution &amp; Financial Record</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, fontSize: '0.8125rem' }}>
              <Fact label="Sanctioned" value={formatINR(p.f_sanctioned_amount)} />
              <Fact label="Estimated cost" value={formatINR(p.f_estimated_cost)} />
              <Fact label="Spent to date" value={formatINR(p.f_expenditure)} />
              <Fact label="Fund utilisation" value={formatPct(p.fund_utilization_pct, 1)} />
              <Fact label="Physical progress" value={formatPct(p.physical_progress_pct, 1)} />
              <Fact
                label="Expenditure-to-progress gap"
                value={formatPct(p.progress_gap_pct, 1)}
                danger={p.progress_gap_pct >= 25}
              />
              <Fact label="Payments released" value={formatNumber(p.f_payment_count, 0)} />
              <Fact label="Days since last payment" value={formatNumber(p.f_days_since_last_payment, 0)} />
              <Fact label="Progress updates" value={formatNumber(p.f_progress_update_count, 0)} />
              <Fact label="Delay" value={`${formatNumber(p.f_delay_days, 0)} days`} danger={p.f_delay_days > 120} />
              <Fact label="Started" value={(p.start_date_syn || '').split(' ')[0] || '--'} />
              <Fact label="Expected completion" value={(p.expected_completion_date_syn || '').split(' ')[0] || '--'} />
            </div>
            <div style={{ marginTop: 16 }}>
              <div className="reason-layer">Work description</div>
              <p className="muted" style={{ marginTop: 4 }}>{p.work_description || 'Not recorded.'}</p>
            </div>
          </div>
        </div>

        {/* ============================ right column ==================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          <div className="card">
            <h2 className="card-title">Investigation Workflow</h2>
            <div style={{ padding: 12, background: 'var(--background-color)', borderRadius: 6, border: '1px solid var(--border-color)', marginBottom: 16 }}>
              <div className="reason-layer">Current status</div>
              <div style={{ fontWeight: 600, fontSize: '1.0625rem' }}>{p.investigation_status}</div>
            </div>
            <p className="muted" style={{ marginBottom: 16 }}>
              The engine surfaces anomalies. It does not determine wrongdoing &mdash;
              the finding stays with the authorised reviewer.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {p.investigation_status === 'Unassigned' && (
                <button className="btn btn-primary" disabled={saving} onClick={() => updateStatus('Under Investigation')}>
                  Assign for review
                </button>
              )}
              {p.investigation_status === 'Under Investigation' && (
                <>
                  <button className="btn btn-primary" style={{ backgroundColor: 'var(--risk-low)' }}
                    disabled={saving} onClick={() => updateStatus('Resolved')}>
                    <CheckCircle size={16} /> Resolved / action taken
                  </button>
                  <button className="btn btn-outline" disabled={saving} onClick={() => updateStatus('Explained / No Issue')}>
                    Explained &mdash; no issue
                  </button>
                </>
              )}
              {['Resolved', 'Explained / No Issue'].includes(p.investigation_status) && (
                <button className="btn btn-outline" disabled={saving} onClick={() => updateStatus('Under Investigation')}>
                  Re-open investigation
                </button>
              )}
            </div>
          </div>

          {/* -------- Layer 3 + 4 -------- */}
          <div className="card">
            <h2 className="card-title flex-center"><Copy size={18} /> Similar &amp; Co-located Works</h2>
            {p.top_similar_projects?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {p.top_similar_projects.map((s) => (
                  <div
                    key={s.work_code}
                    style={{ padding: 12, border: '1px solid var(--border-color)', borderRadius: 6, cursor: 'pointer' }}
                    onClick={() => navigate(`/projects/${s.work_code}`)}
                  >
                    <div className="flex-between">
                      <strong style={{ color: 'var(--primary-color)', fontSize: '0.8125rem' }}>{s.work_code}</strong>
                      <span className="chip layer">{(s.similarity * 100).toFixed(0)}% match</span>
                    </div>
                    <div className="muted" style={{ marginTop: 6, fontSize: '0.75rem' }}>
                      {s.work_description?.slice(0, 120)}
                    </div>
                    <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {s.same_ida === 1 && <span className="chip p2">Same agency</span>}
                      {s.same_constituency === 1 && <span className="chip p3">Same constituency</span>}
                      {s.same_activity === 1 && <span className="chip p4">Same activity</span>}
                      {s.risk_band && <RiskBadge band={s.risk_band} />}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No closely similar works found.</p>
            )}
          </div>

          {/* -------- Layer 4 map -------- */}
          <div className="card">
            <h2 className="card-title flex-center"><MapPin size={18} /> Location</h2>
            <div className="muted" style={{ marginBottom: 12 }}>
              {p.pc_name || p.constituency} &middot; {p.coordinate_type || 'unmapped'}
              {p.geo_source ? ` (${p.geo_source})` : ''}
            </div>
            {p.geo_lat && p.geo_lon ? (
              <div style={{ height: 200, borderRadius: 6, overflow: 'hidden' }}>
                <MapContainer center={[p.geo_lat, p.geo_lon]} zoom={9} style={{ height: '100%', width: '100%' }}>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                  <CircleMarker
                    center={[p.geo_lat, p.geo_lon]} radius={7}
                    fillColor={riskColor(p.risk_band)} color="white" weight={2} fillOpacity={1}
                  >
                    <Popup>{p.work_code}</Popup>
                  </CircleMarker>
                </MapContainer>
              </div>
            ) : (
              <p className="muted">No mapped constituency for this work.</p>
            )}
            <div className="callout warn" style={{ marginTop: 12 }}>
              {p.spatial_resolution_note}
            </div>
          </div>

          {/* -------- Independent benchmark -------- */}
          <div className="card">
            <h2 className="card-title">Legacy Score (comparison only)</h2>
            <div className="flex-between" style={{ marginBottom: 10 }}>
              <span className="muted">Source dataset rule-based score</span>
              <span>
                <strong className="mono-num">{formatNumber(p.legacy_benchmark.d_risk_score, 1)}</strong>{' '}
                <span className="muted">{p.legacy_benchmark.d_risk_band}</span>
              </span>
            </div>
            <div className="flex-between" style={{ marginBottom: 12 }}>
              <span className="muted">MPLADS Sentinel unified score</span>
              <span>
                <strong className="mono-num">{formatNumber(p.risk_score, 1)}</strong>{' '}
                <RiskBadge band={p.risk_band} />
              </span>
            </div>
            <p className="muted" style={{ fontSize: '0.75rem' }}>{p.legacy_benchmark.note}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Fact({ label, value, danger }) {
  return (
    <div>
      <div className="reason-layer">{label}</div>
      <div style={{ fontWeight: 600, color: danger ? 'var(--risk-high)' : 'inherit' }} className="mono-num">
        {value}
      </div>
    </div>
  );
}
