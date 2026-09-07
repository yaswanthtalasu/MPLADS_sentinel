import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
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
  const rawStateGeo = useRef(null);
  const rawPCGeo = useRef(null);

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

  // Helper to extract metric value
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

  // Initialize MapLibre with clean OpenStreetMap tiles
  useEffect(() => {
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm-base': {
            type: 'raster',
            tiles: [
              'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
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
              'raster-opacity': 0.65,
              'raster-saturation': -0.35,
              'raster-contrast': 0.1
            }
          }
        ]
      },
      center: INDIA_CENTER,
      zoom: INDIA_DEFAULT_ZOOM,
      minZoom: 3.5,
      maxZoom: 14
    });

    map.current.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-left');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 15,
      maxWidth: '320px'
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

  // Fetch GeoJSON boundaries once
  useEffect(() => {
    if (!mapLoaded || !map.current) return;

    // Fetch States
    fetch(`${API_BASE}/api/map/boundaries/states`)
      .then(r => r.json())
      .then(data => {
        rawStateGeo.current = data;
        updateStateLayers();
      })
      .catch(err => console.error('Failed to load state boundaries:', err));

    // Fetch PCs
    fetch(`${API_BASE}/api/map/boundaries/constituencies`)
      .then(r => r.json())
      .then(data => {
        rawPCGeo.current = data;
        updatePCLayers();
      })
      .catch(err => console.error('Failed to load PC boundaries:', err));
  }, [mapLoaded]);

  // Update State Layers with enriched properties
  const updateStateLayers = () => {
    if (!map.current || !rawStateGeo.current) return;
    const m = map.current;

    // Enrich state features
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
          avgRisk: stMetrics.avg_risk_score || 0,
          gapClass: stMetrics.gap_classification || ''
        }
      };
    });

    const enrichedGeo = {
      type: 'FeatureCollection',
      features: enrichedFeatures
    };

    if (m.getSource('states-source')) {
      m.getSource('states-source').setData(enrichedGeo);
    } else {
      m.addSource('states-source', {
        type: 'geojson',
        data: enrichedGeo
      });

      // Fill Layer
      m.addLayer({
        id: 'states-fill',
        type: 'fill',
        source: 'states-source',
        paint: {
          'fill-color': ['get', 'fillColor'],
          'fill-opacity': 0.78,
          'fill-outline-color': '#0f4c81'
        }
      });

      // Line Layer (Outer boundary)
      m.addLayer({
        id: 'states-line',
        type: 'line',
        source: 'states-source',
        paint: {
          'line-color': '#0f4c81',
          'line-width': 1.8
        }
      });

      // Hover handler
      m.on('mousemove', 'states-fill', (e) => {
        if (selectedState) return; // Don't show state tooltip if drilled down into PC
        m.getCanvas().style.cursor = 'pointer';
        const p = e.features[0].properties;

        const config = METRIC_CONFIGS[currentMetric] || METRIC_CONFIGS.projects;
        const html = `
          <div style="font-family: system-ui, -apple-system, sans-serif; padding: 6px 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 8px;">
              <strong style="font-size: 0.95rem; color: #0f172a;">${p.st_name}</strong>
              <span style="font-size: 0.7rem; background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-weight: 600;">State</span>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.78rem; color: #334155;">
              <div>Projects: <strong style="color: #0f4c81;">${Number(p.projectCount).toLocaleString()}</strong></div>
              <div>Released: <strong style="color: #059669;">₹${p.disbursedCr} Cr</strong></div>
              <div>Completion: <strong style="color: #7c3aed;">${p.completionPct}%</strong></div>
              <div>Utilization: <strong style="color: #0284c7;">${p.utilizationPct}%</strong></div>
            </div>

            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; font-size: 0.75rem;">
              <span style="color: #64748b;">Review Priority:</span>
              <strong style="color: ${p.highRiskCount > 0 ? '#dc2626' : '#16a34a'};">
                ${p.highRiskCount > 0 ? `⚠️ ${p.highRiskCount} High-Priority Works` : 'Low Risk Profile'}
              </strong>
            </div>

            <div style="margin-top: 8px; font-size: 0.7rem; color: #0284c7; font-weight: 600; text-align: right;">
              Click state to explore Constituencies →
            </div>
          </div>
        `;

        popup.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
      });

      m.on('mouseleave', 'states-fill', () => {
        m.getCanvas().style.cursor = '';
        popup.current.remove();
      });

      // Click handler
      m.on('click', 'states-fill', (e) => {
        const p = e.features[0].properties;
        const bbox = typeof p.bbox === 'string' ? JSON.parse(p.bbox) : p.bbox;
        if (onSelectState) {
          onSelectState(p.st_name, bbox);
        }
      });
    }
  };

  // Update PC Layers with enriched properties
  const updatePCLayers = () => {
    if (!map.current || !rawPCGeo.current) return;
    const m = map.current;

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
          utilizationPct: pcMetrics.utilization_rate_pct || 0,
          highRiskCount: pcMetrics.high_risk_count || 0,
          avgRisk: pcMetrics.avg_risk_score || 0,
          dominantSignal: pcMetrics.dominant_signal || 'Normal'
        }
      };
    });

    const enrichedGeo = {
      type: 'FeatureCollection',
      features: enrichedFeatures
    };

    if (m.getSource('constituencies-source')) {
      m.getSource('constituencies-source').setData(enrichedGeo);
    } else {
      m.addSource('constituencies-source', {
        type: 'geojson',
        data: enrichedGeo
      });

      // Fill Layer (shown when zoomed in or state selected)
      m.addLayer({
        id: 'constituencies-fill',
        type: 'fill',
        source: 'constituencies-source',
        paint: {
          'fill-color': ['get', 'fillColor'],
          'fill-opacity': 0.85,
          'fill-outline-color': '#334155'
        },
        filter: ['==', 'norm_state', ''] // Hidden initially until state selected
      });

      // Constituency Line
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

      // Project Location Dots / Centroid Circle Markers
      m.addLayer({
        id: 'centroids-circle',
        type: 'circle',
        source: 'constituencies-source',
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['get', 'projectCount'],
            0, 4,
            50, 6,
            150, 10,
            300, 14
          ],
          'circle-color': [
            'case',
            ['>', ['get', 'highRiskCount'], 0], '#ef4444',
            ['get', 'fillColor']
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.92
        }
      });

      // Dot Click Handler
      m.on('click', 'centroids-circle', (e) => {
        if (e.features && e.features.length > 0) {
          const p = e.features[0].properties;
          if (onSelectConstituency) {
            onSelectConstituency(p);
          }
        }
      });

      m.on('mouseenter', 'centroids-circle', () => {
        m.getCanvas().style.cursor = 'pointer';
      });

      m.on('mouseleave', 'centroids-circle', () => {
        m.getCanvas().style.cursor = '';
      });

      // Hover handler
      m.on('mousemove', 'constituencies-fill', (e) => {
        m.getCanvas().style.cursor = 'pointer';
        const p = e.features[0].properties;

        const html = `
          <div style="font-family: system-ui, -apple-system, sans-serif; padding: 6px 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 4px; margin-bottom: 8px;">
              <strong style="font-size: 0.95rem; color: #0f172a;">${p.pc_name}</strong>
              <span style="font-size: 0.7rem; background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 4px;">${p.st_name}</span>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.78rem; color: #334155;">
              <div>Projects: <strong style="color: #0f4c81;">${Number(p.projectCount).toLocaleString()}</strong></div>
              <div>Released: <strong style="color: #059669;">₹${p.disbursedCr} Cr</strong></div>
              <div>Completion: <strong style="color: #7c3aed;">${p.completionPct}%</strong></div>
              <div>Utilization: <strong style="color: #0284c7;">${p.utilizationPct}%</strong></div>
            </div>

            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; font-size: 0.75rem;">
              <span style="color: #64748b;">Risk Engine Score:</span>
              <strong style="color: ${p.highRiskCount > 0 ? '#dc2626' : '#16a34a'};">
                ${p.avgRisk} / 100 (${p.highRiskCount} High Risk)
              </strong>
            </div>

            <div style="margin-top: 6px; font-size: 0.68rem; color: #64748b; font-style: italic;">
              * Centroid position. Click to view intelligence & projects →
            </div>
          </div>
        `;

        popup.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
      });

      m.on('mouseleave', 'constituencies-fill', () => {
        m.getCanvas().style.cursor = '';
        popup.current.remove();
      });

      // Click handler
      m.on('click', 'constituencies-fill', (e) => {
        const p = e.features[0].properties;
        if (onSelectConstituency) {
          onSelectConstituency(p);
        }
      });
    }
  };

  // Re-run enrichment when metric or summary data changes
  useEffect(() => {
    updateStateLayers();
    updatePCLayers();
  }, [summaryData, currentMetric]);

  // Handle State Filtering & Map Camera Fly-to
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
        m.setFilter('centroids-circle', [
          'any',
          ['==', ['downcase', ['get', 'st_name']], normState],
          ['==', ['downcase', ['get', 'norm_state']], normState]
        ]);
      }

      // Dim national states layer
      if (m.getLayer('states-fill')) {
        m.setPaintProperty('states-fill', 'fill-opacity', 0.15);
      }

      // Fly to state bounds if available
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
      // Restore national overview
      if (m.getLayer('constituencies-fill')) {
        m.setFilter('constituencies-fill', ['==', 'norm_state', '']);
        m.setFilter('constituencies-line', ['==', 'norm_state', '']);
        m.setFilter('centroids-circle', ['==', 'norm_state', '']);
      }
      if (m.getLayer('states-fill')) {
        m.setPaintProperty('states-fill', 'fill-opacity', 0.78);
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
        zoom: 8.5,
        duration: 1200
      });
    }
  }, [selectedConstituency, mapLoaded]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
