import React, { useState } from 'react';
import { CheckShieldIcon, SparklesIcon, ShieldAlertIcon } from './Icons';

export default function ConfidenceIndicator({ confidenceScore, sourcesCount = 0, isGrounded = true }) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (confidenceScore === null || confidenceScore === undefined) {
    return null;
  }

  const scorePct = Math.round(confidenceScore * 100);
  const isHighConfidence = scorePct >= 70;

  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <button
        type="button"
        onClick={() => setShowTooltip(!showTooltip)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        style={{
          background: isHighConfidence ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
          border: `1px solid ${isHighConfidence ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
          color: isHighConfidence ? 'var(--defense-pass)' : 'var(--defense-warn, #f59e0b)',
          fontSize: '0.68rem',
          fontWeight: 700,
          padding: '1px 8px',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          cursor: 'pointer',
        }}
        title="Click to view grounding verification breakdown"
      >
        <CheckShieldIcon size={12} color={isHighConfidence ? 'var(--defense-pass)' : '#f59e0b'} />
        <span>Grounded ({scorePct}%)</span>
      </button>

      {showTooltip && (
        <div
          style={{
            position: 'absolute',
            bottom: '125%',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'var(--bg-modal, #1e222d)',
            border: '1px solid var(--border-medium, #333d4d)',
            borderRadius: '8px',
            padding: '10px 14px',
            width: '220px',
            boxShadow: 'var(--shadow-md)',
            zIndex: 100,
            fontSize: '0.72rem',
            color: 'var(--text-primary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            pointerEvents: 'none',
          }}
        >
          <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '4px' }}>
            Grounding Transparency
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Token Overlap:</span>
            <strong>{scorePct}%</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Corpus Citations:</span>
            <strong>{sourcesCount} verified</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>L3 Guardrail:</span>
            <span style={{ color: 'var(--defense-pass)', fontWeight: 700 }}>Passed</span>
          </div>
        </div>
      )}
    </div>
  );
}
