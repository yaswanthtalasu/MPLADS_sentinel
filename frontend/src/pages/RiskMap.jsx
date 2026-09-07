import React, { useState, useEffect, useMemo } from 'react';
import { 
  Compass, Layers, Filter, RotateCcw, Search, Database, 
  AlertTriangle, ShieldCheck, ChevronRight, Info, CheckCircle2 
} from 'lucide-react';
import IntelligenceMap from '../components/map/IntelligenceMap';
import MapLegend from '../components/map/MapLegend';
import IntelligenceDrawer from '../components/map/IntelligenceDrawer';
import ProvenanceModal from '../components/map/ProvenanceModal';
import { API_BASE } from '../lib/api';

export default function RiskMap() {
  // State
  const [currentMetric, setCurrentMetric] = useState('projects');
  const [selectedState, setSelectedState] = useState('');
  const [selectedConstituency, setSelectedConstituency] = useState(null);
  const [filterOptions, setFilterOptions] = useState({ states: [], fiscal_years: [], categories: [], statuses: [] });
  const [selectedFY, setSelectedFY] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Data
  const [summaryData, setSummaryData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [showProvenance, setShowProvenance] = useState(false);

  // Fetch Filter Options once
  useEffect(() => {
    fetch(`${API_BASE}/api/map/filter-options`)
      .then(r => r.json())
      .then(opts => setFilterOptions(opts))
      .catch(err => console.error('Failed to load filter options:', err));
  }, []);

  // Fetch Summary data on filter changes
  useEffect(() => {
    setLoadingSummary(true);
    const params = new URLSearchParams();
    if (selectedState) params.append('state', selectedState);
    if (selectedFY) params.append('fiscal_year', selectedFY);
    if (selectedCategory) params.append('category', selectedCategory);
    if (selectedStatus) params.append('status', selectedStatus);

    fetch(`${API_BASE}/api/map/summary?${params.toString()}`)
      .then(r => r.json())
      .then(data => {
        setSummaryData(data);
        setLoadingSummary(false);
      })
      .catch(err => {
        console.error('Failed to load map summary:', err);
        setLoadingSummary(false);
      });
  }, [selectedState, selectedFY, selectedCategory, selectedStatus]);

  // Handle State Selection from map click or dropdown
  const handleSelectState = (stateName, bbox) => {
    setSelectedState(stateName);
    setSelectedConstituency(null);
  };

  // Handle Constituency Selection
  const handleSelectConstituency = (pcProps) => {
    setSelectedConstituency(pcProps);
    if (pcProps.st_name && pcProps.st_name !== selectedState) {
      setSelectedState(pcProps.st_name);
    }
  };

  // Reset to National View
  const handleResetView = () => {
    setSelectedState('');
    setSelectedConstituency(null);
    setSelectedFY('');
    setSelectedCategory('');
    setSelectedStatus('');
    setSearchQuery('');
  };

  // Autocomplete search suggestions
  const searchSuggestions = useMemo(() => {
    if (!searchQuery || searchQuery.length < 2 || !summaryData?.constituencies) return [];
    const q = searchQuery.toLowerCase();
    return Object.values(summaryData.constituencies)
      .filter(pc => pc.pc_name.toLowerCase().includes(q) || pc.state.toLowerCase().includes(q))
      .slice(0, 8);
  }, [searchQuery, summaryData]);

  const kpi = summaryData?.national_summary || {};

  return (
    <div style={{ height: 'calc(100vh - 112px)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Top Controls & Banner */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Header Ribbon */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '1.375rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                MPLADS Intelligence Map
              </h1>
              <span className="badge low" style={{ fontSize: '0.6875rem' }}>
                Verified ECI Delimitation 2019
              </span>
            </div>
            <p style={{ fontSize: '0.8125rem', color: '#64748b', margin: '2px 0 0' }}>
              Hierarchical geospatial intelligence across India, States/UTs, and 543 Parliamentary Constituencies.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button 
              onClick={() => setShowProvenance(true)}
              className="btn btn-outline"
              style={{ fontSize: '0.8125rem', padding: '6px 12px', backgroundColor: '#ffffff' }}
            >
              <Database size={15} color="#0f4c81" />
              Data Provenance & Methodology
            </button>
            <button 
              onClick={handleResetView}
              className="btn btn-outline"
              style={{ fontSize: '0.8125rem', padding: '6px 12px', backgroundColor: '#ffffff' }}
              title="Reset map filters and camera to India national overview"
            >
              <RotateCcw size={15} />
              Reset View
            </button>
          </div>
        </div>

        {/* Global Filter Bar */}
        <div style={{
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          padding: '10px 16px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          {/* Metric Selector Tabs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', marginRight: '4px' }}>
              Metric:
            </span>
            {[
              { id: 'projects', label: 'Project Volume' },
              { id: 'funding', label: 'Released Funds' },
              { id: 'utilization', label: 'Fund Utilization' },
              { id: 'completion', label: 'Completion Rate' },
              { id: 'risk', label: 'Review Priority' },
              { id: 'gap', label: 'Execution Gap' },
              { id: 'need', label: 'Development Need' }
            ].map(m => (
              <button
                key={m.id}
                onClick={() => setCurrentMetric(m.id)}
                style={{
                  padding: '5px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: currentMetric === m.id ? 600 : 500,
                  backgroundColor: currentMetric === m.id ? '#0f4c81' : '#f1f5f9',
                  color: currentMetric === m.id ? '#ffffff' : '#334155',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  whiteSpace: 'nowrap'
                }}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Filters: State, FY, Category, Status, Search */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* State Filter */}
            <select
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                setSelectedConstituency(null);
              }}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.78rem', backgroundColor: '#ffffff' }}
            >
              <option value="">All States / UTs</option>
              {filterOptions.states.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            {/* Fiscal Year */}
            <select
              value={selectedFY}
              onChange={(e) => setSelectedFY(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.78rem', backgroundColor: '#ffffff' }}
            >
              <option value="">All FYs</option>
              {filterOptions.fiscal_years.map(fy => (
                <option key={fy} value={fy}>{fy}</option>
              ))}
            </select>

            {/* Category */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.78rem', backgroundColor: '#ffffff', maxWidth: '140px' }}
            >
              <option value="">All Categories</option>
              {filterOptions.categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>

            {/* Status */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.78rem', backgroundColor: '#ffffff' }}
            >
              <option value="">All Statuses</option>
              <option value="Completed">Completed</option>
              <option value="Ongoing">Ongoing</option>
            </select>

            {/* Search Box */}
            <div style={{ position: 'relative' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                padding: '4px 8px',
                gap: '6px'
              }}>
                <Search size={14} color="#64748b" />
                <input
                  type="text"
                  placeholder="Search PC / State..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: '0.78rem', width: '130px' }}
                />
              </div>

              {/* Suggestions Dropdown */}
              {searchSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '4px',
                  backgroundColor: '#ffffff',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  zIndex: 30,
                  width: '240px',
                  maxHeight: '200px',
                  overflowY: 'auto'
                }}>
                  {searchSuggestions.map(pc => (
                    <div
                      key={pc.pc_id}
                      onClick={() => {
                        handleSelectConstituency(pc);
                        setSearchQuery('');
                      }}
                      style={{ padding: '8px 12px', fontSize: '0.75rem', cursor: 'pointer', borderBottom: '1px solid #f1f5f9' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f1f5f9'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#ffffff'}
                    >
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{pc.pc_name}</div>
                      <div style={{ fontSize: '0.68rem', color: '#64748b' }}>{pc.state} · {pc.project_count} projects</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Breadcrumb Navigation & KPI Ribbon */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          {/* Breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', color: '#64748b' }}>
            <span 
              onClick={handleResetView}
              style={{ cursor: 'pointer', color: selectedState ? '#0284c7' : '#0f172a', fontWeight: selectedState ? 500 : 700 }}
            >
              National (India)
            </span>
            {selectedState && (
              <>
                <ChevronRight size={14} />
                <span 
                  onClick={() => setSelectedConstituency(null)}
                  style={{ cursor: 'pointer', color: selectedConstituency ? '#0284c7' : '#0f172a', fontWeight: selectedConstituency ? 500 : 700 }}
                >
                  {selectedState}
                </span>
              </>
            )}
            {selectedConstituency && (
              <>
                <ChevronRight size={14} />
                <span style={{ color: '#0f172a', fontWeight: 700 }}>
                  {selectedConstituency.pc_name}
                </span>
              </>
            )}
          </div>

          {/* Quick KPI stats */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.78rem', color: '#475569' }}>
            <div>Projects: <strong style={{ color: '#0f4c81' }}>{kpi.total_projects?.toLocaleString() || 0}</strong></div>
            <div>Released: <strong style={{ color: '#059669' }}>₹{kpi.total_disbursed_cr || 0} Cr</strong></div>
            <div>Completion: <strong style={{ color: '#7c3aed' }}>{kpi.completion_rate_pct || 0}%</strong></div>
            <div>Utilization: <strong style={{ color: '#0284c7' }}>{kpi.avg_utilization_pct || 0}%</strong></div>
            {kpi.high_risk_count > 0 && (
              <div style={{ color: '#dc2626', fontWeight: 600 }}>
                ⚠️ {kpi.high_risk_count} High-Priority Works
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Map Main Canvas Container */}
      <div style={{
        flex: 1,
        position: 'relative',
        borderRadius: '10px',
        overflow: 'hidden',
        border: '1px solid #cbd5e1',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
        backgroundColor: '#e2e8f0'
      }}>
        <IntelligenceMap
          summaryData={summaryData}
          currentMetric={currentMetric}
          selectedState={selectedState}
          selectedConstituency={selectedConstituency}
          onSelectState={handleSelectState}
          onSelectConstituency={handleSelectConstituency}
        />

        {/* Legend */}
        <MapLegend currentMetric={currentMetric} />

        {/* Intelligence Side Drawer */}
        <IntelligenceDrawer
          selectedState={selectedState}
          selectedConstituency={selectedConstituency}
          onClose={() => {
            setSelectedConstituency(null);
            setSelectedState('');
          }}
          onSelectConstituency={handleSelectConstituency}
        />
      </div>

      {/* Data Provenance & Methodology Modal */}
      <ProvenanceModal
        isOpen={showProvenance}
        onClose={() => setShowProvenance(false)}
      />
    </div>
  );
}
