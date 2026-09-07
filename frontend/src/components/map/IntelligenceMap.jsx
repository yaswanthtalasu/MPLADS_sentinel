import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Layers, Flame, MapPin, CircleDot, Eye } from 'lucide-react';
import { METRIC_CONFIGS } from './MapLegend';
import { API_BASE } from '../../lib/api';

const INDIA_CENTER = [78.9629, 22.5937];
const INDIA_DEFAULT_ZOOM = 4.3;

export default function IntelligenceMap({
  summaryData,
  currentMetric,
  selectedState,
  selectedConstituency,
  onSelectState,
  onSelectConstituency
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const popup = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Layer Visibility States
  const [showProjectDots, setShowProjectDots] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showBubbles, setShowBubbles] = useState(true);
  const [showBoundaries, setShowBoundaries] = useState(true);

  const rawStateGeo = useRef(null);
  const rawPCGeo = useRef(null);
  const rawCentroidsGeo = useRef(null);
  const rawProjectPointsGeo = useRef(null);

  // Helper to determine color based on value and metric
  const calculateColor = (val, metricId) => {
    const config = METRIC_CONFIGS[metricId] || METRIC_CONFIGS.projects;
    if (config.isCategorical) {
      if (typeof val === 'string') {
        if (val.includes('Attention Required')) return '#dc2626';
        if (val.includes('High Delivery')) return '#059669';
        if (val.includes('High Progress')) return '#0284c7';
        return '#64748b';
      }
      return '#64748b';
    }

    const num = Number(val) || 0;
    const t = config.thresholds || [50, 100, 200, 400];
    const c = config.colors || ['#e0f2fe', '#7dd3fc', '#38bdf8', '#0284c7', '#0369a1'];

    if (num >= t[3]) return c[4];
    if (num >= t[2]) return c[3];
    if (num >= t[1]) return c[2];
    if (num >= t[0]) return c[1];
    return c[0];
  };

  const getMetricValue = (metricsObj, metricId) => {
    if (!metricsObj) return 0;
    if (metricId === 'projects') return metricsObj.project_count || 0;
    if (metricId === 'funding') return metricsObj.total_disbursed_cr || 0;
    if (metricId === 'utilization') return metricsObj.utilization_rate_pct || 0;
    if (metricId === 'completion') return metricsObj.completion_rate_pct || 0;
    if (metricId === 'risk') return metricsObj.avg_risk_score || 0;
    if (metricId === 'gap') return metricsObj.gap_classification || '';
    return metricsObj.project_count || 0;
  };

  // Initialize MapLibre GL Map
  useEffect(() => {
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm-base': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors'
          }
        },
        layers: [
          {
            id: 'osm-base-layer',
            type: 'raster',
            source: 'osm-base',
            minzoom: 0,
            maxzoom: 19,
            paint: {
              'raster-opacity': 0.72,
              'raster-saturation': -0.3,
              'raster-contrast': 0.08
            }
          }
        ]
      },
      center: INDIA_CENTER,
      zoom: INDIA_DEFAULT_ZOOM,
      minZoom: 3.5,
      maxZoom: 16
    });

    map.current.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-left');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 14,
      maxWidth: '340px'
    });

    map.current.on('load', () => {
      setMapLoaded(true);
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  const safeMapAction = (fn) => {
    if (!map.current) return;
    if (map.current.isStyleLoaded && map.current.isStyleLoaded()) {
      fn(map.current);
    } else {
      map.current.once('load', () => {
        if (map.current) fn(map.current);
      });
    }
  };

  // Fetch All Spatial Datasets with infallible offline/online fallback
  useEffect(() => {
    if (!mapLoaded || !map.current) return;

    const fetchGeo = async (endpoint, fallbackPath) => {
      try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        if (res.ok) return await res.json();
      } catch (e) {
        // Fallback to static bundled geo data if backend is asleep or unreachable
      }
      const fallbackRes = await fetch(fallbackPath);
      return await fallbackRes.json();
    };

    // 1. Fetch State Boundaries
    fetchGeo('/api/map/boundaries/states', '/geo_data/india_states.json')
      .then(data => {
        rawStateGeo.current = data;
        updateStateLayers();
      })
      .catch(err => console.error('Failed to load state boundaries:', err));

    // 2. Fetch PC Boundaries
    fetchGeo('/api/map/boundaries/constituencies', '/geo_data/india_constituencies.json')
      .then(data => {
        rawPCGeo.current = data;
        updatePCLayers();
      })
      .catch(err => console.error('Failed to load PC boundaries:', err));

    // 3. Fetch Constituency Centroid Points
    fetchGeo('/api/map/centroids', '/geo_data/india_centroids.json')
      .then(data => {
        rawCentroidsGeo.current = data;
        updateCentroidLayers();
      })
      .catch(err => console.error('Failed to load centroids:', err));

    // 4. Fetch Project Location Points (All Project Dots)
    fetchGeo('/api/map/project-points?limit=25000', '/geo_data/india_project_points.json')
      .then(data => {
        rawProjectPointsGeo.current = data;
        updateProjectPointLayers();
      })
      .catch(err => console.error('Failed to load project points:', err));
  }, [mapLoaded]);

  // Update State Boundaries Layer
  const updateStateLayers = () => {
    if (!rawStateGeo.current) return;
    safeMapAction((m) => {
      const enrichedFeatures = rawStateGeo.current.features.map(f => {
        const stName = f.properties.st_name;
        const stMetrics = summaryData?.states?.[stName] || {};
        const val = getMetricValue(stMetrics, currentMetric);
        const color = calculateColor(val, currentMetric);

        return {
          ...f,
          properties: {
            ...f.properties,
            fillColor: color,
            metricVal: val,
            projectCount: stMetrics.project_count || 0,
            disbursedCr: stMetrics.total_disbursed_cr || 0,
            completionPct: stMetrics.completion_rate_pct || 0,
            utilizationPct: stMetrics.utilization_rate_pct || 0,
            highRiskCount: stMetrics.high_risk_count || 0,
            avgRisk: stMetrics.avg_risk_score || 0
          }
        };
      });

      const enrichedGeo = { type: 'FeatureCollection', features: enrichedFeatures };

      if (m.getSource('states-source')) {
        m.getSource('states-source').setData(enrichedGeo);
      } else {
        m.addSource('states-source', { type: 'geojson', data: enrichedGeo });

        m.addLayer({
          id: 'states-fill',
          type: 'fill',
          source: 'states-source',
          paint: {
            'fill-color': ['get', 'fillColor'],
            'fill-opacity': 0.65,
            'fill-outline-color': '#0f4c81'
          }
        });

        m.addLayer({
          id: 'states-line',
          type: 'line',
          source: 'states-source',
          paint: {
            'line-color': '#0f4c81',
            'line-width': 1.6
          }
        });

        m.on('mousemove', 'states-fill', (e) => {
          if (selectedState) return;
          m.getCanvas().style.cursor = 'pointer';
          const p = e.features[0].properties;

          const html = `
            <div style="font-family: system-ui, -apple-system, sans-serif; padding: 6px 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 6px;">
                <strong style="font-size: 0.95rem; color: #0f172a;">${p.st_name}</strong>
                <span style="font-size: 0.7rem; background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-weight: 600;">State</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.78rem; color: #334155;">
                <div>Projects: <strong style="color: #0f4c81;">${Number(p.projectCount).toLocaleString()}</strong></div>
                <div>Released: <strong style="color: #059669;">₹${p.disbursedCr} Cr</strong></div>
                <div>Completion: <strong style="color: #7c3aed;">${p.completionPct}%</strong></div>
                <div>Utilization: <strong style="color: #0284c7;">${p.utilizationPct}%</strong></div>
              </div>
              <div style="margin-top: 6px; font-size: 0.7rem; color: #0284c7; font-weight: 600;">
                Click to inspect State Constituencies & Works →
              </div>
            </div>
          `;
          popup.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
        });

        m.on('mouseleave', 'states-fill', () => {
          m.getCanvas().style.cursor = '';
          popup.current.remove();
        });

        m.on('click', 'states-fill', (e) => {
          const p = e.features[0].properties;
          const bbox = typeof p.bbox === 'string' ? JSON.parse(p.bbox) : p.bbox;
          if (onSelectState) onSelectState(p.st_name, bbox);
        });
      }
    });
  };

  // Update PC Boundaries Layer
  const updatePCLayers = () => {
    if (!rawPCGeo.current) return;
    safeMapAction((m) => {
      const enrichedFeatures = rawPCGeo.current.features.map(f => {
        const pcId = f.properties.pc_id;
        const pcMetrics = summaryData?.constituencies?.[String(pcId)] || {};
        const val = getMetricValue(pcMetrics, currentMetric);
        const color = calculateColor(val, currentMetric);

        return {
          ...f,
          properties: {
            ...f.properties,
            fillColor: color,
            metricVal: val,
            projectCount: pcMetrics.project_count || 0,
            disbursedCr: pcMetrics.total_disbursed_cr || 0,
            completionPct: pcMetrics.completion_rate_pct || 0,
            highRiskCount: pcMetrics.high_risk_count || 0,
            avgRisk: pcMetrics.avg_risk_score || 0
          }
        };
      });

      const enrichedGeo = { type: 'FeatureCollection', features: enrichedFeatures };

      if (m.getSource('constituencies-source')) {
        m.getSource('constituencies-source').setData(enrichedGeo);
      } else {
        m.addSource('constituencies-source', { type: 'geojson', data: enrichedGeo });

        m.addLayer({
          id: 'constituencies-fill',
          type: 'fill',
          source: 'constituencies-source',
          paint: {
            'fill-color': ['get', 'fillColor'],
            'fill-opacity': 0.75,
            'fill-outline-color': '#475569'
          },
          filter: ['==', 'norm_state', '']
        });

        m.addLayer({
          id: 'constituencies-line',
          type: 'line',
          source: 'constituencies-source',
          paint: {
            'line-color': '#1e293b',
            'line-width': 1.2
          },
          filter: ['==', 'norm_state', '']
        });

        m.on('click', 'constituencies-fill', (e) => {
          const p = e.features[0].properties;
          if (onSelectConstituency) onSelectConstituency(p);
        });
      }
    });
  };

  // Update Centroid Point & Bubble Layers
  const updateCentroidLayers = () => {
    if (!rawCentroidsGeo.current) return;
    safeMapAction((m) => {
      const enrichedFeatures = rawCentroidsGeo.current.features.map(f => {
        const pcId = f.properties.pc_id;
        const pcMetrics = summaryData?.constituencies?.[String(pcId)] || {};
        const val = getMetricValue(pcMetrics, currentMetric);
        const color = calculateColor(val, currentMetric);

        return {
          ...f,
          properties: {
            ...f.properties,
            fillColor: color,
            projectCount: pcMetrics.project_count || f.properties.project_count || 0,
            disbursedCr: pcMetrics.total_disbursed_cr || f.properties.total_disbursed_cr || 0,
            highRiskCount: pcMetrics.high_risk_count || f.properties.high_risk_count || 0,
            avgRisk: pcMetrics.avg_risk_score || f.properties.avg_risk_score || 0,
            complaintsCount: pcMetrics.complaints_count || f.properties.complaints_count || 0
          }
        };
      });

      const enrichedGeo = { type: 'FeatureCollection', features: enrichedFeatures };

      if (m.getSource('centroids-source')) {
        m.getSource('centroids-source').setData(enrichedGeo);
      } else {
        m.addSource('centroids-source', { type: 'geojson', data: enrichedGeo });

        // 1. Heatmap Layer on Centroids (Complaints & High Risk Density)
        m.addLayer({
          id: 'centroids-heatmap',
          type: 'heatmap',
          source: 'centroids-source',
          maxzoom: 12,
          paint: {
            'heatmap-weight': [
              'interpolate', ['linear'], ['get', 'highRiskCount'],
              0, 0.2,
              5, 0.6,
              20, 1.2
            ],
            'heatmap-intensity': [
              'interpolate', ['linear'], ['zoom'],
              3, 0.8,
              8, 1.6
            ],
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0, 'rgba(33, 102, 172, 0)',
              0.2, 'rgba(103, 169, 207, 0.5)',
              0.4, 'rgba(209, 229, 240, 0.7)',
              0.6, 'rgba(253, 219, 199, 0.85)',
              0.8, 'rgba(239, 138, 98, 0.9)',
              1, 'rgba(220, 38, 38, 0.95)'
            ],
            'heatmap-radius': [
              'interpolate', ['linear'], ['zoom'],
              3, 15,
              6, 28,
              9, 45
            ],
            'heatmap-opacity': 0.75
          }
        });

        // 2. Constituency Bubble Layer (Clustered Circles)
        m.addLayer({
          id: 'centroid-bubbles',
          type: 'circle',
          source: 'centroids-source',
          minzoom: 3.5,
          paint: {
            'circle-radius': [
              'interpolate', ['linear'], ['zoom'],
              4, [
                'interpolate', ['linear'], ['get', 'projectCount'],
                0, 3.5,
                50, 6,
                200, 10,
                500, 15
              ],
              8, [
                'interpolate', ['linear'], ['get', 'projectCount'],
                0, 6,
                50, 10,
                200, 16,
                500, 24
              ]
            ],
            'circle-color': [
              'case',
              ['>', ['get', 'highRiskCount'], 0], '#ef4444',
              ['get', 'fillColor']
            ],
            'circle-stroke-width': 1.8,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 0.9
          }
        });

        // Hover on Centroid Bubbles
        m.on('mousemove', 'centroid-bubbles', (e) => {
          m.getCanvas().style.cursor = 'pointer';
          const p = e.features[0].properties;

          const html = `
            <div style="font-family: system-ui, -apple-system, sans-serif; padding: 6px 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 6px;">
                <strong style="font-size: 0.92rem; color: #0f172a;">${p.pc_name}</strong>
                <span style="font-size: 0.68rem; background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 4px;">${p.st_name}</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.78rem; color: #334155;">
                <div>Projects: <strong style="color: #0f4c81;">${Number(p.projectCount).toLocaleString()}</strong></div>
                <div>Released: <strong style="color: #059669;">₹${p.total_disbursed_cr || 0} Cr</strong></div>
              </div>
              <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid #f1f5f9; font-size: 0.74rem;">
                <span style="color: #64748b;">Risk Engine:</span>
                <strong style="color: ${p.highRiskCount > 0 ? '#dc2626' : '#16a34a'};">
                  ${p.highRiskCount > 0 ? `⚠️ ${p.highRiskCount} High Risk Works` : 'Low Risk Profile'}
                </strong>
              </div>
              <div style="margin-top: 6px; font-size: 0.68rem; color: #0284c7; font-weight: 600;">
                Click to view project details in drawer →
              </div>
            </div>
          `;
          popup.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
        });

        m.on('mouseleave', 'centroid-bubbles', () => {
          m.getCanvas().style.cursor = '';
          popup.current.remove();
        });

        m.on('click', 'centroid-bubbles', (e) => {
          const p = e.features[0].properties;
          if (onSelectConstituency) onSelectConstituency(p);
        });
      }
    });
  };

  // Update Individual Project Location Points (Dots)
  const updateProjectPointLayers = () => {
    if (!rawProjectPointsGeo.current) return;
    safeMapAction((m) => {
      if (m.getSource('project-points-source')) {
        m.getSource('project-points-source').setData(rawProjectPointsGeo.current);
      } else {
        m.addSource('project-points-source', {
          type: 'geojson',
          data: rawProjectPointsGeo.current
        });

        // Project Location Dots Layer (Visible at all zoom levels)
        m.addLayer({
          id: 'project-dots',
          type: 'circle',
          source: 'project-points-source',
          paint: {
            'circle-radius': [
              'interpolate', ['linear'], ['zoom'],
              3, 3.5,
              6, 5.5,
              9, 8.5,
              13, 12
            ],
            'circle-color': [
              'match', ['get', 'risk_band'],
              'High', '#ef4444',
              'Medium', '#f59e0b',
              'Low', '#10b981',
              '#0284c7'
            ],
            'circle-stroke-width': [
              'interpolate', ['linear'], ['zoom'],
              3, 0.8,
              7, 1.4,
              12, 2.0
            ],
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 0.95
          }
        });

        // Hover on Individual Project Dots
        m.on('mousemove', 'project-dots', (e) => {
          m.getCanvas().style.cursor = 'pointer';
          const p = e.features[0].properties;

          const isHigh = p.risk_band === 'High';
          const isMed = p.risk_band === 'Medium';
          const badgeBg = isHigh ? '#fee2e2' : isMed ? '#fef3c7' : '#dcfce7';
          const badgeColor = isHigh ? '#b91c1c' : isMed ? '#b45309' : '#15803d';

          const html = `
            <div style="font-family: system-ui, -apple-system, sans-serif; padding: 6px 8px; min-width: 200px;">
              <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">
                <strong style="font-size: 0.76rem; color: #0f172a; font-family: monospace;">${p.work_code}</strong>
                <span style="font-size: 0.68rem; font-weight: 700; background: ${badgeBg}; color: ${badgeColor}; padding: 2px 6px; border-radius: 4px;">
                  ${p.risk_band} (${p.risk_score})
                </span>
              </div>
              <div style="font-size: 0.8rem; color: #0f172a; font-weight: 600; margin-bottom: 4px; line-height: 1.3;">
                ${p.activity_name || p.category}
              </div>
              ${p.work_description && p.work_description !== p.activity_name ? `
                <div style="font-size: 0.72rem; color: #64748b; margin-bottom: 6px; line-height: 1.25;">
                  ${p.work_description}
                </div>
              ` : ''}
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.75rem; color: #334155; background: #f8fafc; padding: 4px 6px; border-radius: 4px;">
                <div>PC: <strong>${p.pc_name}</strong></div>
                <div>State: <strong>${p.state}</strong></div>
                <div>Disbursed: <strong style="color: #059669;">₹${p.amount_lakh || 0} L</strong></div>
                <div>Status: <strong>${p.investigation_status || 'Active'}</strong></div>
              </div>
              <div style="margin-top: 6px; font-size: 0.68rem; color: #0284c7; font-weight: 600; text-align: right;">
                Click dot to investigate project →
              </div>
            </div>
          `;
          popup.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
        });

        m.on('mouseleave', 'project-dots', () => {
          m.getCanvas().style.cursor = '';
          popup.current.remove();
        });

        m.on('click', 'project-dots', (e) => {
          const p = e.features[0].properties;
          if (onSelectConstituency) {
            onSelectConstituency({ pc_id: p.pc_id, pc_name: p.pc_name, st_name: p.state });
          }
        });
      }
    });
  };

  // Synchronize dynamic metric updates
  useEffect(() => {
    updateStateLayers();
    updatePCLayers();
    updateCentroidLayers();
  }, [summaryData, currentMetric]);

  // Handle Layer Visibility Toggles
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    if (m.getLayer('project-dots')) {
      m.setLayoutProperty('project-dots', 'visibility', showProjectDots ? 'visible' : 'none');
    }
    if (m.getLayer('centroids-heatmap')) {
      m.setLayoutProperty('centroids-heatmap', 'visibility', showHeatmap ? 'visible' : 'none');
    }
    if (m.getLayer('centroid-bubbles')) {
      m.setLayoutProperty('centroid-bubbles', 'visibility', showBubbles ? 'visible' : 'none');
    }
    if (m.getLayer('states-fill')) {
      m.setLayoutProperty('states-fill', 'visibility', showBoundaries ? 'visible' : 'none');
      m.setLayoutProperty('states-line', 'visibility', showBoundaries ? 'visible' : 'none');
    }
  }, [showProjectDots, showHeatmap, showBubbles, showBoundaries, mapLoaded]);

  // Handle State Selection & Camera Fly-To
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    if (selectedState) {
      const normState = selectedState.trim().toLowerCase();

      // Show constituencies for selected state
      if (m.getLayer('constituencies-fill')) {
        m.setFilter('constituencies-fill', [
          'any',
          ['==', ['downcase', ['get', 'st_name']], normState],
          ['==', ['downcase', ['get', 'norm_state']], normState]
        ]);
        m.setFilter('constituencies-line', [
          'any',
          ['==', ['downcase', ['get', 'st_name']], normState],
          ['==', ['downcase', ['get', 'norm_state']], normState]
        ]);
      }

      // Filter project dots & centroids to selected state
      if (m.getLayer('centroid-bubbles')) {
        m.setFilter('centroid-bubbles', [
          'any',
          ['==', ['downcase', ['get', 'st_name']], normState],
          ['==', ['downcase', ['get', 'norm_state']], normState]
        ]);
      }
      if (m.getLayer('project-dots')) {
        m.setFilter('project-dots', [
          'any',
          ['==', ['downcase', ['get', 'state']], normState],
          ['==', ['downcase', ['get', 'norm_state']], normState]
        ]);
      }

      // Dim national states
      if (m.getLayer('states-fill')) {
        m.setPaintProperty('states-fill', 'fill-opacity', 0.2);
      }

      // Fit bounds
      if (rawStateGeo.current) {
        const feat = rawStateGeo.current.features.find(
          f => f.properties.st_name?.toLowerCase() === normState || f.properties.norm_state?.toLowerCase() === normState
        );
        if (feat && feat.properties.bbox) {
          const b = typeof feat.properties.bbox === 'string' ? JSON.parse(feat.properties.bbox) : feat.properties.bbox;
          m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: 1200 });
        }
      }
    } else {
      // Restore national overview - SHOW ALL POINTS ACROSS INDIA
      if (m.getLayer('constituencies-fill')) {
        m.setFilter('constituencies-fill', ['==', 'norm_state', '']);
        m.setFilter('constituencies-line', ['==', 'norm_state', '']);
      }
      if (m.getLayer('centroid-bubbles')) {
        m.setFilter('centroid-bubbles', null); // Show all centroids!
      }
      if (m.getLayer('project-dots')) {
        m.setFilter('project-dots', null); // Show all project dots across India!
      }
      if (m.getLayer('states-fill')) {
        m.setPaintProperty('states-fill', 'fill-opacity', 0.65);
      }

      m.flyTo({
        center: INDIA_CENTER,
        zoom: INDIA_DEFAULT_ZOOM,
        duration: 1000
      });
    }
  }, [selectedState, mapLoaded]);

  // Handle Constituency Camera Transition
  useEffect(() => {
    if (!mapLoaded || !map.current || !selectedConstituency) return;
    const m = map.current;

    const lat = selectedConstituency.centroid_lat || selectedConstituency.centroidLat;
    const lon = selectedConstituency.centroid_lon || selectedConstituency.centroidLon;

    if (lat && lon) {
      m.flyTo({
        center: [lon, lat],
        zoom: 9.2,
        duration: 1200
      });
    }
  }, [selectedConstituency, mapLoaded]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

      {/* Floating Layer Controls Toolbar */}
      <div style={{
        position: 'absolute',
        top: 14,
        right: 14,
        backgroundColor: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(8px)',
        borderRadius: '8px',
        border: '1px solid #cbd5e1',
        boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
        padding: '8px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        zIndex: 10
      }}>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase', marginBottom: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Layers size={13} color="#0f4c81" />
          Map Layers
        </div>

        {/* Project Dots Toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#0f172a', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showProjectDots}
            onChange={(e) => setShowProjectDots(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: '#0f4c81' }}
          />
          <MapPin size={13} color="#dc2626" />
          <span>Project Dots (All Points)</span>
        </label>

        {/* Heatmap Toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#0f172a', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={(e) => setShowHeatmap(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: '#ea580c' }}
          />
          <Flame size={13} color="#ea580c" />
          <span>Complaints & Risk Heatmap</span>
        </label>

        {/* Centroid Bubbles Toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#0f172a', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showBubbles}
            onChange={(e) => setShowBubbles(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: '#0284c7' }}
          />
          <CircleDot size={13} color="#0284c7" />
          <span>Constituency Bubbles</span>
        </label>

        {/* Boundaries Toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#0f172a', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showBoundaries}
            onChange={(e) => setShowBoundaries(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: '#059669' }}
          />
          <Eye size={13} color="#059669" />
          <span>State / PC Choropleth</span>
        </label>
      </div>
    </div>
  );
}
