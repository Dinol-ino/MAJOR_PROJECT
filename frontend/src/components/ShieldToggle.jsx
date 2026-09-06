import React from 'react';
import { CheckShieldIcon, ShieldAlertIcon } from './Icons';

export default function ShieldToggle({ shieldOn, onToggle }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!shieldOn)}
      style={{
        background: shieldOn ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
        border: `1px solid ${shieldOn ? 'var(--defense-pass)' : 'var(--defense-block)'}`,
        borderRadius: '16px',
        padding: '5px 12px',
        color: shieldOn ? 'var(--defense-pass)' : 'var(--defense-block)',
        fontSize: '0.78rem',
        fontWeight: 700,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        boxShadow: shieldOn ? '0 0 10px rgba(16, 185, 129, 0.2)' : 'none',
      }}
      title={
        shieldOn
          ? '3-Layer Defensive Shield ACTIVE (L1: Input Guard, L2: Presidio PII, L3: Output Grounding Guard)'
          : '3-Layer Defensive Shield DISABLED (Unprotected Baseline Mode)'
      }
    >
      {shieldOn ? (
        <CheckShieldIcon size={14} color="var(--defense-pass)" />
      ) : (
        <ShieldAlertIcon size={14} color="var(--defense-block)" />
      )}
      <span>Shield: {shieldOn ? 'ON' : 'OFF'}</span>
    </button>
  );
}
