/**
 * RealAnalysisPanel
 *
 * Sidebar panel that lets the user:
 *   1. Draw a bounding box on the map (or type lat/lon).
 *   2. Pick a baseline and monitoring date window.
 *   3. Run real Sentinel-1 change detection via POST /api/real/analyse.
 *   4. Browse the ranked anomaly list and three image overlays.
 */

import React, { useState } from 'react';
import {
  runRealAnalysis,
  type RealAnalyseRequest,
  type RealAnalysisResult,
  type RealAnomalyProperties,
} from '../api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TODAY = new Date().toISOString().slice(0, 10);
const MONTH_AGO = new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10);
const TWO_MONTHS_AGO = new Date(Date.now() - 60 * 86400_000).toISOString().slice(0, 10);

function fmtArea(m2: number): string {
  if (m2 >= 1e6) return `${(m2 / 1e6).toFixed(2)} km²`;
  if (m2 >= 1e4) return `${(m2 / 1e4).toFixed(1)} ha`;
  return `${m2.toLocaleString()} m²`;
}

function changeColor(db: number): string {
  const mag = Math.abs(db);
  if (mag < 2) return '#aaa';
  if (mag < 4) return '#ffdc00';
  if (mag < 7) return '#ff9600';
  if (mag < 10) return '#ff3c00';
  return '#c80000';
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  drawnBbox: [number, number, number, number] | null;  // [W,S,E,N] from map draw
  onBboxChange: (bbox: [number, number, number, number] | null) => void;
  onAnomalyHover: (id: string | null) => void;
  onResult: (result: RealAnalysisResult | null) => void;
  result: RealAnalysisResult | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const inp: React.CSSProperties = {
  width: '100%',
  backgroundColor: '#2a2a2a',
  border: '1px solid #555',
  borderRadius: 4,
  color: '#e0e0e0',
  padding: '5px 8px',
  fontSize: '0.8rem',
  boxSizing: 'border-box',
};

const label: React.CSSProperties = {
  fontSize: '0.72rem',
  color: '#aaa',
  marginBottom: 2,
  display: 'block',
};

const sectionTitle: React.CSSProperties = {
  fontSize: '0.88rem',
  fontWeight: 700,
  color: '#e0e0e0',
  marginBottom: 8,
  marginTop: 4,
  borderBottom: '1px solid #444',
  paddingBottom: 4,
};

const chip = (active: boolean): React.CSSProperties => ({
  display: 'inline-block',
  padding: '3px 10px',
  borderRadius: 20,
  fontSize: '0.72rem',
  fontWeight: 600,
  border: `1px solid ${active ? '#4da6ff' : '#555'}`,
  background: active ? '#4da6ff22' : 'transparent',
  color: active ? '#4da6ff' : '#888',
  cursor: 'pointer',
  marginRight: 4,
  marginBottom: 4,
});

// Quick-select presets for the area
const PRESETS: Array<{ label: string; bbox: [number, number, number, number] }> = [
  { label: 'Kigali, Rwanda', bbox: [29.9, -2.0, 30.2, -1.8] },
  { label: 'Lake Muhazi, RW', bbox: [30.28, -1.85, 30.48, -1.68] },
  { label: 'Beirut Port, LB', bbox: [35.50, 33.88, 35.54, 33.91] },
  { label: 'Jakarta, ID', bbox: [106.7, -6.3, 107.0, -6.1] },
];

type ImageTab = 'change' | 'baseline' | 'monitoring' | 's2';

const RealAnalysisPanel: React.FC<Props> = ({
  drawnBbox,
  onBboxChange,
  onAnomalyHover,
  onResult,
  result,
}) => {
  const [bboxStr, setBboxStr] = useState('29.9,-2.0,30.2,-1.8');
  const [baselineStart, setBaselineStart] = useState(TWO_MONTHS_AGO);
  const [baselineEnd,   setBaselineEnd]   = useState(MONTH_AGO);
  const [monStart, setMonStart]           = useState(MONTH_AGO);
  const [monEnd,   setMonEnd]             = useState(TODAY);
  const [zscore, setZscore]               = useState(2.5);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [selectedAnomaly, setSelectedAnomaly] = useState<RealAnomalyProperties | null>(null);
  const [imageTab, setImageTab]           = useState<ImageTab>('change');

  const activeBbox: [number, number, number, number] | null = drawnBbox ?? (() => {
    const parts = bboxStr.split(',').map(Number);
    if (parts.length === 4 && parts.every(isFinite)) {
      return [parts[0], parts[1], parts[2], parts[3]];
    }
    return null;
  })();

  async function handleRun() {
    if (!activeBbox) { setError('Please enter or draw a valid bounding box.'); return; }
    const [w, s, e, n] = activeBbox;
    if (w >= e || s >= n) { setError('Invalid bbox: west must be < east, south < north.'); return; }
    if (baselineStart >= baselineEnd) { setError('Baseline start must be before baseline end.'); return; }
    if (monStart >= monEnd) { setError('Monitoring start must be before monitoring end.'); return; }

    setLoading(true);
    setError(null);
    setSelectedAnomaly(null);
    onResult(null);

    const req: RealAnalyseRequest = {
      bbox: activeBbox,
      baseline_start: baselineStart,
      baseline_end: baselineEnd,
      monitoring_start: monStart,
      monitoring_end: monEnd,
      zscore_threshold: zscore,
      aoi_id: `bbox-${activeBbox.map(v => v.toFixed(2)).join('_')}`,
    };

    try {
      const res = await runRealAnalysis(req);
      onResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function b64src(b64: string): string {
    return `data:image/png;base64,${b64}`;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* ─── Area of interest ─── */}
      <div>
        <p style={sectionTitle}>Area of Interest</p>

        {/* Presets */}
        <div style={{ marginBottom: 8 }}>
          {PRESETS.map(p => (
            <span
              key={p.label}
              style={chip(JSON.stringify(drawnBbox) === JSON.stringify(p.bbox) || bboxStr === p.bbox.join(','))}
              onClick={() => {
                setBboxStr(p.bbox.join(','));
                onBboxChange(p.bbox);
              }}
            >
              {p.label}
            </span>
          ))}
        </div>

        <span style={label}>Bbox (W,S,E,N) — or draw on map</span>
        <input
          style={inp}
          value={drawnBbox ? drawnBbox.join(',') : bboxStr}
          onChange={e => { setBboxStr(e.target.value); onBboxChange(null); }}
          placeholder="29.9,-2.0,30.2,-1.8"
        />
        {drawnBbox && (
          <div style={{ fontSize: '0.7rem', color: '#4da6ff', marginTop: 4 }}>
            Using drawn bbox. <span
              style={{ cursor: 'pointer', textDecoration: 'underline' }}
              onClick={() => onBboxChange(null)}
            >Clear</span>
          </div>
        )}
      </div>

      {/* ─── Date windows ─── */}
      <div>
        <p style={sectionTitle}>Date Windows</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <div>
            <span style={label}>Baseline start</span>
            <input type="date" style={inp} value={baselineStart} onChange={e => setBaselineStart(e.target.value)} />
          </div>
          <div>
            <span style={label}>Baseline end</span>
            <input type="date" style={inp} value={baselineEnd} onChange={e => setBaselineEnd(e.target.value)} />
          </div>
          <div>
            <span style={label}>Monitor start</span>
            <input type="date" style={inp} value={monStart} onChange={e => setMonStart(e.target.value)} />
          </div>
          <div>
            <span style={label}>Monitor end</span>
            <input type="date" style={inp} value={monEnd} onChange={e => setMonEnd(e.target.value)} />
          </div>
        </div>

        <div style={{ marginTop: 8 }}>
          <span style={label}>Z-score threshold: {zscore.toFixed(1)}σ</span>
          <input
            type="range" min={1.5} max={4.0} step={0.1}
            value={zscore}
            onChange={e => setZscore(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#4da6ff' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#666' }}>
            <span>1.5σ (sensitive)</span>
            <span>4.0σ (strict)</span>
          </div>
        </div>
      </div>

      {/* ─── Run button ─── */}
      <button
        onClick={handleRun}
        disabled={loading}
        style={{
          background: loading ? '#333' : 'linear-gradient(135deg, #4da6ff, #0066cc)',
          border: 'none',
          borderRadius: 6,
          color: loading ? '#666' : '#fff',
          padding: '10px 0',
          fontWeight: 700,
          fontSize: '0.9rem',
          cursor: loading ? 'not-allowed' : 'pointer',
          letterSpacing: '0.03em',
          transition: 'all 0.2s',
        }}
      >
        {loading ? '⏳ Fetching Sentinel data…' : '🛰 Run Real Analysis'}
      </button>

      {error && (
        <div style={{
          background: '#3a1212',
          border: '1px solid #c80000',
          borderRadius: 4,
          padding: '8px 10px',
          fontSize: '0.78rem',
          color: '#ff9090',
        }}>
          ⚠ {error}
        </div>
      )}

      {/* ─── Results ─── */}
      {result && (
        <>
          {/* Stats banner */}
          <div style={{
            background: 'linear-gradient(135deg, #1a2a3a, #0a1a2a)',
            border: '1px solid #2a4a6a',
            borderRadius: 6,
            padding: '10px 12px',
            fontSize: '0.8rem',
          }}>
            <div style={{ color: '#4da6ff', fontWeight: 700, marginBottom: 6 }}>
              🛰 {result.satellite} {result.cached ? '(cached)' : ''}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              <span style={{ color: '#aaa' }}>Anomalies</span>
              <strong style={{ color: '#fff' }}>{result.stats.n_anomalies}</strong>
              <span style={{ color: '#aaa' }}>Peak change</span>
              <strong style={{ color: changeColor(result.stats.peak_change_db) }}>
                {result.stats.peak_change_db.toFixed(1)} dB
              </strong>
              <span style={{ color: '#aaa' }}>Changed area</span>
              <strong style={{ color: '#fff' }}>{fmtArea(result.stats.total_change_area_m2)}</strong>
              <span style={{ color: '#aaa' }}>Std change</span>
              <strong style={{ color: '#fff' }}>{result.stats.std_change_db.toFixed(2)} dB</strong>
            </div>
          </div>

          {/* Image tabs */}
          <div>
            <p style={sectionTitle}>Satellite Images</p>
            <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
              {([
                ['change', '🔥 Change'],
                ['baseline', '📡 Baseline'],
                ['monitoring', '📡 Monitoring'],
                ['s2', '🌍 S2 RGB'],
              ] as [ImageTab, string][]).map(([tab, lbl]) => (
                <button
                  key={tab}
                  onClick={() => setImageTab(tab)}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 20,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    border: `1px solid ${imageTab === tab ? '#4da6ff' : '#444'}`,
                    background: imageTab === tab ? '#4da6ff22' : '#222',
                    color: imageTab === tab ? '#4da6ff' : '#888',
                    cursor: 'pointer',
                  }}
                >
                  {lbl}
                </button>
              ))}
            </div>
            {(() => {
              const imgMap: Record<ImageTab, string> = {
                change: result.images.change_overlay,
                baseline: result.images.sar_baseline,
                monitoring: result.images.sar_monitoring,
                s2: result.images.sentinel2_rgb,
              };
              const b64 = imgMap[imageTab];
              if (!b64) return (
                <div style={{ fontSize: '0.78rem', color: '#666', textAlign: 'center', padding: 12 }}>
                  No image available for this tab.
                </div>
              );
              return (
                <img
                  src={b64src(b64)}
                  alt={imageTab}
                  style={{
                    width: '100%',
                    borderRadius: 4,
                    border: '1px solid #333',
                    display: 'block',
                  }}
                />
              );
            })()}
            <div style={{ fontSize: '0.68rem', color: '#555', marginTop: 4 }}>
              Baseline: {result.baseline.start} → {result.baseline.end}  ·  
              Monitor: {result.monitoring.start} → {result.monitoring.end}
            </div>
          </div>

          {/* Anomaly list */}
          {result.anomalies.features.length > 0 && (
            <div>
              <p style={sectionTitle}>Detected Anomalies ({result.anomalies.features.length})</p>
              {result.anomalies.features.map(f => {
                const p = f.properties;
                const isSelected = selectedAnomaly?.id === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => setSelectedAnomaly(isSelected ? null : p)}
                    onMouseEnter={() => onAnomalyHover(p.id)}
                    onMouseLeave={() => onAnomalyHover(null)}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 8,
                      padding: '8px 10px',
                      marginBottom: 6,
                      borderRadius: 5,
                      cursor: 'pointer',
                      background: isSelected ? '#1a2d40' : '#1e1e1e',
                      border: `1px solid ${isSelected ? '#4da6ff' : '#333'}`,
                      transition: 'all 0.15s',
                    }}
                  >
                    <div style={{
                      minWidth: 24,
                      height: 24,
                      borderRadius: '50%',
                      background: changeColor(p.peak_change_db),
                      color: '#111',
                      fontWeight: 800,
                      fontSize: '0.72rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      {p.rank}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'capitalize', color: '#e0e0e0' }}>
                        {p.event_type.replace('_', ' ')}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#888', marginTop: 2 }}>
                        {fmtArea(p.area_m2)} · conf {(p.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontWeight: 700, color: changeColor(p.peak_change_db), fontSize: '0.88rem' }}>
                        {p.peak_change_db > 0 ? '+' : ''}{p.peak_change_db.toFixed(1)} dB
                      </div>
                      <div style={{ fontSize: '0.68rem', color: '#666' }}>peak Δ</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Selected anomaly detail */}
          {selectedAnomaly && (
            <div style={{
              background: '#12212f',
              border: '1px solid #4da6ff',
              borderRadius: 6,
              padding: '10px 12px',
              fontSize: '0.78rem',
            }}>
              <div style={{ color: '#4da6ff', fontWeight: 700, marginBottom: 8 }}>
                Anomaly #{selectedAnomaly.rank} — {selectedAnomaly.event_type.replace('_', ' ')}
              </div>
              {([
                ['Rank',           `#${selectedAnomaly.rank}`],
                ['Area',           fmtArea(selectedAnomaly.area_m2)],
                ['Mean change',    `${selectedAnomaly.mean_change_db.toFixed(2)} dB`],
                ['Peak change',    `${selectedAnomaly.peak_change_db.toFixed(2)} dB`],
                ['Baseline VV',   `${selectedAnomaly.baseline_vv_db.toFixed(1)} dB`],
                ['Monitor VV',    `${selectedAnomaly.monitoring_vv_db.toFixed(1)} dB`],
                ['Pixels',         selectedAnomaly.pixel_count.toLocaleString()],
                ['Confidence',     `${(selectedAnomaly.confidence * 100).toFixed(0)}%`],
                ['Detected at',    selectedAnomaly.detected_at],
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ color: '#888' }}>{k}</span>
                  <strong style={{ color: '#e0e0e0' }}>{v}</strong>
                </div>
              ))}
              <button
                onClick={() => setSelectedAnomaly(null)}
                style={{
                  marginTop: 8, width: '100%',
                  background: 'transparent',
                  border: '1px solid #4da6ff',
                  color: '#4da6ff',
                  borderRadius: 4,
                  padding: '4px 0',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                }}
              >
                Clear selection
              </button>
            </div>
          )}

          {result.anomalies.features.length === 0 && (
            <div style={{
              background: '#1a2a1a',
              border: '1px solid #2a5a2a',
              borderRadius: 4,
              padding: '10px',
              fontSize: '0.78rem',
              color: '#6db86d',
              textAlign: 'center',
            }}>
              ✓ No significant anomalies detected (threshold: {result.stats.zscore_threshold}σ)
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default RealAnalysisPanel;
