import React, { useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import MapComponent from '../components/Map';
import EventPanel from '../components/EventPanel';
import TimeSeriesChart from '../components/TimeSeriesChart';
import {
  getAnomalies,
  getSummary,
  getTimeSeries,
  getProductMeta,
  getMovement,
  listAois,
  imageUrl,
  movementImageUrl,
  visitImageUrl,
  getRealTimeline,
} from '../api';
import type {
  AnomalyProperties,
  AnomalySummary,
  Aoi,
  ImageKind,
  MovementAnalysis,
  MovementAreaProperties,
  ProductMeta,
  TimeSeries,
} from '../api';

function useAois() {
  return useQuery<Aoi[]>({ queryKey: ['aois'], queryFn: listAois });
}

const velocityColor = (v: number): string => {
  const mag = Math.abs(v);
  if (mag <= 3) return '#ffdc00';
  if (mag <= 8) return '#ff9600';
  if (mag <= 14) return '#ff3c00';
  if (mag <= 20) return '#c80000';
  return '#820000';
};

const LEGEND_STEPS: Array<[number, string]> = [
  [3, '#ffdc00'],
  [8, '#ff9600'],
  [14, '#ff3c00'],
  [20, '#c80000'],
  [30, '#820000'],
];

// Magnitude ramp for cumulative movement (mm over the selected period) -
// mirrors MOVEMENT_RAMP in the backend engine.
const MOVEMENT_LEGEND_STEPS: Array<[number, string]> = [
  [1, '#966eff'],
  [4, '#cd3ceb'],
  [10, '#ff2da5'],
  [18, '#ff8c3c'],
  [28, '#ffeb8c'],
];

const movementColor = (m: number): string => {
  const mag = Math.abs(m);
  if (mag <= 1) return '#966eff';
  if (mag <= 4) return '#cd3ceb';
  if (mag <= 10) return '#ff2da5';
  if (mag <= 18) return '#ff8c3c';
  return '#ffeb8c';
};

const dateInputStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  backgroundColor: '#3d3d3d',
  border: '1px solid #555',
  borderRadius: 4,
  color: '#e0e0e0',
  padding: '4px 6px',
  fontSize: '0.78rem',
};

const RealTimelapsePlayer: React.FC<{ aoiId: string; bbox: [number, number, number, number] }> = ({ aoiId, bbox }) => {
  const { data: timeline, isLoading, isError } = useQuery({
    queryKey: ['real-timeline', aoiId, bbox],
    queryFn: () => getRealTimeline(aoiId, bbox),
    enabled: !!aoiId && !!bbox,
  });
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    let interval: number;
    if (isPlaying && timeline && timeline.length > 0) {
      interval = window.setInterval(() => {
        setCurrentIndex((prev) => (prev + 1) % timeline.length);
      }, 500);
    }
    return () => window.clearInterval(interval);
  }, [isPlaying, timeline]);

  if (isLoading) return <div style={{marginTop: '1rem', fontSize: '0.85rem'}}>Loading real satellite data...</div>;
  if (isError) return <div style={{marginTop: '1rem', fontSize: '0.85rem', color: '#ff6b6b'}}>Failed to load real data.</div>;
  if (!timeline || timeline.length === 0) return <div style={{marginTop: '1rem', fontSize: '0.85rem'}}>No real imagery found for this area.</div>;

  const currentItem = timeline[currentIndex];
  
  // CSS Cropping logic
  const [T_minX, T_minY, T_maxX, T_maxY] = bbox;
  const [I_minX, I_minY, I_maxX, I_maxY] = currentItem.image_bbox || [T_minX, T_minY, T_maxX, T_maxY];
  
  const scaleX = (I_maxX - I_minX) / (T_maxX - T_minX);
  const scaleY = (I_maxY - I_minY) / (T_maxY - T_minY);
  
  const left = -((T_minX - I_minX) / (T_maxX - T_minX)) * 100;
  const top = -((I_maxY - T_maxY) / (T_maxY - T_minY)) * 100;

  return (
    <div style={{ marginTop: '1rem', backgroundColor: '#3d3d3d', padding: 10, borderRadius: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ fontSize: '0.95rem', margin: 0 }}>Real Data Timelapse</h3>
        <button 
          onClick={() => setIsPlaying(!isPlaying)}
          style={{
            background: isPlaying ? '#ff6b6b' : '#4dc3ff',
            color: '#111',
            border: 'none',
            borderRadius: 4,
            padding: '4px 8px',
            cursor: 'pointer',
            fontSize: '0.75rem',
            fontWeight: 'bold'
          }}
        >
          {isPlaying ? 'Pause' : 'Play'}
        </button>
      </div>
      <div style={{ position: 'relative', width: '100%', aspectRatio: '1/1', backgroundColor: '#222', borderRadius: 4, overflow: 'hidden' }}>
        <img 
          src={currentItem.thumbnail_url} 
          alt={`Sentinel-1 on ${currentItem.date}`}
          style={{ 
            position: 'absolute',
            left: `${left}%`,
            top: `${top}%`,
            width: `${scaleX * 100}%`, 
            height: `${scaleY * 100}%`, 
            objectFit: 'fill'
          }}
        />
        <div style={{ position: 'absolute', bottom: 8, left: 8, background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: 4, fontSize: '0.7rem' }}>
          {new Date(currentItem.date).toLocaleDateString()} ({currentIndex + 1} / {timeline.length})
        </div>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { data: aois = [], isLoading, isError, error } = useAois();
  const [selectedAoiId, setSelectedAoiId] = useState<string | null>(null);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AnomalyProperties | null>(null);
  const [clickedLocation, setClickedLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [selectedMovementId, setSelectedMovementId] = useState<string | null>(null);
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [mapBounds, setMapBounds] = useState<[number, number, number, number] | null>(null);
  const [stitchBbox, setStitchBbox] = useState<[number, number, number, number] | null>(null);
  const [visibleImages, setVisibleImages] = useState<Record<ImageKind, boolean>>({
    sar: false,
    velocity: false,
    movement: true,
  });

  const aoi = useMemo(
    () => aois.find((a) => a.id === selectedAoiId) ?? aois[0] ?? null,
    [aois, selectedAoiId],
  );

  const { data: product } = useQuery<ProductMeta>({
    queryKey: ['product', aoi?.id],
    queryFn: () => getProductMeta(aoi!.id),
    enabled: !!aoi,
  });

  // Default the analysis period to the full Sentinel-1 acquisition window
  const effectiveStart = periodStart || product?.acquisition.start || '';
  const effectiveEnd = periodEnd || product?.acquisition.end || '';
  const periodValid = !!effectiveStart && !!effectiveEnd && effectiveStart < effectiveEnd;

  // Stack every Sentinel-1 visit inside the period and rank moved areas
  const {
    data: movement,
    isLoading: movementLoading,
    isError: movementFailed,
    error: movementError,
  } = useQuery<MovementAnalysis>({
    queryKey: ['movement', aoi?.id, effectiveStart, effectiveEnd],
    queryFn: () => getMovement(aoi!.id, effectiveStart, effectiveEnd),
    enabled: !!aoi && periodValid,
  });

  const movementUrl = aoi && periodValid ? movementImageUrl(aoi.id, effectiveStart, effectiveEnd) : null;

  const { data: anomalies } = useQuery({
    queryKey: ['anomalies', aoi?.id],
    queryFn: () => getAnomalies(aoi!.id),
    enabled: !!aoi,
  });

  const { data: summary } = useQuery<AnomalySummary>({
    queryKey: ['summary', aoi?.id],
    queryFn: () => getSummary(aoi!.id),
    enabled: !!aoi,
  });

  const { data: timeSeries } = useQuery<TimeSeries>({
    queryKey: ['timeseries', aoi?.id, clickedLocation?.lat, clickedLocation?.lng],
    queryFn: () => getTimeSeries(aoi!.id, clickedLocation!.lat, clickedLocation!.lng),
    enabled: !!aoi && !!clickedLocation,
  });

  const handleMapClick = (lngLat: { lat: number; lng: number }) => {
    setClickedLocation(lngLat);
    setSelectedEvent(null);
    setSelectedAnomalyId(null);
    setSelectedMovementId(null);
  };

  const handleAnomalyClick = (properties: AnomalyProperties) => {
    setSelectedEvent(properties);
    setSelectedAnomalyId(properties.id);
    setClickedLocation(null);
    setSelectedMovementId(null);
  };

  const handleMovementAreaClick = (properties: MovementAreaProperties) => {
    setSelectedMovementId(properties.id);
    setSelectedEvent(null);
    setSelectedAnomalyId(null);
    setClickedLocation(null);
  };

  const handleRankSelect = (props: AnomalyProperties) => {
    setSelectedAnomalyId(props.id);
    setSelectedEvent(props);
  };

  const toggleImage = (kind: ImageKind) =>
    setVisibleImages((prev) => ({ ...prev, [kind]: !prev[kind] }));

  const topAnomalies: AnomalyProperties[] = anomalies?.features.map((f) => f.properties) ?? [];
  const movementAreas: MovementAreaProperties[] = movement?.areas.features.map((f) => f.properties) ?? [];
  const selectedMovement = movementAreas.find((p) => p.id === selectedMovementId) ?? null;
  const aoiId = aoi?.id ?? '';

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div>
          <h2>Areas of Interest</h2>
          <span className="demo-badge" style={{ marginLeft: 0, marginBottom: '1rem', display: 'inline-block' }}>
            DEMO MODE
          </span>
          <div style={{ marginTop: '0.5rem' }}>
            {isLoading && <p style={{ color: '#888' }}>Loading AOIs…</p>}
            {isError && <p style={{ color: '#ff6b6b' }}>Failed to load AOIs: {(error as Error)?.message}</p>}
            {aois.map((a) => (
              <div
                key={a.id}
                style={{
                  padding: '10px',
                  backgroundColor: aoi?.id === a.id ? '#4da6ff33' : '#3d3d3d',
                  border: aoi?.id === a.id ? '1px solid #4da6ff' : '1px solid transparent',
                  cursor: 'pointer',
                  borderRadius: '4px',
                  marginBottom: '6px',
                }}
                onClick={() => {
                  setSelectedAoiId(a.id);
                  setSelectedAnomalyId(null);
                  setSelectedEvent(null);
                  setSelectedMovementId(null);
                  setClickedLocation(null);
                }}
              >
                {a.name}
              </div>
            ))}
          </div>
        </div>

        {summary && (
          <div style={{ marginTop: '1rem', padding: '10px', backgroundColor: '#3d3d3d', borderRadius: '4px', fontSize: '0.85rem' }}>
            <strong style={{ color: '#4da6ff' }}>AOI Summary</strong>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
              <span>Anomalies</span>
              <strong>{summary.n_anomalies}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Peak subsidence</span>
              <strong style={{ color: '#ff6b6b' }}>
                {summary.max_subsidence_mm_yr != null ? `${summary.max_subsidence_mm_yr.toFixed(1)} mm/yr` : '–'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Peak uplift</span>
              <strong style={{ color: '#4dc3ff' }}>
                {summary.max_uplift_mm_yr != null ? `${summary.max_uplift_mm_yr.toFixed(1)} mm/yr` : '–'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Affected area</span>
              <strong>{(summary.total_area_m2 / 1e6).toFixed(2)} km²</strong>
            </div>
          </div>
        )}

        {product && (
          <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Movement in Period</h3>
            <div style={{ fontSize: '0.75rem', color: '#aaa', marginBottom: 6 }}>
              Overlay the Sentinel-1 visits taken between:
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="date"
                aria-label="Period start"
                value={effectiveStart}
                min={product.acquisition.start}
                max={product.acquisition.end}
                onChange={(e) => {
                  setPeriodStart(e.target.value);
                  setSelectedMovementId(null);
                }}
                style={dateInputStyle}
              />
              <input
                type="date"
                aria-label="Period end"
                value={effectiveEnd}
                min={product.acquisition.start}
                max={product.acquisition.end}
                onChange={(e) => {
                  setPeriodEnd(e.target.value);
                  setSelectedMovementId(null);
                }}
                style={dateInputStyle}
              />
            </div>
            {!periodValid && (
              <p style={{ fontSize: '0.75rem', color: '#ff6b6b', marginTop: 4 }}>
                End date must be after start date.
              </p>
            )}

            {periodValid && movementLoading && (
              <p style={{ fontSize: '0.78rem', color: '#888', marginTop: 6 }}>
                Stacking Sentinel-1 visits…
              </p>
            )}
            {periodValid && movementFailed && (
              <p style={{ fontSize: '0.75rem', color: '#ff6b6b', marginTop: 6 }}>
                {(movementError as Error)?.message}
              </p>
            )}

            {movement && (
              <>
                <div style={{ marginTop: 8, fontSize: '0.78rem', color: '#ccc' }}>
                  <strong style={{ color: '#ff2da5' }}>{movement.n_acquisitions}</strong> visits
                  overlaid · detect ≥ {movement.threshold_mm.toFixed(1)} mm
                </div>

                {/* The actual Sentinel-1 images being stacked */}
                <div
                  style={{
                    display: 'flex',
                    gap: 4,
                    overflowX: 'auto',
                    marginTop: 6,
                    paddingBottom: 4,
                  }}
                >
                  {movement.acquisitions.map((acq) => (
                    <img
                      key={acq.id}
                      src={visitImageUrl(aoiId, acq.index)}
                      loading="lazy"
                      title={`${acq.id} · ${acq.date}`}
                      alt={`Sentinel-1 visit ${acq.date}`}
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: 3,
                        flex: '0 0 auto',
                        objectFit: 'cover',
                        opacity: 0.9,
                      }}
                    />
                  ))}
                </div>

                <div
                  style={{
                    marginTop: 8,
                    padding: '8px 10px',
                    backgroundColor: '#3d3d3d',
                    borderRadius: 4,
                    fontSize: '0.82rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Peak movement</span>
                    <strong style={{ color: '#ff2da5' }}>
                      {movement.stats.max_movement_magnitude_mm.toFixed(1)} mm
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Detected areas</span>
                    <strong>{movement.stats.n_areas}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Affected area</span>
                    <strong>{(movement.stats.total_area_m2 / 1e6).toFixed(2)} km²</strong>
                  </div>
                </div>

                {movementAreas.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <strong style={{ fontSize: '0.85rem' }}>Highest movement</strong>
                    {movementAreas.slice(0, 5).map((props) => (
                      <div
                        key={props.id}
                        onClick={() => setSelectedMovementId(props.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 10px',
                          marginTop: 6,
                          borderRadius: 4,
                          cursor: 'pointer',
                          backgroundColor:
                            selectedMovementId === props.id ? '#ff2da533' : '#3d3d3d',
                          border:
                            selectedMovementId === props.id
                              ? '1px solid #ff2da5'
                              : '1px solid transparent',
                        }}
                      >
                        <span
                          style={{
                            minWidth: 22,
                            height: 22,
                            borderRadius: '50%',
                            background: movementColor(props.peak_movement_mm),
                            color: '#111',
                            fontWeight: 700,
                            fontSize: '0.75rem',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {props.rank}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>
                            {props.event_type} · #{props.rank}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#aaa' }}>
                            {props.n_acquisitions} visits · {props.area_m2.toLocaleString()} m²
                          </div>
                        </div>
                        <strong
                          style={{
                            color: props.peak_movement_mm < 0 ? '#ff6b6b' : '#4dc3ff',
                            fontSize: '0.85rem',
                          }}
                        >
                          {props.peak_movement_mm.toFixed(1)} mm
                        </strong>
                      </div>
                    ))}
                  </div>
                )}

                {movementAreas.length === 0 && !movementLoading && (
                  <p style={{ fontSize: '0.75rem', color: '#888', marginTop: 8 }}>
                    No area moved more than {movement.threshold_mm.toFixed(1)} mm during this period.
                  </p>
                )}

                {selectedMovement && (
                  <div
                    style={{
                      marginTop: 8,
                      padding: '8px 10px',
                      backgroundColor: '#4a2140',
                      border: '1px solid #ff2da5',
                      borderRadius: 4,
                      fontSize: '0.8rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Period</span>
                      <strong>
                        {selectedMovement.period_start} → {selectedMovement.period_end}
                      </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Peak movement</span>
                      <strong style={{ color: '#ff2da5' }}>
                        {selectedMovement.peak_movement_mm.toFixed(1)} mm
                      </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Mean movement</span>
                      <strong>{selectedMovement.mean_movement_mm.toFixed(1)} mm</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Mean rate</span>
                      <strong>{selectedMovement.mean_velocity_mm_yr.toFixed(1)} mm/yr</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Coherence</span>
                      <strong>{selectedMovement.coherence.toFixed(2)}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Confidence</span>
                      <strong>{(selectedMovement.confidence * 100).toFixed(0)}%</strong>
                    </div>
                    <button
                      onClick={() => setSelectedMovementId(null)}
                      style={{
                        marginTop: 8,
                        width: '100%',
                        background: 'transparent',
                        border: '1px solid #ff2da5',
                        color: '#ff2da5',
                        borderRadius: 4,
                        padding: '4px 0',
                        cursor: 'pointer',
                        fontSize: '0.78rem',
                      }}
                    >
                      Clear selection
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {topAnomalies.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Highest Displacement</h3>
            {topAnomalies.slice(0, 5).map((props) => (
              <div
                key={props.id}
                onClick={() => handleRankSelect(props)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 10px',
                  marginBottom: 6,
                  borderRadius: 4,
                  cursor: 'pointer',
                  backgroundColor: selectedAnomalyId === props.id ? '#ff222233' : '#3d3d3d',
                  border: selectedAnomalyId === props.id ? '1px solid #ff2222' : '1px solid transparent',
                }}
              >
                <span
                  style={{
                    minWidth: 22,
                    height: 22,
                    borderRadius: '50%',
                    background: velocityColor(props.mean_velocity),
                    color: '#111',
                    fontWeight: 700,
                    fontSize: '0.75rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {props.rank}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>
                    {props.event_type} · #{props.rank}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#aaa' }}>
                    {props.area_m2.toLocaleString()} m² · coh {props.coherence.toFixed(2)}
                  </div>
                </div>
                <strong style={{ color: props.mean_velocity < 0 ? '#ff6b6b' : '#4dc3ff', fontSize: '0.85rem' }}>
                  {props.max_velocity.toFixed(1)} mm/yr
                </strong>
              </div>
            ))}
          </div>
        )}

        {timeSeries && clickedLocation && (
          <TimeSeriesChart data={timeSeries.points.map((p) => ({ date: p.date, displacement: p.displacement_mm }))} location={clickedLocation} />
        )}

        {product && (
          <div style={{ marginTop: '1rem' }}>
            <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Product Layers</h3>
            {(['sar', 'velocity'] as ImageKind[]).map((kind) => (
              <label
                key={kind}
                style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer', marginBottom: 6 }}
              >
                <input type="checkbox" checked={visibleImages[kind]} onChange={() => toggleImage(kind)} />
                {kind === 'sar' ? 'SAR backscatter' : 'Velocity overlay'}
                <span style={{ color: '#888', fontSize: '0.75rem' }}>
                  {product.width}×{product.height}px
                </span>
                <img
                  src={imageUrl(aoiId, kind)}
                  alt={`${kind} thumbnail`}
                  style={{ width: 40, height: 40, marginLeft: 'auto', borderRadius: 3, objectFit: 'cover' }}
                />
              </label>
            ))}
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: '0.85rem',
                cursor: 'pointer',
                marginBottom: 6,
              }}
            >
              <input
                type="checkbox"
                checked={visibleImages.movement}
                onChange={() => toggleImage('movement')}
              />
              Movement heatmap (period)
              <span style={{ color: '#888', fontSize: '0.75rem' }}>
                {movement?.n_acquisitions ?? 0} visits
              </span>
              {movementUrl && (
                <img
                  src={movementUrl}
                  alt="movement thumbnail"
                  style={{
                    width: 40,
                    height: 40,
                    marginLeft: 'auto',
                    borderRadius: 3,
                    objectFit: 'cover',
                  }}
                />
              )}
            </label>
            <p style={{ fontSize: '0.75rem', color: '#888', marginTop: 4 }}>
              {product.satellite} · {product.acquisition.start} → {product.acquisition.end}
            </p>
          </div>
        )}

        {aoiId && (
          <div>
            <RealTimelapsePlayer aoiId={aoiId} bbox={stitchBbox || product?.bbox || [-180, -90, 180, 90]} />
            <button
              onClick={() => {
                if (mapBounds) setStitchBbox(mapBounds);
              }}
              style={{
                marginTop: 6,
                width: '100%',
                background: '#4a2140',
                border: '1px solid #ff2da5',
                color: '#e0e0e0',
                borderRadius: 4,
                padding: '6px 0',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              Stitch Current Map View
            </button>
            <button
              onClick={() => {
                const b = stitchBbox || product?.bbox || [-180, -90, 180, 90];
                window.history.pushState(null, '', `/video?aoiId=${aoiId}&bbox=${b.join(',')}`);
              }}
              style={{
                marginTop: 6,
                width: '100%',
                background: '#2c3e50',
                border: '1px solid #4dc3ff',
                color: '#e0e0e0',
                borderRadius: 4,
                padding: '6px 0',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              Open Full-Screen High-Contrast Video
            </button>
          </div>
        )}

        <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: '#aaa' }}>
          <strong style={{ color: '#ccc' }}>|velocity| legend</strong>
          <div style={{ display: 'flex', gap: 6, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            {LEGEND_STEPS.map(([mm, color]) => (
              <span key={color} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 10, height: 10, background: color, borderRadius: 2, display: 'inline-block' }} />
                ≤{mm}
              </span>
            ))}
            <span style={{ marginLeft: 8, color: '#4dc3ff' }}>▲ uplift</span>
          </div>
        </div>

        <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#aaa' }}>
          <strong style={{ color: '#ff2da5' }}>period movement legend</strong>
          <div style={{ display: 'flex', gap: 6, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            {MOVEMENT_LEGEND_STEPS.map(([mm, color]) => (
              <span key={color} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    background: color,
                    borderRadius: 2,
                    display: 'inline-block',
                  }}
                />
                ≤{mm} mm
              </span>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 'auto' }}>
          <p style={{ fontSize: '0.8rem', color: '#888' }}>
            <strong>Note:</strong> InSAR measurements represent displacement along the radar Line of Sight (LOS),
            not true 3D movement. Demo data is synthetic.
          </p>
        </div>
      </div>

      <div className="map-container" style={{ flex: 1 }}>
        <MapComponent
          aoi={aoi}
          anomalies={anomalies ?? null}
          product={product ?? null}
          visibleImages={visibleImages}
          selectedAnomalyId={selectedAnomalyId}
          movementUrl={movementUrl}
          movementAreas={movement ?? null}
          selectedMovementId={selectedMovementId}
          onMapClick={handleMapClick}
          onAnomalyClick={handleAnomalyClick}
          onMovementAreaClick={handleMovementAreaClick}
          onBoundsChange={setMapBounds}
        />
      </div>

      {selectedEvent && (
        <EventPanel
          event={selectedEvent}
          onClose={() => {
            setSelectedEvent(null);
            setSelectedAnomalyId(null);
          }}
        />
      )}
    </div>
  );
};

export default Dashboard;
