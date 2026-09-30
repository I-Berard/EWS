import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRealTimeline } from '../api';

const VideoPage: React.FC = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Parse URL search params for aoiId and bbox
  const params = new URLSearchParams(window.location.search);
  const aoiId = params.get('aoiId');
  const bboxParam = params.get('bbox');
  const bbox: [number, number, number, number] | null = bboxParam 
    ? (bboxParam.split(',').map(Number) as [number, number, number, number])
    : null;

  const { data: timeline, isLoading, isError } = useQuery({
    queryKey: ['real-timeline', aoiId, bbox],
    queryFn: () => getRealTimeline(aoiId!, bbox || undefined),
    enabled: !!aoiId,
  });

  useEffect(() => {
    let interval: number;
    if (isPlaying && timeline && timeline.length > 0) {
      interval = window.setInterval(() => {
        setCurrentIndex((prev) => (prev + 1) % timeline.length);
      }, 500);
    }
    return () => window.clearInterval(interval);
  }, [isPlaying, timeline]);

  if (!aoiId) return <div style={{color: 'white', padding: 20}}>Missing aoiId in URL.</div>;
  if (isLoading) return <div style={{color: 'white', padding: 20}}>Loading high-quality video...</div>;
  if (isError || !timeline) return <div style={{color: 'white', padding: 20}}>Failed to load video.</div>;
  if (timeline.length === 0) return <div style={{color: 'white', padding: 20}}>No imagery found.</div>;

  const currentItem = timeline[currentIndex];

  let scaleX = 1;
  let scaleY = 1;
  let left = 0;
  let top = 0;

  if (bbox && currentItem.image_bbox) {
    const [T_minX, T_minY, T_maxX, T_maxY] = bbox;
    const [I_minX, I_minY, I_maxX, I_maxY] = currentItem.image_bbox;
    scaleX = (I_maxX - I_minX) / (T_maxX - T_minX);
    scaleY = (I_maxY - I_minY) / (T_maxY - T_minY);
    left = -((T_minX - I_minX) / (T_maxX - T_minX)) * 100;
    top = -((I_maxY - T_maxY) / (T_maxY - T_minY)) * 100;
  }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#000',
      display: 'flex',
      flexDirection: 'column',
      color: '#fff',
      fontFamily: 'sans-serif'
    }}>
      <div style={{
        padding: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#111',
        borderBottom: '1px solid #333'
      }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem' }}>High-Contrast SAR Timelapse</h2>
        <div>
          <button
            onClick={() => window.location.href = '/'}
            style={{ marginRight: 10, padding: '8px 16px', background: '#333', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}
          >
            Back to Dashboard
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{ padding: '8px 16px', background: isPlaying ? '#ff6b6b' : '#4dc3ff', color: '#111', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 'bold' }}
          >
            {isPlaying ? 'Pause' : 'Play'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ position: 'relative', width: '80vmin', height: '80vmin', backgroundColor: '#111', overflow: 'hidden', boxShadow: '0 0 20px rgba(0,0,0,0.5)', borderRadius: 8 }}>
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
        </div>
        <div style={{ position: 'absolute', bottom: 30, background: 'rgba(0,0,0,0.8)', padding: '10px 20px', borderRadius: 8, fontSize: '1.2rem' }}>
          {new Date(currentItem.date).toLocaleDateString()} ({currentIndex + 1} / {timeline.length})
        </div>
      </div>
      
      <div style={{ padding: '1rem 2rem', background: '#111' }}>
        <input 
          type="range" 
          min={0} 
          max={timeline.length - 1} 
          value={currentIndex}
          onChange={(e) => {
            setIsPlaying(false);
            setCurrentIndex(parseInt(e.target.value, 10));
          }}
          style={{ width: '100%', cursor: 'pointer' }}
        />
      </div>
    </div>
  );
};

export default VideoPage;
