/**
 * RealDashboard
 *
 * Full-screen layout for the real Sentinel-1 analysis mode:
 *   LEFT  – RealAnalysisPanel (config + results)
 *   RIGHT – MapLibre map with draw-bbox tool, change overlay, anomaly polygons
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import RealAnalysisPanel from '../components/RealAnalysisPanel';
import type { RealAnalysisResult } from '../api';

// ---------------------------------------------------------------------------
// Colour helpers (mirrors RealAnalysisPanel)
// ---------------------------------------------------------------------------

function changeColor(db: number): string {
  const mag = Math.abs(db);
  if (mag < 2) return '#aaa';
  if (mag < 4) return '#ffdc00';
  if (mag < 7) return '#ff9600';
  if (mag < 10) return '#ff3c00';
  return '#c80000';
}

// ---------------------------------------------------------------------------
// Map component for real data
// ---------------------------------------------------------------------------

interface RealMapProps {
  drawnBbox: [number, number, number, number] | null;
  onBboxDrawn: (bbox: [number, number, number, number]) => void;
  result: RealAnalysisResult | null;
  hoveredAnomalyId: string | null;
}

const SOURCE_ANOMALIES = 'real-anomalies';
const LAYER_FILL      = 'real-anomaly-fill';
const LAYER_LINE      = 'real-anomaly-line';
const SOURCE_BBOX     = 'drawn-bbox';
const LAYER_BBOX_FILL = 'drawn-bbox-fill';
const LAYER_BBOX_LINE = 'drawn-bbox-line';

const RealMap: React.FC<RealMapProps> = ({ drawnBbox, onBboxDrawn, result, hoveredAnomalyId }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<maplibregl.Map | null>(null);
  const readyRef     = useRef(false);

  // Drawing state
  const isDrawingRef    = useRef(false);
  const drawStartRef    = useRef<[number, number] | null>(null);
  // (draw marker not used, removed)
  const drawRectElem    = useRef<HTMLDivElement | null>(null);

  // Keep refs stable
  const onBboxDrawnRef  = useRef(onBboxDrawn);
  onBboxDrawnRef.current = onBboxDrawn;

  // ── Map init ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const m = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [30.05, -1.95],
      zoom: 10,
      dragRotate: false, // Prevent rotation when shift-dragging
      boxZoom: false,    // Prevent native box zoom when shift-dragging
    });

    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.addControl(new maplibregl.ScaleControl(), 'bottom-right');

    m.on('load', () => {
      readyRef.current = true;

      // ── Bbox rectangle layer ─────────────────────────────────────────────
      m.addSource(SOURCE_BBOX, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      m.addLayer({
        id: LAYER_BBOX_FILL,
        type: 'fill',
        source: SOURCE_BBOX,
        paint: { 'fill-color': '#4da6ff', 'fill-opacity': 0.08 },
      });
      m.addLayer({
        id: LAYER_BBOX_LINE,
        type: 'line',
        source: SOURCE_BBOX,
        paint: { 'line-color': '#4da6ff', 'line-width': 2, 'line-dasharray': [4, 3] },
      });

      // ── Anomaly layers ───────────────────────────────────────────────────
      m.addSource(SOURCE_ANOMALIES, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      m.addLayer({
        id: LAYER_FILL,
        type: 'fill',
        source: SOURCE_ANOMALIES,
        paint: {
          'fill-color': [
            'interpolate', ['linear'],
            ['abs', ['coalesce', ['get', 'peak_change_db'], 0]],
            2, '#ffdc00', 4, '#ff9600', 7, '#ff3c00', 10, '#c80000', 15, '#820000',
          ],
          'fill-opacity': ['case', ['==', ['get', 'id'], ''], 0.35, 0.45],
        },
      });
      m.addLayer({
        id: LAYER_LINE,
        type: 'line',
        source: SOURCE_ANOMALIES,
        paint: { 'line-color': '#fff', 'line-width': 1, 'line-opacity': 0.6 },
      });

      // Popup on click
      const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: '240px' });
      m.on('click', LAYER_FILL, (e) => {
        const feat = e.features?.[0];
        if (!feat) return;
        const p = feat.properties as Record<string, unknown>;
        const html = `
          <div style="font-size:0.78rem;color:#e0e0e0;background:#1e1e1e;padding:6px">
            <strong style="color:#4da6ff">#${p.rank} ${String(p.event_type).replace('_',' ')}</strong><br/>
            Peak Δ: <strong style="color:${changeColor(Number(p.peak_change_db))}">${Number(p.peak_change_db).toFixed(1)} dB</strong><br/>
            Mean Δ: ${Number(p.mean_change_db).toFixed(1)} dB<br/>
            Area: ${Number(p.area_m2).toLocaleString()} m²<br/>
            Confidence: ${(Number(p.confidence) * 100).toFixed(0)}%
          </div>`;
        popup.setLngLat(e.lngLat).setHTML(html).addTo(m);
      });
      m.on('mouseenter', LAYER_FILL, () => { m.getCanvas().style.cursor = 'pointer'; });
      m.on('mouseleave', LAYER_FILL, () => { m.getCanvas().style.cursor = ''; });
    });

    mapRef.current = m;
    return () => { m.remove(); mapRef.current = null; readyRef.current = false; };
  }, []);

  // ── Draw interaction (shift+drag) ────────────────────────────────────────
  useEffect(() => {
    // Capture map reference at effect registration time (stable for the lifetime of the map)
    const capturedMap = mapRef.current;
    if (!capturedMap) return;

    const canvasEl = capturedMap.getCanvas();

    function screenToLngLat(x: number, y: number): [number, number] {
      const rect = canvasEl.getBoundingClientRect();
      const ll = capturedMap!.unproject([x - rect.left, y - rect.top]);
      return [ll.lng, ll.lat];
    }

    function onMouseDown(e: MouseEvent) {
      if (!e.shiftKey) return;
      e.preventDefault();
      isDrawingRef.current = true;
      drawStartRef.current = screenToLngLat(e.clientX, e.clientY);
      capturedMap!.dragPan.disable();
      canvasEl.style.cursor = 'crosshair';

      const rect = document.createElement('div');
      rect.style.cssText = [
        'position:absolute', 'border:2px dashed #4da6ff',
        'background:rgba(77,166,255,0.1)', 'pointer-events:none',
        'display:none', 'z-index:10',
      ].join(';');
      containerRef.current?.appendChild(rect);
      drawRectElem.current = rect;
    }

    function onMouseMove(e: MouseEvent) {
      if (!isDrawingRef.current || !drawStartRef.current || !drawRectElem.current) return;
      const rect = canvasEl.getBoundingClientRect();
      const startLL = drawStartRef.current;
      const startPx = capturedMap!.project(startLL as maplibregl.LngLatLike);
      const curPx   = { x: e.clientX - rect.left, y: e.clientY - rect.top };

      const x = Math.min(startPx.x, curPx.x);
      const y = Math.min(startPx.y, curPx.y);
      const w = Math.abs(startPx.x - curPx.x);
      const h = Math.abs(startPx.y - curPx.y);

      const r = drawRectElem.current;
      r.style.display = 'block';
      r.style.left   = `${x}px`;
      r.style.top    = `${y}px`;
      r.style.width  = `${w}px`;
      r.style.height = `${h}px`;
    }

    function onMouseUp(e: MouseEvent) {
      if (!isDrawingRef.current || !drawStartRef.current) return;
      isDrawingRef.current = false;
      capturedMap!.dragPan.enable();
      canvasEl.style.cursor = '';

      if (drawRectElem.current) {
        drawRectElem.current.remove();
        drawRectElem.current = null;
      }

      const endLL = screenToLngLat(e.clientX, e.clientY);
      const [x0, y0] = drawStartRef.current;
      const [x1, y1] = endLL;
      const w = Math.abs(x1 - x0);
      const h = Math.abs(y1 - y0);
      if (w < 0.001 || h < 0.001) return;

      const bbox: [number, number, number, number] = [
        Math.min(x0, x1), Math.min(y0, y1),
        Math.max(x0, x1), Math.max(y0, y1),
      ];
      onBboxDrawnRef.current(bbox);
      drawStartRef.current = null;
    }

    window.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  // ── Update bbox rect on map ──────────────────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !readyRef.current) return;

    const src = m.getSource(SOURCE_BBOX) as maplibregl.GeoJSONSource | undefined;
    if (!src) return;

    if (!drawnBbox) {
      src.setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const [w, s, e, n] = drawnBbox;
    src.setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'Polygon',
          coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        },
      }],
    });
    m.fitBounds([[w, s], [e, n]], { padding: 60, maxZoom: 14 });
  }, [drawnBbox]);

  // ── Update anomaly polygons ──────────────────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !readyRef.current) return;
    const src = m.getSource(SOURCE_ANOMALIES) as maplibregl.GeoJSONSource | undefined;
    if (!src) return;

    if (!result) {
      src.setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    src.setData(result.anomalies as unknown as Parameters<maplibregl.GeoJSONSource['setData']>[0]);
  }, [result]);

  // ── Highlight hovered anomaly ────────────────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !readyRef.current) return;
    m.setPaintProperty(LAYER_FILL, 'fill-opacity',
      hoveredAnomalyId
        ? ['case', ['==', ['get', 'id'], hoveredAnomalyId], 0.75, 0.35]
        : 0.45
    );
  }, [hoveredAnomalyId]);

  // ── Change overlay ───────────────────────────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !readyRef.current || !result) return;
    if (!result.images.change_overlay) return;

    const [w, s, e, n] = result.bbox;
    const SRC_ID = 'real-change-overlay';
    const LYR_ID = 'real-change-overlay-layer';

    if (m.getLayer(LYR_ID)) m.removeLayer(LYR_ID);
    if (m.getSource(SRC_ID)) m.removeSource(SRC_ID);

    m.addSource(SRC_ID, {
      type: 'image',
      url: `data:image/png;base64,${result.images.change_overlay}`,
      coordinates: [[w, n], [e, n], [e, s], [w, s]],
    });
    m.addLayer({
      id: LYR_ID,
      type: 'raster',
      source: SRC_ID,
      paint: { 'raster-opacity': 0.7 },
    }, LAYER_FILL);
  }, [result]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {/* Draw hint */}
      <div style={{
        position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
        background: 'rgba(0,0,0,0.7)', color: '#4da6ff', padding: '5px 14px',
        borderRadius: 20, fontSize: '0.72rem', fontWeight: 600, pointerEvents: 'none',
        border: '1px solid #4da6ff44',
      }}>
        ⇧ Shift + drag to draw analysis area
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Real Dashboard (page)
// ---------------------------------------------------------------------------

const RealDashboard: React.FC = () => {
  const [drawnBbox, setDrawnBbox] = useState<[number, number, number, number] | null>(null);
  const [result, setResult]       = useState<RealAnalysisResult | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleBboxDrawn = useCallback((bbox: [number, number, number, number]) => {
    setDrawnBbox(bbox);
    setResult(null);
  }, []);

  return (
    <div className="dashboard">
      {/* ── Sidebar ── */}
      <div
        className="sidebar"
        style={{ width: 320, minWidth: 320, padding: '1rem' }}
      >
        {/* Header */}
        <div style={{ marginBottom: 4 }}>
          <h2 style={{ margin: 0, fontSize: '1rem', color: '#e0e0e0' }}>
            Real Satellite Analysis
          </h2>
          <span style={{
            display: 'inline-block',
            marginTop: 4,
            background: 'linear-gradient(135deg, #4da6ff, #0066cc)',
            color: '#fff',
            padding: '2px 10px',
            borderRadius: 20,
            fontSize: '0.7rem',
            fontWeight: 700,
            letterSpacing: '0.06em',
          }}>
            SENTINEL-1 GRD · LIVE
          </span>
        </div>

        <RealAnalysisPanel
          drawnBbox={drawnBbox}
          onBboxChange={setDrawnBbox}
          onAnomalyHover={setHoveredId}
          onResult={setResult}
          result={result}
        />

        {/* Legend */}
        <div style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid #333' }}>
          <div style={{ fontSize: '0.72rem', color: '#aaa', marginBottom: 4, fontWeight: 600 }}>
            |ΔdB| change legend
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[
              [2, '#ffdc00'],
              [4, '#ff9600'],
              [7, '#ff3c00'],
              [10, '#c80000'],
              [15, '#820000'],
            ].map(([db, color]) => (
              <span key={String(db)} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: '0.7rem', color: '#aaa' }}>
                <span style={{ width: 10, height: 10, background: String(color), borderRadius: 2, display: 'inline-block' }} />
                ≤{db} dB
              </span>
            ))}
          </div>
          <div style={{ marginTop: 8, fontSize: '0.7rem', color: '#555', lineHeight: 1.4 }}>
            Negative ΔdB → backscatter decrease (possible flooding, subsidence, vegetation loss).<br/>
            Positive ΔdB → backscatter increase (possible construction, debris, surface change).
          </div>
        </div>
      </div>

      {/* ── Map ── */}
      <div className="map-container">
        <RealMap
          drawnBbox={drawnBbox}
          onBboxDrawn={handleBboxDrawn}
          result={result}
          hoveredAnomalyId={hoveredId}
        />
      </div>
    </div>
  );
};

export default RealDashboard;
