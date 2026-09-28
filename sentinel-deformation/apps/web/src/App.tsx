import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './pages/Dashboard';
import './index.css';

const queryClient = new QueryClient();

function App() {
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
