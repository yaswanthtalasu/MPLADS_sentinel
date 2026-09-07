import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function ProjectMiniMap({ lat, lon, workCode, riskColor = '#0f4c81' }) {
  const mapContainer = useRef(null);
  const map = useRef(null);

  useEffect(() => {
    if (!mapContainer.current || !lat || !lon) return;

    if (!map.current) {
      map.current = new maplibregl.Map({
        container: mapContainer.current,
        style: {
          version: 8,
          sources: {
            'osm-tiles': {
              type: 'raster',
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              attribution: '&copy; OpenStreetMap contributors'
            }
          },
          layers: [
            {
              id: 'osm-layer',
              type: 'raster',
              source: 'osm-tiles',
              minzoom: 0,
              maxzoom: 19
            }
          ]
        },
        center: [lon, lat],
        zoom: 9,
        interactive: true
      });

      map.current.on('load', () => {
        new maplibregl.Marker({ color: riskColor })
          .setLngLat([lon, lat])
          .setPopup(new maplibregl.Popup().setText(workCode || 'Project Location'))
          .addTo(map.current);
      });
    }

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [lat, lon, workCode, riskColor]);

  return <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />;
}
