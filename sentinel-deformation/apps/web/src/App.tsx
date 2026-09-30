import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import VideoPage from './pages/VideoPage';
import './index.css';

const queryClient = new QueryClient();

function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const onLocationChange = () => {
      setCurrentPath(window.location.pathname);
    };

    window.addEventListener('popstate', onLocationChange);
    // Support simple pushState overriding for SPA navigation
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
          <h1>Sentinel Deformation Monitor</h1>
        </header>
        <main className="app-main">
          <Dashboard />
        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
