import React from 'react';
import { BookIcon, CheckShieldIcon, ScaleIcon } from './Icons';
import ProvenancePanel from './ProvenancePanel';

export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) {
    return null;
  }

  const hasStatutes = sources.some(s => s.doc_type === 'statutory_law' || !s.doc_type || s.act?.includes('Act') || s.act?.includes('Code'));
  const hasUserDocs = sources.some(s => s.doc_type === 'user_document' || s.act?.endsWith('.pdf'));
  
  let panelTitle = 'Grounded Sources & Citations';
  if (hasStatutes && !hasUserDocs) {
    panelTitle = 'Grounded Statutory Provisions & Citations';
  } else if (!hasStatutes && hasUserDocs) {
    panelTitle = 'Referenced User Document Sources';
  }

  return (
    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
      <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', fontWeight: 700 }}>
        <BookIcon size={14} color="var(--accent-cyan)" />
        <span>{panelTitle} ({sources.length})</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {sources.map((src, index) => {
          const actName = src.act || src.title || 'Source Reference';
          const sectionNum = src.section ? `Section ${src.section}` : null;
          const trustPct = src.trust_score ? Math.round(src.trust_score * 100) : null;
          const simPct = src.similarity_score ? Math.round(src.similarity_score * 100) : null;
          const isUserDoc = src.doc_type === 'user_document' || actName.endsWith('.pdf');

          return (
            <div
              key={index}
              style={{
                background: 'var(--bg-app)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              {/* Card Header with Badges */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 700, color: isUserDoc ? 'var(--accent-blue)' : 'var(--accent-cyan)' }}>
                    [{index + 1}] {actName}
                  </span>
                  <span style={{ fontSize: '0.65rem', background: isUserDoc ? 'rgba(56, 189, 248, 0.15)' : 'rgba(0, 210, 180, 0.15)', color: isUserDoc ? 'var(--accent-blue)' : 'var(--accent-cyan)', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
                    {isUserDoc ? 'USER DOC' : 'STATUTE'}
                  </span>
                  {sectionNum && (
                    <span style={{ color: 'var(--accent-blue)', background: 'rgba(56, 189, 248, 0.1)', padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                      {sectionNum}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {trustPct !== null && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--defense-pass)', background: 'rgba(16, 185, 129, 0.1)', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
                      Trust: {trustPct}%
                    </span>
                  )}
                  {simPct !== null && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', background: 'rgba(255, 255, 255, 0.05)', padding: '1px 6px', borderRadius: '4px' }}>
                      Sim: {simPct}%
                    </span>
                  )}
                </div>
              </div>

              {/* Source Text Snippet */}
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.45', margin: 0 }}>
                "{src.text}"
              </p>

              {/* Progressive Disclosure Provenance Panel */}
              <ProvenancePanel source={src} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

