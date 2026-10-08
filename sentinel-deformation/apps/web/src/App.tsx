import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import VideoPage from './pages/VideoPage';
import RealDashboard from './pages/RealDashboard';
import './index.css';

const queryClient = new QueryClient();

type Mode = 'demo' | 'real';

function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [mode, setMode] = useState<Mode>('demo');

  useEffect(() => {
    const onLocationChange = () => {
      setCurrentPath(window.location.pathname);
    };

    window.addEventListener('popstate', onLocationChange);
    const originalPushState = history.pushState;
    history.pushState = function (...args) {
      originalPushState.apply(this, args);
      onLocationChange();
    };

    return () => {
      window.removeEventListener('popstate', onLocationChange);
      history.pushState = originalPushState;
    };
  }, []);

  if (currentPath === '/video') {
    return (
      <QueryClientProvider client={queryClient}>
        <VideoPage />
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="app-container">
        <header className="app-header">
          <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.2rem' }}>🛰</span>
            <h1 style={{ margin: 0, color: '#4da6ff', fontSize: '1.4rem', fontWeight: 700, letterSpacing: '0.5px' }}>
              Sentinel Deformation Monitor
            </h1>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 0, border: '1px solid #444', borderRadius: 8, overflow: 'hidden' }}>
            {(['demo', 'real'] as Mode[]).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: '6px 18px',
                  border: 'none',
                  background: mode === m
                    ? (m === 'real' ? 'linear-gradient(135deg, #4da6ff, #0066cc)' : '#ff9800')
                    : '#1e1e1e',
                  color: mode === m ? '#fff' : '#888',
                  fontWeight: mode === m ? 700 : 400,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  letterSpacing: '0.04em',
                  transition: 'all 0.2s',
                }}
              >
                {m === 'demo' ? '🧪 DEMO' : '🛰 REAL DATA'}
              </button>
            ))}
          </div>
        </header>
        <main className="app-main">
          {mode === 'demo' ? <Dashboard /> : <RealDashboard />}
        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
