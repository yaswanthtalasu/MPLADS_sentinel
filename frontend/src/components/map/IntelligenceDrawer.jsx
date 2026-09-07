import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X, AlertTriangle, ShieldCheck, CheckCircle, Clock,
  ExternalLink, Layers, PieChart, ArrowRight, ChevronLeft, ChevronRight, FileText, Camera, AlertCircle
} from 'lucide-react';
import { API_BASE } from '../../lib/api';

export default function IntelligenceDrawer({ 
  selectedState, 
  selectedConstituency, 
  onClose, 
  onSelectConstituency 
}) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [projectPage, setProjectPage] = useState(1);
  const [riskFilter, setRiskFilter] = useState('');

  useEffect(() => {
    if (!selectedState && !selectedConstituency) {
      setData(null);
      return;
    }

    setLoading(true);
    setProjectPage(1);

    if (selectedConstituency) {
      const pcId = selectedConstituency.pc_id || selectedConstituency;
      const url = `${API_BASE}/api/map/constituency/${pcId}?page=${projectPage}${riskFilter ? `&risk_band=${riskFilter}` : ''}`;
      fetch(url)
        .then(r => r.json())
        .then(res => {
          setData({ type: 'constituency', ...res });
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    } else if (selectedState) {
      fetch(`${API_BASE}/api/map/state/${encodeURIComponent(selectedState)}`)
        .then(r => r.json())
        .then(res => {
          setData({ type: 'state', ...res });
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }
  }, [selectedState, selectedConstituency, projectPage, riskFilter]);

  if (!selectedState && !selectedConstituency) return null;

  const isPC = data?.type === 'constituency';

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      right: 0,
      bottom: 0,
      width: '460px',
      backgroundColor: '#ffffff',
      boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
      borderLeft: '1px solid #cbd5e1',
      zIndex: 20,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      animation: 'slideIn 0.25s ease-out'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        backgroundColor: '#0f4c81',
        color: '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255,255,255,0.1)'
      }}>
        <div style={{ overflow: 'hidden' }}>
          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#93c5fd', fontWeight: 600, letterSpacing: '0.05em' }}>
            {isPC ? 'Constituency Intelligence' : 'State Intelligence'}
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '2px 0 0', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
            {isPC ? data.constituency_metadata?.pc_name : data?.state || selectedState}
          </h2>
          {isPC && (
            <div style={{ fontSize: '0.75rem', color: '#e2e8f0', marginTop: '2px' }}>
              State: {data.constituency_metadata?.state} · PC No: {data.constituency_metadata?.pc_no || 'N/A'}
            </div>
          )}
        </div>
        <button 
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.15)',
            border: 'none',
            color: '#ffffff',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Body Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
            Loading geospatial intelligence...
          </div>
        ) : data ? (
          <>
            {/* Representative Centroid Notice for Constituency */}
            {isPC && (
              <div style={{
                backgroundColor: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: '6px',
                padding: '10px 12px',
                fontSize: '0.75rem',
                color: '#1e40af',
                lineHeight: 1.35
              }}>
                <strong>Representative Centroid:</strong> Map position reflects the official constituency geometric centroid. Exact GPS project locations are unreleased in public feeds.
              </div>
            )}

            {/* Core KPIs */}
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: '8px', textTransform: 'uppercase' }}>
                Key Performance Indicators
              </div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '10px'
              }}>
                <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Total Projects</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f4c81' }}>
                    {(isPC ? data.kpis?.total_projects : data.total_projects)?.toLocaleString()}
                  </div>
                </div>

                <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Released Funding</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#059669' }}>
                    ₹{isPC ? data.kpis?.total_disbursed_cr : data.total_disbursed_cr} Cr
                  </div>
                </div>

                <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Completion Rate</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#7c3aed' }}>
                    {isPC ? data.kpis?.completion_rate_pct : data.completion_rate_pct}%
                  </div>
                </div>

                <div style={{ backgroundColor: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Fund Utilization</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0284c7' }}>
                    {isPC ? data.kpis?.avg_utilization_pct : data.avg_utilization_pct}%
                  </div>
                </div>
              </div>
            </div>

            {/* Risk & Anomaly Profile */}
            <div style={{
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              padding: '14px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#991b1b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertTriangle size={16} />
                  Risk Engine Signal Analysis
                </span>
                <span className="badge high" style={{ fontSize: '0.7rem' }}>
                  {(isPC ? data.kpis?.high_risk_count : data.high_risk_count)} High Priority
                </span>
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#7f1d1d', marginBottom: '8px' }}>
                Average Review Score: <strong>{isPC ? data.kpis?.avg_risk_score : data.avg_risk_score} / 100</strong>
              </div>

              {isPC && data.anomaly_signals && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.75rem', color: '#991b1b', marginTop: '6px', borderTop: '1px dashed #fca5a5', paddingTop: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Missing Site Monitoring Photos:</span>
                    <strong>{data.anomaly_signals.missing_photo_count} ({data.anomaly_signals.missing_photo_pct}%)</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Exact Round Disbursed Amounts:</span>
                    <strong>{data.anomaly_signals.round_amount_count} works</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>No Photographic Evidence:</span>
                    <strong>{data.anomaly_signals.no_evidence_count} works</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Duplicate Descriptions (same agency):</span>
                    <strong>{data.anomaly_signals.near_duplicate_count} works</strong>
                  </div>
                </div>
              )}
            </div>

            {/* If State View: Show Constituencies Ranked */}
            {!isPC && data.constituencies && (
              <div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#475569', marginBottom: '8px', textTransform: 'uppercase' }}>
                  Parliamentary Constituencies ({data.constituencies.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '240px', overflowY: 'auto' }}>
                  {data.constituencies.map(pc => (
                    <div 
                      key={pc.pc_id}
                      onClick={() => onSelectConstituency && onSelectConstituency(pc)}
                      style={{
                        padding: '10px 12px',
                        backgroundColor: '#f8fafc',
                        borderRadius: '6px',
                        border: '1px solid #e2e8f0',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'all 0.15s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#e0f2fe'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: '#0f172a' }}>{pc.pc_name}</div>
                        <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                          {pc.project_count} Projects · ₹{pc.disbursed_cr} Cr
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {pc.high_risk_count > 0 && (
                          <span className="badge high" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                            {pc.high_risk_count} Alert
                          </span>
                        )}
                        <ArrowRight size={14} color="#64748b" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* If Constituency View: Project List */}
            {isPC && data.projects && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#475569', textTransform: 'uppercase' }}>
                    Constituency Projects ({data.projects_pagination?.total_projects || data.projects.length})
                  </span>
                  <select 
                    value={riskFilter}
                    onChange={(e) => { setRiskFilter(e.target.value); setProjectPage(1); }}
                    style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                  >
                    <option value="">All Risk Bands</option>
                    <option value="High">High Risk Only</option>
                    <option value="Medium">Medium Risk</option>
                    <option value="Low">Low Risk</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {data.projects.map(proj => (
                    <div 
                      key={proj.work_code}
                      onClick={() => navigate(`/projects/${proj.work_code}`)}
                      style={{
                        padding: '10px 12px',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        transition: 'border-color 0.15s, box-shadow 0.15s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#0f4c81';
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e2e8f0';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                        <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 600, color: '#0f4c81' }}>
                          {proj.work_code}
                        </span>
                        <span className={`badge ${proj.risk_band?.toLowerCase()}`} style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
                          {proj.risk_score?.toFixed(1)}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.75rem', color: '#334155', fontWeight: 500, marginBottom: '4px', lineHeight: 1.3 }}>
                        {proj.activity_name || proj.work_description || proj.category}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: '#64748b' }}>
                        <span>Disbursed: ₹{proj.amount_disbursed_lakh} Lakh</span>
                        <span>{proj.recommend_fy || 'N/A'}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {data.projects_pagination?.total_pages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                    <button 
                      disabled={projectPage <= 1}
                      onClick={() => setProjectPage(p => p - 1)}
                      className="btn btn-outline"
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                    >
                      <ChevronLeft size={14} /> Prev
                    </button>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Page {projectPage} of {data.projects_pagination.total_pages}
                    </span>
                    <button 
                      disabled={projectPage >= data.projects_pagination.total_pages}
                      onClick={() => setProjectPage(p => p + 1)}
                      className="btn btn-outline"
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                    >
                      Next <ChevronRight size={14} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
