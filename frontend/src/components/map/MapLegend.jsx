import React from 'react';
import { Info } from 'lucide-react';

export const METRIC_CONFIGS = {
  projects: {
    id: 'projects',
    label: 'Project Activity',
    unit: 'Projects',
    description: 'Volume and geographic concentration of sanctioned MPLADS works.',
    thresholds: [50, 100, 200, 400],
    colors: ['#e0f2fe', '#7dd3fc', '#38bdf8', '#0284c7', '#0369a1'],
    labels: ['< 50', '50 - 100', '100 - 200', '200 - 400', '400+']
  },
  funding: {
    id: 'funding',
    label: 'Released Funding',
    unit: '₹ Crores',
    description: 'Total financial disbursement released for sanctioned works.',
    thresholds: [5, 10, 25, 50],
    colors: ['#ecfdf5', '#a7f3d0', '#34d399', '#059669', '#065f46'],
    labels: ['< ₹5 Cr', '₹5 - 10 Cr', '₹10 - 25 Cr', '₹25 - 50 Cr', '₹50+ Cr']
  },
  utilization: {
    id: 'utilization',
    label: 'Fund Utilization Rate',
    unit: '%',
    description: 'Reported expenditure divided by sanctioned disbursement.',
    thresholds: [50, 70, 85, 95],
    colors: ['#fef3c7', '#fde68a', '#fcd34d', '#10b981', '#047857'],
    labels: ['< 50%', '50 - 70%', '70 - 85%', '85 - 95%', '> 95%']
  },
  completion: {
    id: 'completion',
    label: 'Completion Rate',
    unit: '%',
    description: 'Proportion of sanctioned works with recorded completion.',
    thresholds: [40, 60, 80, 95],
    colors: ['#f3e8ff', '#d8b4fe', '#c084fc', '#9333ea', '#6b21a8'],
    labels: ['< 40%', '40 - 60%', '60 - 80%', '80 - 95%', '> 95%']
  },
  risk: {
    id: 'risk',
    label: 'Review Priority / Risk',
    unit: 'Score (0-100)',
    description: 'Aggregated risk engine anomaly score and concentration of review-priority works.',
    thresholds: [10, 20, 35, 50],
    colors: ['#ecfdf5', '#fef3c7', '#fde047', '#f97316', '#dc2626'],
    labels: ['Low (0-10)', 'Moderate (10-20)', 'Elevated (20-35)', 'High (35-50)', 'Critical (50+)']
  },
  gap: {
    id: 'gap',
    label: 'Potential Execution Gap',
    unit: 'Classification',
    description: 'Cross-tabulated analysis of funding volume vs actual completion rate.',
    isCategorical: true,
    categories: [
      { label: 'High Disbursed · Low Completion (Attention Required)', color: '#dc2626' },
      { label: 'High Disbursed · High Delivery Rate', color: '#059669' },
      { label: 'Moderate Disbursed · High Progress', color: '#0284c7' },
      { label: 'Moderate Disbursed · Moderate Progress', color: '#64748b' }
    ]
  },
  need: {
    id: 'need',
    label: 'Development Need',
    unit: 'Official Indicator',
    description: 'Census & NITI Aayog development baseline integration.',
    isNoticeOnly: true,
    notice: 'Authoritative census indicators pending integration. Synthetic/random proxies strictly excluded per geospatial integrity rule.'
  }
};

export default function MapLegend({ currentMetric, onMetricChange }) {
  const config = METRIC_CONFIGS[currentMetric] || METRIC_CONFIGS.projects;

  return (
    <div style={{
      position: 'absolute',
      bottom: 24,
      left: 24,
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      backdropFilter: 'blur(8px)',
      padding: '14px 18px',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      border: '1px solid #cbd5e1',
      zIndex: 10,
      maxWidth: '320px',
      fontSize: '0.8125rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.875rem' }}>
          {config.label}
        </span>
        <span style={{ color: '#64748b', fontSize: '0.75rem', fontWeight: 500 }}>
          {config.unit}
        </span>
      </div>

      <p style={{ color: '#475569', fontSize: '0.75rem', marginBottom: '10px', lineHeight: 1.4 }}>
        {config.description}
      </p>

      {config.isNoticeOnly ? (
        <div style={{
          backgroundColor: '#eff6ff',
          border: '1px solid #bfdbfe',
          padding: '8px 10px',
          borderRadius: '6px',
          color: '#1e40af',
          fontSize: '0.75rem',
          display: 'flex',
          gap: '6px',
          alignItems: 'flex-start'
        }}>
          <Info size={14} style={{ marginTop: '2px', flexShrink: 0 }} />
          <span>{config.notice}</span>
        </div>
      ) : config.isCategorical ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {config.categories.map((cat, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: 14, height: 14, backgroundColor: cat.color, borderRadius: 3, flexShrink: 0 }} />
              <span style={{ color: '#334155', fontSize: '0.72rem', lineHeight: 1.2 }}>{cat.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', height: '10px', borderRadius: '4px', overflow: 'hidden', marginBottom: '6px' }}>
            {config.colors.map((c, i) => (
              <div key={i} style={{ flex: 1, backgroundColor: c }} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.7rem' }}>
            <span>{config.labels[0]}</span>
            <span>{config.labels[Math.floor(config.labels.length / 2)]}</span>
            <span>{config.labels[config.labels.length - 1]}</span>
          </div>
        </div>
      )}
    </div>
  );
}
