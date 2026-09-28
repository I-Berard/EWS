import React, { useState, useEffect } from 'react';
import MapComponent from '../components/Map';
import EventPanel from '../components/EventPanel';
import TimeSeriesChart from '../components/TimeSeriesChart';
import axios from 'axios';

const Dashboard: React.FC = () => {
  const [aois, setAois] = useState<any[]>([]);
  const [selectedAoi, setSelectedAoi] = useState<any | null>(null);
  
  // Dashboard UI state
  const [anomalies, setAnomalies] = useState<any>(null);
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null);
  const [timeSeriesData, setTimeSeriesData] = useState<any[]>([]);
  const [clickedLocation, setClickedLocation] = useState<{lat: number, lng: number} | null>(null);

  useEffect(() => {
    // Fetch mock AOI for demo
    axios.get('http://localhost:8000/api/aois/')
      .then(res => {
        setAois(res.data);
        if (res.data.length > 0) setSelectedAoi(res.data[0]);
      })
      .catch(err => {
        console.error('Error fetching AOIs:', err);
        const demoAoi = {
          id: 'demo-rwanda-1',
          name: 'Kigali Deformation Demo',
          geometry: {
            type: 'Polygon',
            coordinates: [[[30.0, -1.9], [30.15, -1.9], [30.15, -2.0], [30.0, -2.0], [30.0, -1.9]]]
          }
        };
        setAois([demoAoi]);
        setSelectedAoi(demoAoi);
      });
      
    // Generate synthetic anomalies for the Kigali area
    setAnomalies({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            id: 'evt-001',
            event_type: 'landslide_candidate',
            area_m2: 45000,
            mean_velocity: -12.4,
            max_velocity: -22.1,
            coherence: 0.85,
            confidence: 0.9,
            detected_at: '2026-09-28T00:00:00Z'
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[30.08, -1.96], [30.09, -1.96], [30.09, -1.95], [30.08, -1.95], [30.08, -1.96]]]
          }
        },
        {
          type: 'Feature',
          properties: {
            id: 'evt-002',
            event_type: 'subsidence',
            area_m2: 120000,
            mean_velocity: -6.2,
            max_velocity: -8.4,
            coherence: 0.95,
            confidence: 0.98,
            detected_at: '2026-09-28T00:00:00Z'
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[30.05, -1.93], [30.07, -1.93], [30.07, -1.92], [30.05, -1.92], [30.05, -1.93]]]
          }
        }
      ]
    });
  }, []);

  const handleMapClick = (lngLat: { lat: number; lng: number }) => {
    setClickedLocation(lngLat);
    // Generate synthetic time series data for the clicked point
    const data = [];
    let currentDisp = 0;
    for (let i = 0; i < 12; i++) {
      currentDisp += (Math.random() * -4); // Synthetic downward trend
      data.push({
        date: `2026-${String(i+1).padStart(2, '0')}`,
        displacement: Number(currentDisp.toFixed(1))
      });
    }
    setTimeSeriesData(data);
    setSelectedEvent(null);
  };

  const handleAnomalyClick = (properties: any) => {
    setSelectedEvent(properties);
    setTimeSeriesData([]); // Hide time series if showing an anomaly event summary
    setClickedLocation(null);
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div>
          <h2>Areas of Interest</h2>
          <span className="demo-badge" style={{ marginLeft: 0, marginBottom: '1rem', display: 'inline-block' }}>DEMO MODE</span>
          <div style={{ marginTop: '0.5rem' }}>
            {aois.map(aoi => (
              <div 
                key={aoi.id} 
                style={{ 
                  padding: '10px', 
                  backgroundColor: selectedAoi?.id === aoi.id ? '#4da6ff33' : '#3d3d3d',
                  border: selectedAoi?.id === aoi.id ? '1px solid #4da6ff' : '1px solid transparent',
                  cursor: 'pointer',
                  borderRadius: '4px'
                }}
                onClick={() => setSelectedAoi(aoi)}
              >
                {aoi.name}
              </div>
            ))}
          </div>
        </div>
        
        {timeSeriesData.length > 0 && (
          <TimeSeriesChart data={timeSeriesData} location={clickedLocation!} />
        )}
        
        <div style={{ marginTop: 'auto' }}>
          <p style={{ fontSize: '0.8rem', color: '#888' }}>
            <strong>Note:</strong> InSAR measurements represent displacement along the radar Line of Sight (LOS), not true 3D movement.
          </p>
        </div>
      </div>
      
      <div className="map-container">
        <MapComponent 
          aoi={selectedAoi} 
          anomalies={anomalies}
          onMapClick={handleMapClick}
          onAnomalyClick={handleAnomalyClick}
        />
      </div>

      {selectedEvent && (
        <EventPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}
    </div>
  );
};

export default Dashboard;
