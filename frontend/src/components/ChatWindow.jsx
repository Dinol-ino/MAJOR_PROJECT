import React, { useState } from 'react';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import SourcesPanel from './SourcesPanel';

export default function ChatWindow({ messages, onSendMessage, sessionId, onUploadSuccess }) {
  const [input, setInput] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSendMessage(input);
    setInput('');
  };

  const handleSpeechEnd = (transcript) => {
    setInput((prev) => (prev ? prev + ' ' + transcript : transcript));
  };

  return (
    <div className="chat-window-container glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '600px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--panel-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.25rem' }}>🧑‍⚖️ Legal Assistant Workspace</h2>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Session: {sessionId}</span>
      </div>

      {/* Messages list */}
      <div style={{ flex: 1, padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>
            <span style={{ fontSize: '2.5rem', marginBottom: '12px' }}>⚖️</span>
            <p>Welcome to DFrag. Ask a legal question or upload acts / company documents to get started.</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div 
              key={idx} 
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
                background: msg.role === 'user' ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(99, 102, 241, 0.3)' : 'var(--panel-border)'}`,
                borderRadius: '12px',
                padding: '12px 16px',
              }}
            >
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                {msg.role === 'user' ? 'You' : 'DFrag AI'}
              </div>
              <p style={{ fontSize: '0.95rem', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{msg.content}</p>
              
              {/* If answer was blocked */}
              {msg.blocked_by && (
                <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger-color)', borderRadius: '6px', color: 'var(--danger-color)', fontSize: '0.85rem' }}>
                  ⚠️ Blocked by {msg.blocked_by.toUpperCase()} - Reason: {msg.block_reason}
                </div>
              )}

              {/* Citations panel if output exists and is not blocked */}
              {!msg.blocked_by && msg.sources && msg.sources.length > 0 && (
                <SourcesPanel sources={msg.sources} />
              )}
            </div>
          ))
        )}
      </div>

      {/* Footer input form */}
      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--panel-border)', background: 'rgba(15, 23, 42, 0.4)' }}>
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <UploadButton sessionId={sessionId} onUploadSuccess={onUploadSuccess} />
          
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your legal query (e.g. 'What is Section 66 IT Act penalty?')..."
            style={{
              flex: 1,
              background: '#0f172a',
              border: '1px solid var(--panel-border)',
              borderRadius: '8px',
              padding: '12px 16px',
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
          
          <MicButton onSpeechEnd={handleSpeechEnd} />
          
          <button
            type="submit"
            style={{
              background: 'var(--accent-color)',
              border: 'none',
              borderRadius: '8px',
              padding: '12px 20px',
              color: 'white',
              fontWeight: '600',
            }}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
