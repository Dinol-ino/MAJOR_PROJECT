import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("DFrag Workspace UI Crash:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100vw', height: '100vh', background: '#0f1115', color: '#ffffff', fontFamily: 'sans-serif', padding: '24px' }}>
          <div style={{ maxWidth: '520px', background: '#15181d', border: '1px solid #ef4444', borderRadius: '12px', padding: '28px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
            <h2 style={{ color: '#ef4444', marginBottom: '12px', fontSize: '1.2rem' }}>DFrag Interface Error</h2>
            <p style={{ color: '#a3aab8', fontSize: '0.85rem', marginBottom: '16px' }}>The workspace encountered an unexpected render issue:</p>
            <pre style={{ background: '#0f1115', padding: '12px', borderRadius: '8px', color: '#f87171', fontSize: '0.78rem', overflowX: 'auto', marginBottom: '20px' }}>
              {this.state.error?.toString() || 'Unknown error'}
            </pre>
            <button
              onClick={() => { localStorage.clear(); window.location.reload(); }}
              style={{ background: '#2563eb', color: '#ffffff', border: 'none', borderRadius: '6px', padding: '10px 18px', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}
            >
              Reset Session & Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
