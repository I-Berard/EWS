import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

interface TimeSeriesData {
  date: string;
  displacement: number;
}

interface TimeSeriesChartProps {
  data: TimeSeriesData[];
  location?: { lat: number; lng: number };
}

const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ data, location }) => {
  if (!data || data.length === 0) return null;

  return (
    <div className="timeseries-chart-container" style={{ padding: '1rem', backgroundColor: 'var(--panel-bg)', borderRadius: '8px', border: '1px solid var(--border-color)', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', color: 'var(--accent-color)' }}>
        LOS Displacement Time Series
      </h3>
      {location && (
        <p style={{ fontSize: '0.8rem', color: '#888', marginBottom: '1rem' }}>
          Lat: {location.lat.toFixed(4)}, Lng: {location.lng.toFixed(4)}
        </p>
      )}
      <div style={{ height: '200px', width: '100%' }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#444" />
            <XAxis dataKey="date" stroke="#aaa" tick={{ fontSize: 12 }} />
            <YAxis 
              stroke="#aaa" 
              tick={{ fontSize: 12 }}
              label={{ value: 'Displacement (mm)', angle: -90, position: 'insideLeft', fill: '#aaa', fontSize: 12 }}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1e1e1e', border: '1px solid #444', borderRadius: '4px' }}
              itemStyle={{ color: '#4da6ff' }}
            />
            <Line 
              type="monotone" 
              dataKey="displacement" 
              stroke="#4da6ff" 
              strokeWidth={2}
              dot={{ r: 4, fill: '#4da6ff' }}
              activeDot={{ r: 6 }} 
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TimeSeriesChart;
