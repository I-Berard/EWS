import React, { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { AnomalyCollection, ImageKind, MovementAnalysis, MovementAreaProperties, ProductMeta, Polygon } from '../api';

interface MapProps {
  aoi?: { id: string; geometry: Polygon } | null;
  anomalies?: AnomalyCollection | null;
  product?: ProductMeta | null;
  /** Which raster overlays to show (images are served by the API as PNGs). */
  visibleImages?: Record<ImageKind, boolean>;
  /** Focus this anomaly (rank list selection) - highlights it and flies to it. */
  selectedAnomalyId?: string | null;
  /** URL of the period-movement heatmap PNG (stack of Sentinel-1 visits). */
  movementUrl?: string | null;
  /** Ranked areas that moved the most inside the selected period. */
  movementAreas?: MovementAnalysis | null;
  /** Focus this movement area (rank list selection) - highlights it and flies to it. */
  selectedMovementId?: string | null;
  onMapClick?: (lngLat: { lat: number; lng: number }) => void;
  onAnomalyClick?: (anomalyProperties: AnomalyCollection['features'][0]['properties']) => void;
  onMovementAreaClick?: (properties: MovementAreaProperties) => void;
  onBoundsChange?: (bounds: [number, number, number, number]) => void;
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

// Magnitude colour ramp for cumulative |movement| (mm over the period) - matches
// the API's MOVEMENT_RAMP used for the heatmap PNG.
const MOVEMENT_RAMP: Array<[number, string]> = [
  [1, '#966eff'],
  [4, '#cd3ceb'],
  [10, '#ff2da5'],
  [18, '#ff8c3c'],
  [28, '#ffeb8c'],
];

/** MapLibre expression interpolating fill color by |peak_movement_mm|. */
const movementColorExpression = (): maplibregl.ExpressionSpecification => {
  const stops = MOVEMENT_RAMP.flatMap(([threshold, color]) => [threshold, color]);
  return [
    'interpolate',
    ['linear'],
    ['abs', ['coalesce', ['get', 'peak_movement_mm'], 0]],
    ...stops,
  ] as unknown as maplibregl.ExpressionSpecification;
};

/** Filter shape accepted by Map#setFilter (kept opaque to the local typings). */
type MapFilter = Parameters<maplibregl.Map['setFilter']>[1];

const MapComponent: React.FC<MapProps> = ({
  aoi,
  anomalies,
  product,
  visibleImages,
  selectedAnomalyId,
  movementUrl,
  movementAreas,
  selectedMovementId,
  onMapClick,
  onAnomalyClick,
  onMovementAreaClick,
  onBoundsChange,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const mapReady = useRef(false);

  // Keep latest callbacks without re-binding map events
  const clickCb = useRef(onMapClick);
  const anomalyCb = useRef(onAnomalyClick);
  const movementCb = useRef(onMovementAreaClick);
  clickCb.current = onMapClick;
  anomalyCb.current = onAnomalyClick;
  movementCb.current = onMovementAreaClick;

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
      if (map.current && onBoundsChange) {
        const b = map.current.getBounds();
        onBoundsChange([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
      }
    });

    map.current.on('moveend', () => {
      if (map.current && onBoundsChange) {
        const b = map.current.getBounds();
        onBoundsChange([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
      }
    });

    map.current.on('click', (e) => {
      // Movement areas render on top - query them before the anomalies
      if (map.current?.getLayer('movement-areas-fill')) {
        const movementFeatures = map.current.queryRenderedFeatures(e.point, { layers: ['movement-areas-fill'] });
        if (movementFeatures && movementFeatures.length > 0 && movementCb.current) {
          movementCb.current(movementFeatures[0].properties as MovementAreaProperties);
          return;
        }
      }
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
    map.current.on('mouseenter', 'movement-areas-fill', () => {
      if (map.current) map.current.getCanvas().style.cursor = 'pointer';
    });
    map.current.on('mouseleave', 'movement-areas-fill', () => {
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
    // The movement heatmap and its ranked polygons toggle together
    const movementVisible = (visibleImages?.movement ?? false) && !!movementUrl;
    for (const layerId of ['overlay-movement', 'movement-areas-fill', 'movement-areas-outline']) {
      if (!map.current.getLayer(layerId)) continue;
      map.current.setLayoutProperty(layerId, 'visibility', movementVisible ? 'visible' : 'none');
    }
  };

  useEffect(() => {
    runWhenReady(updateImageVisibility);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleImages, product, movementUrl]);

  // -------------------------------------------------------------------------
  // Period-movement heatmap raster (API-rendered stack of Sentinel-1 visits)
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!map.current || !product || !movementUrl) return;

    runWhenReady(() => {
      if (!map.current || !product || !movementUrl) return;
      const [west, south, east, north] = product.bbox;
      const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [
        [west, north],
        [east, north],
        [east, south],
        [west, south],
      ];
      const existing = map.current.getSource('img-movement') as unknown as
        | { updateImage?: (opts: { url: string; coordinates?: typeof coordinates }) => void }
        | undefined;

      if (!existing) {
        map.current.addSource('img-movement', { type: 'image', url: movementUrl, coordinates });
      } else if (typeof existing.updateImage === 'function') {
        // Same source: swap URL (new period) and coordinates (new AOI) in place
        existing.updateImage({ url: movementUrl, coordinates });
      }

      if (!map.current.getLayer('overlay-movement')) {
        map.current.addLayer(
          {
            id: 'overlay-movement',
            type: 'raster',
            source: 'img-movement',
            paint: {
              'raster-opacity': 0.9,
              'raster-fade-duration': 300,
            },
          },
          map.current.getLayer('anomalies-fill') ? 'anomalies-fill' : undefined,
        );
      }
      updateImageVisibility();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product, movementUrl]);

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

  // -------------------------------------------------------------------------
  // Movement areas: ranked polygons for the selected period
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!map.current || !movementAreas) return;

    runWhenReady(() => {
      if (!map.current || !movementAreas) return;
      const data = movementAreas.areas;
      const existing = map.current.getSource('movement-areas') as maplibregl.GeoJSONSource | undefined;

      if (existing) {
        existing.setData(data);
      } else {
        map.current.addSource('movement-areas', { type: 'geojson', data });
        map.current.addLayer({
          id: 'movement-areas-fill',
          type: 'fill',
          source: 'movement-areas',
          paint: {
            'fill-color': movementColorExpression(),
            'fill-opacity': 0.5,
          },
        });
        map.current.addLayer({
          id: 'movement-areas-outline',
          type: 'line',
          source: 'movement-areas',
          paint: {
            'line-color': '#ff2da5',
            'line-width': ['case', ['==', ['get', 'rank'], 1], 3, 1.5],
          },
        });
      }

      updateMovementSelection();
      updateImageVisibility();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [movementAreas]);

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

  // Highlight the selected movement area (from the ranked list or a map click)
  const updateMovementSelection = () => {
    if (!map.current) return;
    const selectedId = selectedMovementId ?? null;
    if (map.current.getLayer('movement-areas-outline')) {
      map.current.setFilter(
        'movement-areas-outline',
        (selectedId
          ? ['==', ['get', 'id'], selectedId]
          : ['==', ['get', 'rank'], 1]) as unknown as MapFilter,
      );
    }
    if (map.current.getLayer('movement-areas-fill')) {
      map.current.setPaintProperty('movement-areas-fill', 'fill-opacity', selectedId ? 0.75 : 0.5);
    }
  };

  useEffect(() => {
    runWhenReady(updateMovementSelection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMovementId, movementAreas]);

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

  // Fly to the selected movement area when chosen from the ranked list
  useEffect(() => {
    if (!map.current || !selectedMovementId || !movementAreas) return;
    const feature = movementAreas.areas.features.find((f) => f.properties.id === selectedMovementId);
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
  }, [selectedMovementId, movementAreas]);

  return <div ref={mapContainer} className="map-container" style={{ width: '100%', height: '100%' }} />;
};

export default MapComponent;
