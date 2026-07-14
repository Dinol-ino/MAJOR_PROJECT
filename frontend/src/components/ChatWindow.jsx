import React, { useState, useRef, useEffect } from 'react';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import SourcesPanel from './SourcesPanel';

export default function ChatWindow({ messages, onSendMessage, sessionId, onUploadSuccess }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
    <div
      className="card main-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 120px)',
        minHeight: '500px',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
            <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
            <path d="M7 21h10"/>
            <path d="M12 3v18"/>
            <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
          </svg>
          <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Legal Assistant
          </span>
        </div>
        <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
          {sessionId}
        </span>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          padding: 'var(--space-3)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-2)',
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 'var(--space-2)',
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--border-default)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
              <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
              <path d="M7 21h10"/>
              <path d="M12 3v18"/>
              <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
            </svg>
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
                Ask a legal question or upload documents to get started.
              </p>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '4px' }}>
                Indian law statutes, acts, and case references are supported.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '75%',
              }}
            >
              {/* Role label */}
              <div
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-muted)',
                  marginBottom: '4px',
                  textAlign: msg.role === 'user' ? 'right' : 'left',
                }}
              >
                {msg.role === 'user' ? 'You' : 'DFrag'}
              </div>

              {/* Message bubble */}
              <div
                style={{
                  background: msg.role === 'user'
                    ? 'rgba(37, 99, 235, 0.08)'
                    : 'var(--bg-surface)',
                  border: `1px solid ${msg.role === 'user'
                    ? 'rgba(37, 99, 235, 0.2)'
                    : 'var(--border-default)'}`,
                  borderRadius: 'var(--radius-lg)',
                  padding: '12px var(--space-2)',
                }}
              >
                <p style={{ fontSize: '0.875rem', lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                  {msg.content}
                </p>

                {/* Blocked notice */}
                {msg.blocked_by && (
                  <div
                    style={{
                      marginTop: 'var(--space-1)',
                      padding: 'var(--space-1) 12px',
                      background: 'rgba(239, 68, 68, 0.06)',
                      border: '1px solid rgba(239, 68, 68, 0.15)',
                      borderLeft: '3px solid var(--color-danger)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8125rem',
                      color: 'var(--color-danger)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 'var(--space-1)',
                    }}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: '2px' }}>
                      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>
                    <span>Blocked by {msg.blocked_by.toUpperCase()} — {msg.block_reason}</span>
                  </div>
                )}

                {/* Citations */}
                {!msg.blocked_by && msg.sources && msg.sources.length > 0 && (
                  <SourcesPanel sources={msg.sources} />
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderTop: '1px solid var(--border-default)',
          background: 'var(--bg-secondary)',
          flexShrink: 0,
        }}
      >
        <form onSubmit={handleSend} style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center' }}>
          <UploadButton sessionId={sessionId} onUploadSuccess={onUploadSuccess} />

          <input
            type="text"
            className="input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your legal query..."
            style={{ flex: 1 }}
          />

          <MicButton onSpeechEnd={handleSpeechEnd} />

          <button type="submit" className="btn-icon" style={{ background: 'var(--color-accent)', borderColor: 'var(--color-accent)', color: '#fff' }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m22 2-7 20-4-9-9-4Z"/>
              <path d="M22 2 11 13"/>
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
