import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { AnomalyCollection, ImageKind, ProductMeta, Polygon } from '../api';

interface MapProps {
  aoi?: { id: string; geometry: Polygon } | null;
  anomalies?: AnomalyCollection | null;
  product?: ProductMeta | null;
  /** Which raster overlays to show (images are served by the API as PNGs). */
  visibleImages?: Record<ImageKind, boolean>;
  /** Focus this anomaly (rank list selection) - highlights it and flies to it. */
  selectedAnomalyId?: string | null;
  onMapClick?: (lngLat: { lat: number; lng: number }) => void;
  onAnomalyClick?: (anomalyProperties: AnomalyCollection['features'][0]['properties']) => void;
}

// Magnitude colour ramp for |mean_velocity| (mm/yr) - matches the API's PNG ramp
const RAMP_STEPS: Array<[number, string]> = [
  [3, '#ffdc00'],
  [8, '#ff9600'],
  [14, '#ff3c00'],
  [20, '#c80000'],
  [30, '#820000'],
];

/** MapLibre expression interpolating fill color by |mean_velocity|. */
const velocityColorExpression = (): maplibregl.ExpressionSpecification => {
  const stops = RAMP_STEPS.flatMap(([threshold, color]) => [threshold, color]);
  return [
    'interpolate',
    ['linear'],
    ['abs', ['coalesce', ['get', 'mean_velocity'], 0]],
    ...stops,
  ] as unknown as maplibregl.ExpressionSpecification;
};

const MapComponent: React.FC<MapProps> = ({
  aoi,
  anomalies,
  product,
  visibleImages,
  selectedAnomalyId,
  onMapClick,
  onAnomalyClick,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const mapReady = useRef(false);

  // Keep latest callbacks without re-binding map events
  const clickCb = useRef(onMapClick);
  const anomalyCb = useRef(onAnomalyClick);
  clickCb.current = onMapClick;
  anomalyCb.current = onAnomalyClick;

  const runWhenReady = (fn: () => void) => {
    if (map.current && mapReady.current) {
      fn();
    } else if (map.current) {
      map.current.once('load', fn);
    }
  };

  // -------------------------------------------------------------------------
  // Map init
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (map.current || !mapContainer.current) return;
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [30.06, -1.95],
      zoom: 10,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.current.on('load', () => {
      mapReady.current = true;
      map.current?.triggerRepaint();
    });

    map.current.on('click', (e) => {
      const anomalyFeatures = map.current?.queryRenderedFeatures(e.point, { layers: ['anomalies-fill'] });
      if (anomalyFeatures && anomalyFeatures.length > 0 && anomalyCb.current) {
        anomalyCb.current(anomalyFeatures[0].properties as AnomalyCollection['features'][0]['properties']);
        return;
      }
      clickCb.current?.({ lat: e.lngLat.lat, lng: e.lngLat.lng });
    });

    map.current.on('mouseenter', 'anomalies-fill', () => {
      if (map.current) map.current.getCanvas().style.cursor = 'pointer';
    });
    map.current.on('mouseleave', 'anomalies-fill', () => {
      if (map.current) map.current.getCanvas().style.cursor = '';
    });
  }, []);

  // -------------------------------------------------------------------------
  // Product raster overlays (SAR backscatter + velocity), served by the API
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!map.current || !product) return;

    runWhenReady(() => {
      if (!map.current || !product) return;
      const [west, south, east, north] = product.bbox;

      const layers: Array<{ id: ImageKind; url: string; beforeId: string }> = [
        { id: 'sar', url: `/api/demo/aois/${product.aoi_id}/images/sar`, beforeId: 'anomalies-fill' },
        { id: 'velocity', url: `/api/demo/aois/${product.aoi_id}/images/velocity`, beforeId: 'anomalies-outline' },
      ];

      for (const { id, url, beforeId } of layers) {
        if (!map.current.getSource(`img-${id}`)) {
          map.current.addSource(`img-${id}`, {
            type: 'image',
            url,
            coordinates: [
              [west, north],
              [east, north],
              [east, south],
              [west, south],
            ],
          });
        }
        if (!map.current.getLayer(`overlay-${id}`)) {
          map.current.addLayer(
            {
              id: `overlay-${id}`,
              type: 'raster',
              source: `img-${id}`,
              paint: {
                'raster-opacity': 0.85,
                'raster-fade-duration': 300,
              },
            },
            beforeId,
          );
        }
      }
      updateImageVisibility();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product]);

  const updateImageVisibility = () => {
    if (!map.current) return;
    for (const id of ['sar', 'velocity'] as ImageKind[]) {
      const layerId = `overlay-${id}`;
      if (!map.current.getLayer(layerId)) continue;
      const visible = visibleImages?.[id] ?? false;
      map.current.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
    }
  };

  useEffect(() => {
    runWhenReady(updateImageVisibility);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleImages, product]);

  // -------------------------------------------------------------------------
  // AOI outline + fit bounds
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!map.current || !aoi) return;

    runWhenReady(() => {
      if (!map.current || !aoi) return;

      if (map.current.getSource('aoi')) {
        (map.current.getSource('aoi') as maplibregl.GeoJSONSource).setData(aoi.geometry);
      } else {
        map.current.addSource('aoi', { type: 'geojson', data: aoi.geometry });
        map.current.addLayer({
          id: 'aoi-outline',
          type: 'line',
          source: 'aoi',
          paint: { 'line-color': '#4da6ff', 'line-width': 2, 'line-dasharray': [2, 2] },
        });
      }

      // Fly to the AOI bounds
      const coords: Array<[number, number]> = aoi.geometry.coordinates[0];
      const lons = coords.map((c) => c[0]);
      const lats = coords.map((c) => c[1]);
      map.current.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        { padding: 40, duration: 1200, maxZoom: 12 },
      );
    });
  }, [aoi]);

  // -------------------------------------------------------------------------
  // Anomalies: fill/outline/highlight/labels
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!map.current || !anomalies) return;

    runWhenReady(() => {
      if (!map.current || !anomalies) return;

      if (map.current.getSource('anomalies')) {
        (map.current.getSource('anomalies') as maplibregl.GeoJSONSource).setData(anomalies);
      } else {
        map.current.addSource('anomalies', { type: 'geojson', data: anomalies });

        map.current.addLayer(
          {
            id: 'anomalies-fill',
            type: 'fill',
            source: 'anomalies',
            paint: {
              // Rank 1 (highest |velocity|) gets a strong red + pulsing-style emphasis
              'fill-color': [
                'case',
                ['==', ['get', 'rank'], 1], '#ff2222',
                ['>', ['get', 'mean_velocity'], 0], '#4dc3ff', // uplift
                velocityColorExpression(),
              ],
              'fill-opacity': [
                'case',
                ['==', ['get', 'rank'], 1], 0.85,
                0.6,
              ],
            },
          },
          'anomalies-outline',
        );

        map.current.addLayer({
          id: 'anomalies-outline',
          type: 'line',
          source: 'anomalies',
          paint: {
            'line-color': '#ffffff',
            'line-width': ['case', ['==', ['get', 'rank'], 1], 3, 1],
          },
        });

        map.current.addLayer({
          id: 'anomaly-rank-labels',
          type: 'symbol',
          source: 'anomalies',
          layout: {
            'text-field': ['to-string', ['get', 'rank']],
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-size': 14,
          },
          paint: {
            'text-color': '#ffffff',
            'text-halo-color': '#000000',
            'text-halo-width': 2,
          },
        });
      }

      updateSelection();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anomalies]);

  // Highlight the selected anomaly (from the ranked list or a map click)
  const updateSelection = () => {
    if (!map.current) return;
    const selectedId = selectedAnomalyId ?? null;
    if (map.current.getLayer('anomalies-highlight')) {
      map.current.setFilter('anomalies-highlight', ['==', ['get', 'id'], selectedId ?? '']);
    }
    if (map.current.getLayer('anomalies-outline')) {
      if (selectedId) {
        map.current.setFilter('anomalies-outline', ['==', ['get', 'id'], selectedId]);
        map.current.setPaintProperty('anomalies-outline', 'line-color', '#ff2222');
        map.current.setPaintProperty('anomalies-outline', 'line-width', 3);
      } else {
        map.current.setFilter('anomalies-outline', ['==', ['get', 'rank'], 1]);
        map.current.setPaintProperty('anomalies-outline', 'line-color', '#ffffff');
        map.current.setPaintProperty('anomalies-outline', 'line-width', 3);
      }
    }
  };

  useEffect(() => {
    runWhenReady(updateSelection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAnomalyId, anomalies]);

  // Fly to the selected anomaly when chosen from the ranked list
  useEffect(() => {
    if (!map.current || !selectedAnomalyId || !anomalies) return;
    const feature = anomalies.features.find((f) => f.properties.id === selectedAnomalyId);
    if (!feature) return;
    const coords: Array<[number, number]> = feature.geometry.coordinates[0];
    const lons = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    map.current.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 120, duration: 900, maxZoom: 14 },
    );
  }, [selectedAnomalyId, anomalies]);

  return <div ref={mapContainer} className="map-container" style={{ width: '100%', height: '100%' }} />;
};

export default MapComponent;
