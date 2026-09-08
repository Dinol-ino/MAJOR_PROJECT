import React, { useState } from 'react';

/**
 * ContextMeter — Claude-style context window budget indicator.
 * Displays total token usage and detailed breakdown (History, Documents, System).
 */
export default function ContextMeter({
  usedTokens = 3200,
  maxTokens = 32768,
  breakdown = { history: 1800, documents: 900, system: 500 }
}) {
  const [showPopover, setShowPopover] = useState(false);

  const percent = Math.min(100, Math.round((usedTokens / maxTokens) * 100));
  const isHigh = percent >= 80;

  const formatTokens = (n) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return `${n}`;
  };

  const meterColor = isHigh ? 'var(--accent-amber)' : 'var(--accent)';

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <div
        onClick={() => setShowPopover(!showPopover)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '2px 8px',
          borderRadius: 'var(--radius-sm)',
          background: 'transparent',
          cursor: 'pointer',
          fontSize: '0.72rem',
          color: isHigh ? 'var(--accent-amber)' : 'var(--text-secondary)',
          userSelect: 'none'
        }}
        title="Click to view context budget breakdown"
      >
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {formatTokens(usedTokens)} / {formatTokens(maxTokens)} tokens ({percent}%)
        </span>

        {/* Mini progress pill */}
        <div
          style={{
            width: '42px',
            height: '4px',
            background: 'var(--border-subtle)',
            borderRadius: '2px',
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              width: `${percent}%`,
              height: '100%',
              background: meterColor,
              transition: 'width 0.3s ease'
            }}
          />
        </div>
      </div>

      {/* Breakdown Popover */}
      {showPopover && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: '6px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'var(--shadow-md)',
            padding: '10px 14px',
            fontSize: '0.73rem',
            color: 'var(--text-primary)',
            zIndex: 1200,
            width: '240px'
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '6px', color: 'var(--text-primary)' }}>
            Context Window Allocation
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'var(--font-mono)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Conversation History:</span>
              <span>{formatTokens(breakdown.history || 0)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Vault Documents:</span>
              <span>{formatTokens(breakdown.documents || 0)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>System Directives:</span>
              <span>{formatTokens(breakdown.system || 0)}</span>
            </div>
          </div>
          <div style={{ marginTop: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '4px', fontSize: '0.68rem', color: 'var(--text-dim)' }}>
            {isHigh ? '⚠️ Context > 80% — Older turns are summarized.' : 'Ample capacity remaining for statutory synthesis.'}
          </div>
        </div>
      )}
    </div>
  );
}
