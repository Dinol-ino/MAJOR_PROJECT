import React from 'react';
import { ShieldIcon } from './Icons';
import './ShieldToggle.css';

export default function ShieldToggle({ shieldOn, onToggle }) {
  return (
    <div className={`shield-container glass-panel ${shieldOn ? 'shield-active' : 'shield-inactive'}`}>
      <div className="shield-info">
        <span className="shield-label">Security Shield</span>
        <span className={`shield-status ${shieldOn ? 'status-on' : 'status-off'}`}>
          {shieldOn ? 'ON / PROTECTED' : 'OFF / VULNERABLE'}
        </span>
      </div>
      <button 
        type="button" 
        className={`shield-button ${shieldOn ? 'btn-active' : 'btn-inactive'}`}
        onClick={() => onToggle(!shieldOn)}
      >
        <ShieldIcon size={18} color={shieldOn ? 'var(--safe-color)' : 'var(--danger-color)'} />
        <span className="slider-indicator"></span>
      </button>
    </div>
  );
}
