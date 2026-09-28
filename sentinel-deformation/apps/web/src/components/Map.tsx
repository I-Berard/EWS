import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface MapProps {
  aoi?: any;
  anomalies?: any;
  onMapClick?: (lngLat: { lat: number; lng: number }) => void;
  onAnomalyClick?: (anomalyProperties: any) => void;
}

const MapComponent: React.FC<MapProps> = ({ aoi, anomalies, onMapClick, onAnomalyClick }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (map.current || !mapContainer.current) return;
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [30.06, -1.95],
      zoom: 10
    });
    
    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.current.on('click', (e) => {
      // Check if we clicked an anomaly
      const features = map.current?.queryRenderedFeatures(e.point, { layers: ['anomalies-fill'] });
      if (features && features.length > 0 && onAnomalyClick) {
        onAnomalyClick(features[0].properties);
        return;
      }
      
      // Otherwise regular map click for time series
      if (onMapClick) {
        onMapClick(e.lngLat);
      }
    });

    // Change cursor to pointer over anomalies
    map.current.on('mouseenter', 'anomalies-fill', () => {
      if (map.current) map.current.getCanvas().style.cursor = 'pointer';
    });
    map.current.on('mouseleave', 'anomalies-fill', () => {
      if (map.current) map.current.getCanvas().style.cursor = '';
    });

  }, []);

  // Update AOI
  useEffect(() => {
    if (!map.current || !aoi) return;
    
    const updateSource = () => {
      if (map.current?.getSource('aoi')) {
        (map.current.getSource('aoi') as maplibregl.GeoJSONSource).setData(aoi.geometry);
      } else {
        map.current?.addSource('aoi', { type: 'geojson', data: aoi.geometry });
        map.current?.addLayer({
          id: 'aoi-outline',
          type: 'line',
          source: 'aoi',
          paint: { 'line-color': '#4da6ff', 'line-width': 2, 'line-dasharray': [2, 2] }
        });
      }
    };
    
    if (map.current.isStyleLoaded()) {
      updateSource();
    } else {
      map.current.once('load', updateSource);
    }
  }, [aoi]);

  // Update Anomalies
  useEffect(() => {
    if (!map.current || !anomalies) return;
    
    const updateSource = () => {
      if (map.current?.getSource('anomalies')) {
        (map.current.getSource('anomalies') as maplibregl.GeoJSONSource).setData(anomalies);
      } else {
        map.current?.addSource('anomalies', { type: 'geojson', data: anomalies });
        
        map.current?.addLayer({
          id: 'anomalies-fill',
          type: 'fill',
          source: 'anomalies',
          paint: {
            'fill-color': [
              'case',
              ['<', ['get', 'mean_velocity'], -10], '#ff3333', // severe subsidence
              ['<', ['get', 'mean_velocity'], -5], '#ff9933',  // moderate subsidence
              '#ffcc00' // mild
            ],
            'fill-opacity': 0.6
          }
        });

        map.current?.addLayer({
          id: 'anomalies-outline',
          type: 'line',
          source: 'anomalies',
          paint: { 'line-color': '#ffffff', 'line-width': 1 }
        });
      }
    };

    if (map.current.isStyleLoaded()) {
      updateSource();
    } else {
      map.current.once('load', updateSource);
    }
  }, [anomalies]);

  return (
    <div ref={mapContainer} className="map-container" style={{ width: '100%', height: '100%' }} />
  );
};

export default MapComponent;
