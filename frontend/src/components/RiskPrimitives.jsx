import React from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { LAYER_COLORS, riskColor, formatNumber } from '../lib/api';

/** Coloured risk band pill. */
export function RiskBadge({ band }) {
  if (!band) return null;
  return <span className={`badge ${band.toLowerCase()}`}>{band}</span>;
}

/** Investigator priority chip (P1 = look at this first). */
export function PriorityChip({ priority }) {
  if (!priority) return null;
  return <span className={`chip ${priority.toLowerCase()}`}>{priority}</span>;
}

/** Which of the six layers drove this score. */
export function LayerChip({ label }) {
  if (!label) return null;
  return <span className="chip layer">{label}</span>;
}

/**
 * The six-layer breakdown.
 *
 * `mode="score"`      shows each layer's own 0-100 score.
 * `mode="contribution"` shows weighted points contributed to the unified score,
 *                       which is what actually explains the headline number.
 */
export function LayerBreakdown({ layers, mode = 'score' }) {
  if (!layers?.length) return null;
  const max = mode === 'contribution'
    ? Math.max(...layers.map((l) => l.contribution), 1)
    : 100;

  return (
    <div className="layer-bars">
      {layers.map((l) => {
        const value = mode === 'contribution' ? l.contribution : l.score;
        return (
          <div className="layer-bar-row" key={l.key}>
            <div>
              <div className="layer-bar-label">{l.label}</div>
              <div className="layer-weight-note">weight {(l.weight * 100).toFixed(0)}%</div>
            </div>
            <div className="layer-bar-track">
              <div
                className="layer-bar-fill"
                style={{
                  width: `${Math.min(100, (value / max) * 100)}%`,
                  backgroundColor: LAYER_COLORS[l.key] || '#94a3b8',
                }}
              />
            </div>
            <div className="layer-bar-value">{formatNumber(value, mode === 'contribution' ? 1 : 0)}</div>
          </div>
        );
      })}
    </div>
  );
}

const SEVERITY_ICON = {
  high: AlertTriangle,
  medium: AlertCircle,
  low: Info,
};

/** "Why was this flagged" - one card per reason, most severe first. */
export function ReasonList({ reasons }) {
  if (!reasons?.length) {
    return (
      <p className="muted">
        No material anomaly detected across the six risk layers. This work sits
        within normal range for its peer group.
      </p>
    );
  }
  return (
    <ul className="reason-list">
      {reasons.map((r, i) => {
        const Icon = SEVERITY_ICON[r.severity] || Info;
        return (
          <li className={`reason ${r.severity}`} key={i}>
            <Icon
              size={18}
              style={{ flexShrink: 0, marginTop: 2, color: r.severity === 'high' ? 'var(--risk-high)' : r.severity === 'medium' ? 'var(--risk-medium)' : '#94a3b8' }}
            />
            <div>
              <div className="reason-layer">{r.layer}</div>
              <div className="reason-message">{r.message}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Big score readout used on the investigation header. */
export function ScoreBlock({ score, band, priority, label = 'Unified Risk Score' }) {
  return (
    <div className="score-block">
      <div className="muted">{label}</div>
      <div className="score-value" style={{ color: riskColor(band) }}>
        {formatNumber(score, 0)}
        <span className="score-denominator"> / 100</span>
      </div>
      <div style={{ marginTop: 6, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <RiskBadge band={band} />
        <PriorityChip priority={priority} />
      </div>
    </div>
  );
}
