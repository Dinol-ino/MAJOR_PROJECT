import React from 'react';

/**
 * StagedLoadingIndicator — Replaces static spinner with an SSE-driven staged pipeline indicator
 * and a 3-line shimmer skeleton at message arrival position.
 */
export default function StagedLoadingIndicator({
  stage = 'retrieving', // 'retrieving' | 'mcp' | 'analyzing' | 'streaming'
  stageText
}) {
  const getStageLabel = () => {
    if (stageText) return stageText;
    switch (stage) {
      case 'retrieving':
        return 'Retrieving grounded evidence from vault…';
      case 'mcp':
        return 'Querying canonical MCP statutes & case registries…';
      case 'analyzing':
        return 'Synthesizing statutory analysis & cross-walk citations…';
      case 'streaming':
        return 'Formulating grounded answer…';
      default:
        return 'Processing legal query…';
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '16px 20px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        maxWidth: 'var(--max-content-width)',
        width: '100%',
        margin: '0 auto',
        boxSizing: 'border-box'
      }}
    >
      {/* Staged Status Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: 'var(--accent)',
            animation: 'pulse-subtle 1.4s infinite ease-in-out'
          }}
        />
        <span
          style={{
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)'
          }}
        >
          {getStageLabel()}
        </span>
      </div>

      {/* 3-Line Shimmer Skeleton */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
        <div className="shimmer-line" style={{ width: '92%', height: '14px' }} />
        <div className="shimmer-line" style={{ width: '84%', height: '14px' }} />
        <div className="shimmer-line" style={{ width: '60%', height: '14px' }} />
      </div>
    </div>
  );
}
