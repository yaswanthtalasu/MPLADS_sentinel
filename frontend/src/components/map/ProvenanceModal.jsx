import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, ShieldAlert, Download, ExternalLink, Database, MapPin } from 'lucide-react';
import { API_BASE } from '../../lib/api';

export default function ProvenanceModal({ isOpen, onClose }) {
  const [provenance, setProvenance] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      fetch(`${API_BASE}/api/map/provenance`)
        .then(r => r.json())
        .then(data => {
          setProvenance(data);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.65)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '680px',
        maxHeight: '90vh',
        overflowY: 'auto',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        border: '1px solid #e2e8f0',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#0f4c81',
          color: '#ffffff',
          borderTopLeftRadius: '12px',
          borderTopRightRadius: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database size={22} color="#93c5fd" />
            <div>
              <h2 style={{ fontSize: '1.125rem', fontWeight: 700, margin: 0 }}>Map Data & Spatial Methodology</h2>
              <p style={{ fontSize: '0.75rem', color: '#bfdbfe', margin: 0 }}>Authoritative Provenance & Geospatial Integrity Report</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#ffffff',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Integrity Banner */}
          <div style={{
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '8px',
            padding: '14px 16px',
            display: 'flex',
            gap: '12px',
            alignItems: 'flex-start'
          }}>
            <CheckCircle2 size={20} color="#16a34a" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#166534', fontSize: '0.875rem' }}>
                Zero Synthetic Coordinates Policy Active
              </div>
              <p style={{ fontSize: '0.8125rem', color: '#15803d', marginTop: '2px', lineHeight: 1.4 }}>
                All randomly generated coordinates from raw prototype feeds have been completely stripped. 
                Geographic analysis is performed strictly on verified boundaries and representative constituency centroids.
              </p>
            </div>
          </div>

          {/* Coordinate Disclaimer */}
          <div style={{
            backgroundColor: '#fffbeb',
            border: '1px solid #fef3c7',
            borderRadius: '8px',
            padding: '14px 16px',
            display: 'flex',
            gap: '12px',
            alignItems: 'flex-start'
          }}>
            <MapPin size={20} color="#d97706" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#92400e', fontSize: '0.875rem' }}>
                Representative Centroid Disclosure
              </div>
              <p style={{ fontSize: '0.8125rem', color: '#b45309', marginTop: '2px', lineHeight: 1.4 }}>
                "Project-level coordinates are unavailable in official open records. Map position represents the constituency centroid and does not indicate the exact project location."
              </p>
            </div>
          </div>

          {/* Metadata Table */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>Loading provenance metadata...</div>
          ) : provenance ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#1e293b' }}>Dataset & Provenance Attributes</h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '12px',
                backgroundColor: '#f8fafc',
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                fontSize: '0.8125rem'
              }}>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Boundary Source:</div>
                  <div style={{ fontWeight: 600, color: '#0f172a' }}>{provenance.boundary_source}</div>
                </div>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Delimitation Reference:</div>
                  <div style={{ fontWeight: 600, color: '#0f172a' }}>{provenance.derived_from}</div>
                </div>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>License:</div>
                  <div style={{ fontWeight: 600, color: '#0f172a' }}>{provenance.license}</div>
                </div>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Coordinate Method:</div>
                  <div style={{ fontWeight: 600, color: '#0f172a' }}>{provenance.coordinate_method}</div>
                </div>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Official Constituencies Mapped:</div>
                  <div style={{ fontWeight: 600, color: '#0f172a' }}>{provenance.total_official_constituencies} Lok Sabha PCs</div>
                </div>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>MPLADS Dataset Match Rate:</div>
                  <div style={{ fontWeight: 700, color: '#16a34a' }}>
                    {provenance.matched_projects} / {provenance.total_mplads_projects} ({provenance.match_rate_pct}%)
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {/* Action Footer */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            paddingTop: '16px',
            borderTop: '1px solid #e2e8f0'
          }}>
            <a 
              href={`${API_BASE}/api/map/quality-report-download`} 
              download="map_data_quality_report.csv"
              className="btn btn-outline"
              style={{ fontSize: '0.8125rem' }}
            >
              <Download size={16} />
              Download Quality Report (CSV)
            </a>
            <button className="btn btn-primary" onClick={onClose} style={{ fontSize: '0.8125rem' }}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
