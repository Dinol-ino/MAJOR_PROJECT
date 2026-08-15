import React from 'react';
import { ShieldIcon } from './Icons';

export default function ShieldToggle({ shieldOn, onToggle }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(!shieldOn)}
      style={{
        background: shieldOn ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
        border: `1px solid ${shieldOn ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
        borderRadius: '16px',
        padding: '4px 12px',
        color: shieldOn ? '#22c55e' : '#ef4444',
        fontSize: '0.78rem',
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
      title={shieldOn ? 'Security Shield Active (Protected)' : 'Security Shield Disabled'}
    >
      <ShieldIcon size={14} color={shieldOn ? '#22c55e' : '#ef4444'} />
      <span>Shield: {shieldOn ? 'ON' : 'OFF'}</span>
    </button>
  );
}
