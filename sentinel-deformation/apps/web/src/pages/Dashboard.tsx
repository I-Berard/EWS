import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import MapComponent from '../components/Map';
import EventPanel from '../components/EventPanel';
import TimeSeriesChart from '../components/TimeSeriesChart';
import {
  getAnomalies,
  getSummary,
  getTimeSeries,
  getProductMeta,
  listAois,
  imageUrl,
} from '../api';
import type {
  AnomalyProperties,
  AnomalySummary,
  Aoi,
  ImageKind,
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

const Dashboard: React.FC = () => {
  const { data: aois = [], isLoading, isError, error } = useAois();
  const [selectedAoiId, setSelectedAoiId] = useState<string | null>(null);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AnomalyProperties | null>(null);
  const [clickedLocation, setClickedLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [visibleImages, setVisibleImages] = useState<Record<ImageKind, boolean>>({
    sar: false,
    velocity: true,
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
  };

  const handleAnomalyClick = (properties: AnomalyProperties) => {
    setSelectedEvent(properties);
    setSelectedAnomalyId(properties.id);
    setClickedLocation(null);
  };

  const handleRankSelect = (props: AnomalyProperties) => {
    setSelectedAnomalyId(props.id);
    setSelectedEvent(props);
  };

  const toggleImage = (kind: ImageKind) =>
    setVisibleImages((prev) => ({ ...prev, [kind]: !prev[kind] }));

  const topAnomalies: AnomalyProperties[] = anomalies?.features.map((f) => f.properties) ?? [];
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
            <p style={{ fontSize: '0.75rem', color: '#888', marginTop: 4 }}>
              {product.satellite} · {product.acquisition.start} → {product.acquisition.end}
            </p>
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
          onMapClick={handleMapClick}
          onAnomalyClick={handleAnomalyClick}
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
