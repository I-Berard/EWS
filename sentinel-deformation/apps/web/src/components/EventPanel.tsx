import React from 'react';

interface DeformationEvent {
  id: string;
  event_type: string;
  area_m2: number;
  mean_velocity: number;
  max_velocity: number;
  coherence: number;
  confidence: number;
  detected_at: string;
}

interface EventPanelProps {
  event: DeformationEvent | null;
  onClose: () => void;
}

const EventPanel: React.FC<EventPanelProps> = ({ event, onClose }) => {
  if (!event) return null;

  return (
    <div className="event-panel" style={{
      width: '320px',
      backgroundColor: 'var(--panel-bg)',
      borderLeft: '1px solid var(--border-color)',
      padding: '1.5rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      overflowY: 'auto'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#ff6b6b' }}>Anomaly Details</h2>
        <button 
          onClick={onClose}
          style={{ background: 'transparent', border: 'none', color: '#aaa', cursor: 'pointer', fontSize: '1.2rem' }}
        >×</button>
      </div>
      
      <div className="event-metric">
        <span className="metric-label">Type</span>
        <span className="metric-value">{event.event_type.replace('_', ' ').toUpperCase()}</span>
      </div>
      
      <div className="event-metric">
        <span className="metric-label">Area (m²)</span>
        <span className="metric-value">{event.area_m2.toLocaleString()}</span>
      </div>

      <div className="event-metric">
        <span className="metric-label">Mean Velocity</span>
        <span className="metric-value" style={{ color: event.mean_velocity < 0 ? '#ff6b6b' : '#4da6ff' }}>
          {event.mean_velocity.toFixed(2)} mm/yr
        </span>
      </div>

      <div className="event-metric">
        <span className="metric-label">Max Velocity</span>
        <span className="metric-value" style={{ color: event.max_velocity < 0 ? '#ff6b6b' : '#4da6ff' }}>
          {event.max_velocity.toFixed(2)} mm/yr
        </span>
      </div>

      <div className="event-metric">
        <span className="metric-label">Mean Coherence</span>
        <span className="metric-value">{event.coherence.toFixed(2)} / 1.00</span>
      </div>

      <div className="event-metric">
        <span className="metric-label">Confidence Score</span>
        <span className="metric-value">{(event.confidence * 100).toFixed(0)}%</span>
      </div>

      <div style={{ marginTop: 'auto', padding: '1rem', backgroundColor: '#3d3d3d', borderRadius: '4px' }}>
        <p style={{ margin: 0, fontSize: '0.8rem', color: '#ffcc00' }}>
          <strong>⚠️ Warning:</strong> Values represent Line-Of-Sight (LOS) displacement. A deformation anomaly does not necessarily indicate a confirmed landslide.
        </p>
      </div>
    </div>
  );
};

export default EventPanel;
