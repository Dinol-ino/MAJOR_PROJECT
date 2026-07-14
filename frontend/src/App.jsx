import React, { useState, useEffect } from 'react';
import ShieldToggle from './components/ShieldToggle';
import HardwareForm from './components/HardwareForm';
import ChatWindow from './components/ChatWindow';
import { apiClient } from './api/client';

export default function App() {
  const [sessionId, setSessionId] = useState('');
  const [shieldOn, setShieldOn] = useState(true);
  const [selectedModel, setSelectedModel] = useState('qwen2.5:3b');
  const [messages, setMessages] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  const startNewSession = () => {
    const randomId = Math.random().toString(36).substring(2, 8).toUpperCase();
    setSessionId(randomId);
    setMessages([]);
    setAuditLogs([]);
  };

  // Generate a random session ID on load
  useEffect(() => {
    startNewSession();
  }, []);

  const handleSendMessage = async (text) => {
    // 1. Add user message locally
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);

    try {
      // 2. Fetch response from backend api client
      const response = await apiClient.chat(text, sessionId, shieldOn);
      
      // 3. Handle response
      const botMsg = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        blocked_by: response.blocked_by,
        block_reason: response.block_reason
      };
      setMessages((prev) => [...prev, botMsg]);

      // 4. Update audit logs
      refreshAuditLogs();
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Could not connect to the backend server. Make sure it is running.' }
      ]);
    }
  };

  const refreshAuditLogs = async () => {
    try {
      const logData = await apiClient.getAuditLogs(sessionId);
      setAuditLogs(logData.rows);
    } catch (err) {
      console.warn('Could not load audit logs:', err);
    }
  };

  const handleUploadSuccess = () => {
    refreshAuditLogs();
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: 'var(--space-3)', minHeight: '100vh' }}>
      {/* Header */}
      <header
        className="app-header"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--space-3)',
          paddingBottom: 'var(--space-2)',
          borderBottom: '1px solid var(--border-default)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>
            </svg>
            <div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                DFrag
              </h1>
              <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', letterSpacing: '0.02em', marginTop: '1px' }}>
                Security-Hardened Legal AI Workspace
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
            Session {sessionId}
          </span>
        </div>
      </header>

      {/* Dashboard Grid */}
      <div className="dashboard-grid" style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 'var(--space-3)', alignItems: 'start' }}>
        {/* Sidebar */}
        <div className="sidebar" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {/* New Session */}
          <button
            type="button"
            onClick={startNewSession}
            className="btn-primary"
            style={{ width: '100%', height: '44px', fontSize: '0.875rem' }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14"/>
              <path d="M12 5v14"/>
            </svg>
            New Session
          </button>

          {/* Security Shield */}
          <ShieldToggle shieldOn={shieldOn} onToggle={setShieldOn} />

          {/* Hardware Recommendation */}
          <HardwareForm onModelRecommended={setSelectedModel} />

          {/* Audit Trail */}
          <div className="card" style={{ padding: 'var(--space-2)', flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
              <div className="section-header" style={{ marginBottom: 0 }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 8v4l3 3"/>
                  <circle cx="12" cy="12" r="10"/>
                </svg>
                <span className="section-title">Audit Trail</span>
              </div>
              <button
                type="button"
                onClick={refreshAuditLogs}
                className="btn-ghost"
                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/>
                  <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>
                  <path d="M21 21v-5h-5"/>
                </svg>
                Refresh
              </button>
            </div>

            {auditLogs.length === 0 ? (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', padding: 'var(--space-2) 0', textAlign: 'center' }}>
                No audit events logged yet.
              </p>
            ) : (
              <div className="table-container" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Action</th>
                      <th>Layer</th>
                      <th>Hash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log, idx) => (
                      <tr key={idx}>
                        <td className="mono">{log.ts.split('T')[1].substring(0, 8)}</td>
                        <td>
                          <span className={`badge ${log.layer ? 'badge--danger' : 'badge--success'}`}>
                            {log.action.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ color: log.layer ? 'var(--color-danger)' : 'var(--text-muted)' }}>
                          {log.layer || '—'}
                        </td>
                        <td className="mono" title={log.hash}>{log.hash.substring(0, 12)}...</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Chat Workspace */}
        <ChatWindow
          messages={messages}
          onSendMessage={handleSendMessage}
          sessionId={sessionId}
          onUploadSuccess={handleUploadSuccess}
        />
      </div>
    </div>
  );
}
