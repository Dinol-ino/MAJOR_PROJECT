import React, { useState, useEffect } from 'react';
import ShieldToggle from './components/ShieldToggle';
import HardwareForm from './components/HardwareForm';
import ChatWindow from './components/ChatWindow';
import { apiClient } from './api/client';
import { ShieldIcon, PlusIcon, AuditIcon, RefreshIcon } from './components/Icons';

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
      // 2. Fetch response from backend api client passing selectedModel
      const response = await apiClient.chat(text, sessionId, shieldOn, selectedModel);
      
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
      setAuditLogs(logData.rows || []);
    } catch (err) {
      console.warn('Could not load audit logs:', err);
    }
  };

  const handleUploadSuccess = () => {
    refreshAuditLogs();
  };

  return (
    <div style={{ maxWidth: '1240px', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <header style={{ marginBottom: '24px', textAlign: 'center' }}>
        <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '2.4rem', fontWeight: 800, color: 'white', display: 'inline-flex', alignItems: 'center', gap: '10px' }} className="glow-text">
          <ShieldIcon size={32} color="var(--accent-color)" /> DFrag Workspace
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '6px', fontSize: '0.9rem' }}>
          Indian Law Legal AI Copilot — Hardened Offline Retrieval-Augmented Generation
        </p>
      </header>

      {/* Main dashboard content */}
      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px' }}>
        {/* Sidebar Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <button
            type="button"
            onClick={startNewSession}
            style={{
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              padding: '12px 16px',
              fontWeight: '600',
              fontFamily: 'var(--font-title)',
              fontSize: '0.95rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: 'var(--shadow-glow)',
              cursor: 'pointer',
            }}
          >
            <PlusIcon size={18} />
            <span>Start New Session</span>
          </button>
          
          <ShieldToggle shieldOn={shieldOn} onToggle={setShieldOn} />
          
          <HardwareForm 
            onModelRecommended={setSelectedModel} 
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
          />

          {/* Audit Logs panel */}
          <div className="glass-panel" style={{ padding: '20px', flex: 1, minHeight: '200px', borderRadius: '12px' }}>
            <h3 style={{ fontFamily: 'var(--font-title)', fontSize: '0.95rem', marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AuditIcon size={16} color="var(--accent-color)" />
                Audit Trail
              </span>
              <button 
                type="button" 
                onClick={refreshAuditLogs} 
                style={{ background: 'none', border: 'none', color: 'var(--accent-color)', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <RefreshIcon size={12} /> Refresh
              </button>
            </h3>
            {auditLogs.length === 0 ? (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>No audit events logged yet.</p>
            ) : (
              <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {auditLogs.map((log, idx) => (
                  <div 
                    key={idx} 
                    style={{ 
                      fontSize: '0.78rem', 
                      background: 'rgba(0,0,0,0.2)', 
                      padding: '8px', 
                      borderRadius: '6px',
                      borderLeft: `3px solid ${log.layer ? 'var(--danger-color)' : 'var(--safe-color)'}`
                    }}
                  >
                    <div style={{ color: 'var(--text-secondary)' }}>{log.ts.split('T')[1].substring(0, 8)} - {log.action.toUpperCase()}</div>
                    {log.layer && <div style={{ color: 'var(--danger-color)' }}>Blocked by: {log.layer}</div>}
                    <div style={{ fontFamily: 'monospace', fontSize: '0.7rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      Hash: {log.hash ? log.hash.substring(0, 16) : 'N/A'}...
                    </div>
                  </div>
                ))}
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
