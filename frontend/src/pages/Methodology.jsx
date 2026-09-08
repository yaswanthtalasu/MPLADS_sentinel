import React, { useEffect, useState } from 'react';
import { api, LAYER_COLORS } from '../lib/api';

const LAYER_NOTES = {
  financial_anomaly: 'Isolation Forest over the money shape of the work: sanctioned amount, estimated cost, expenditure, disbursement share, payment count, average payment size and spending velocity - all log-transformed because INR values are heavily right-skewed.',
  execution_risk: 'Isolation Forest over the delivery shape, blended with two directional facts an auditor actually cares about: funds drawn ahead of physical progress, and works that have stalled (money spent, no movement, no recent payment).',
  context_deviation: 'No work is compared against the whole portfolio. Each is matched to peers on activity, state, cost band and financial year, then measured with a median-absolute-deviation z-score. Small peer groups are weak evidence, so their deviations are shrunk towards zero.',
  semantic_similarity: 'Full sparse TF-IDF cosine over work descriptions, deliberately keeping rare village and landmark tokens - they are what separate a genuine duplicate from a reused template. A duplicate only counts when it sits inside the same implementing agency or constituency.',
  spatial_risk: 'Functional overlap = semantic similarity x same activity x same constituency x overlapping period, plus constituency-level saturation of a single activity in a single year.',
  data_quality: 'Missing evidence is not fraud, but it is why fraud cannot be ruled out. Scored separately so "this looks wrong" is never confused with "we cannot tell".',
};

export default function Methodology() {
  const [meta, setMeta] = useState(null);
  const [validation, setValidation] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.engineMeta().then(setMeta).catch((e) => setError(e.message));
    api.validation().then(setValidation).catch(() => {});
  }, []);

  if (error) return <div className="callout excluded"><strong>Engine not built.</strong><div>{error}</div></div>;
  if (!meta) return <div>Loading methodology...</div>;

  return (
    <div>
      <h1 className="card-title" style={{ fontSize: '1.5rem', marginBottom: 2 }}>How the Risk Score is Built</h1>
      <p className="muted" style={{ marginBottom: 24 }}>
        Built {meta.built_at} &middot; {meta.n_projects.toLocaleString('en-IN')} works &middot;
        embeddings: <code className="col">{meta.embedding_backend}</code>
      </p>

      <div className="callout warn" style={{ marginBottom: 24 }}>
        <strong>This is not a fraud predictor.</strong> {meta.note}
      </div>

      <div className="card">
        <h2 className="card-title">The Six Layers</h2>
        <p className="muted" style={{ marginBottom: 16 }}>
          Each layer scores independently from a different kind of evidence. The unified
          score is their weighted fusion, so no single model can flag a work on its own.
        </p>
        <div className="method-grid">
          {meta.layers.map((l) => (
            <div className="method-card" key={l.key} style={{ borderTop: `3px solid ${LAYER_COLORS[l.key]}` }}>
              <div className="flex-between" style={{ marginBottom: 4 }}>
                <h3>{l.label}</h3>
                <span className="chip layer">{(l.weight * 100).toFixed(0)}%</span>
              </div>
              <p>{LAYER_NOTES[l.key]}</p>
            </div>
          ))}
        </div>
      </div>

     

      <div className="card">
        <h2 className="card-title">Peer Group Ladder</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          Each work takes the most specific peer group with at least{' '}
          <strong>{meta.min_peer_group_size}</strong> members, walking down this ladder:
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {meta.peer_levels.map((lvl, i) => (
            <span key={lvl} className={`chip ${i === 0 ? 'p1' : i < 4 ? 'p3' : 'p4'}`}>
              {i + 1}. {lvl}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Score Shaping &amp; Bands</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          Each layer's raw signal is rank-transformed, then pushed through a convex curve
          (exponent <strong>{meta.score_curve}</strong>) so the bulk of ordinary works sits near
          zero. Without that shaping the median work would score 50/100 and "medium risk" would
          become the default state of the entire portfolio.
        </p>
        <div className="table-container">
          <table>
            <thead><tr><th>Band</th><th>Unified score</th></tr></thead>
            <tbody>
              {meta.band_thresholds.map(([cut, name]) => (
                <tr key={name}><td><span className={`badge ${name.toLowerCase()}`}>{name}</span></td>
                  <td className="mono-num">&ge; {cut}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {validation?.scenarios?.length > 0 && (
        <div className="card">
          <h2 className="card-title">Does the Engine Actually Find Anything?</h2>
          <div className="callout warn" style={{ marginBottom: 16 }}>{validation.disclaimer}</div>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>Injected scenario</th><th style={{ textAlign: 'right' }}>Works</th>
                  <th style={{ textAlign: 'right' }}>Mean risk score</th>
                  <th style={{ textAlign: 'right' }}>% flagged Medium or High</th></tr>
              </thead>
              <tbody>
                {validation.scenarios.map((s) => (
                  <tr key={s.scenario} style={{ fontWeight: s.scenario === 'normal' ? 700 : 400 }}>
                    <td>{s.scenario}</td>
                    <td className="mono-num" style={{ textAlign: 'right' }}>{s.n.toLocaleString('en-IN')}</td>
                    <td className="mono-num" style={{ textAlign: 'right' }}>{s.mean_risk}</td>
                    <td className="mono-num" style={{ textAlign: 'right' }}>{s.pct_flagged_med_or_high}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            Works injected with delayed execution and spend-ahead behaviour rank above normal
            ones, while <em>progress_ahead</em> ranks <em>below</em> normal &mdash; a work that is
            ahead of its spending is correctly not treated as a risk.
          </p>
        </div>
      )}

      <div className="card">
        <h2 className="card-title">Coordinate Policy</h2>
        <p className="muted">{meta.spatial_resolution_note}</p>
      </div>
    </div>
  );
}
