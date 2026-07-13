import React from 'react';
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
        <span className="shield-icon">🛡️</span>
        <span className="slider-indicator"></span>
      </button>
    </div>
  );
}
