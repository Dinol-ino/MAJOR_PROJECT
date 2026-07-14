import React from 'react';

export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', fontStyle: 'italic', padding: 'var(--space-1) 0' }}>
        No citations cited for this response.
      </div>
    );
  }

  return (
    <div style={{ marginTop: 'var(--space-2)', borderTop: '1px solid var(--border-default)', paddingTop: 'var(--space-2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: 'var(--space-1)', color: 'var(--text-muted)', fontSize: '0.6875rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>
        Cited References ({sources.length})
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {sources.map((src, index) => (
          <div
            key={index}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-default)',
              borderLeft: '3px solid var(--color-accent)',
              borderRadius: 'var(--radius-sm)',
              padding: 'var(--space-1) 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.8125rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>{src.act}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Section {src.section}</span>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{src.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
