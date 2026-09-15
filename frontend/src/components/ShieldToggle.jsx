import React from 'react';
import { CheckShieldIcon, ShieldAlertIcon } from './Icons';

export default function ShieldToggle({ shieldOn, onToggle }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!shieldOn)}
      style={{
        background: shieldOn ? 'rgba(255, 0, 127, 0.12)' : 'var(--bg-raised)',
        border: `1px solid ${shieldOn ? 'var(--accent-pink)' : 'var(--border-medium)'}`,
        borderRadius: '16px',
        padding: '5px 12px',
        color: shieldOn ? 'var(--accent-pink)' : 'var(--text-muted)',
        fontSize: '0.78rem',
        fontWeight: 700,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        boxShadow: 'var(--shadow-sm)',
      }}
      title={
        shieldOn
          ? '3-Layer Defensive Shield ACTIVE (L1: Input Guard, L2: Presidio PII, L3: Output Grounding Guard)'
          : '3-Layer Defensive Shield DISABLED (Unprotected Baseline Mode)'
      }
    >
      {shieldOn ? (
        <CheckShieldIcon size={14} color="var(--accent-pink)" />
      ) : (
        <ShieldAlertIcon size={14} color="var(--text-muted)" />
      )}
      <span>Shield: {shieldOn ? 'ON' : 'OFF'}</span>
    </button>
  );
}
