import React from 'react';
import { AuditIcon } from './Icons';

export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) {
    return (
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontStyle: 'italic', padding: '6px 0' }}>
        No citations cited for this response.
      </div>
    );
  }

  return (
    <div className="sources-panel" style={{ marginTop: '12px', borderTop: '1px solid var(--panel-border)', paddingTop: '12px' }}>
      <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
        <AuditIcon size={14} color="var(--accent-color)" /> Cited References ({sources.length})
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
              padding: '10px 12px' 
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: '600', color: 'var(--accent-color)' }}>{src.act || src.title || 'Legal Document'}</span>
              <span style={{ color: 'var(--text-secondary)' }}>{src.section ? `Section ${src.section}` : ''}</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: '1.4' }}>{src.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
