import React from 'react';

export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) {
    return (
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontStyle: 'italic', padding: '8px' }}>
        No citations cited for this response.
      </div>
    );
  }

  return (
    <div className="sources-panel" style={{ marginTop: '12px', borderTop: '1px solid var(--panel-border)', paddingTop: '12px' }}>
      <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
        📚 Cited References ({sources.length})
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {sources.map((src, index) => (
          <div 
            key={index} 
            className="source-card" 
            style={{ 
              background: 'rgba(255, 255, 255, 0.03)', 
              border: '1px solid var(--panel-border)', 
              borderRadius: '8px', 
              padding: '10px' 
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.85rem' }}>
              <span style={{ fontWeight: '600', color: 'var(--accent-color)' }}>{src.act}</span>
              <span style={{ color: 'var(--text-secondary)' }}>Section {src.section}</span>
            </div>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: '1.4' }}>{src.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
