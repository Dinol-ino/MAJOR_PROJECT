import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { CheckShieldIcon, GlobeIcon } from './Icons';

export default function ModeIndicator() {
  const [runtimeMode, setRuntimeMode] = useState('OFFLINE');

  useEffect(() => {
    let isMounted = true;

    // Check runtime status on mount
    async function checkStatus() {
      try {
        const res = await fetch('/api/runtime/status');
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            if (data.runtime_engine === 'cloud') {
              const prov = data.cloud_fallback?.active_provider === 'zai' ? 'Z.ai' : 'Grok';
              setRuntimeMode(`CLOUD (${prov})`);
            } else {
              setRuntimeMode('OFFLINE');
            }
          }
        }
      } catch (err) {
        if (isMounted) setRuntimeMode('OFFLINE');
      }
    }

    checkStatus();

    // Listen to live runtime_switched events from SSE stream or fallback events
    const handleRuntimeSwitched = (e) => {
      const detail = e.detail || {};
      if (detail.to === 'cloud') {
        const prov = (detail.provider || '').toLowerCase() === 'zai' ? 'Z.ai' : 'Grok';
        setRuntimeMode(`CLOUD (${prov})`);
      } else {
        setRuntimeMode('OFFLINE');
      }
    };

    window.addEventListener('runtime_switched', handleRuntimeSwitched);

    return () => {
      isMounted = false;
      window.removeEventListener('runtime_switched', handleRuntimeSwitched);
    };
  }, []);

  const isCloud = runtimeMode.startsWith('CLOUD');
  const isOffline = !isCloud;

  const bg = isCloud
    ? 'rgba(245, 158, 11, 0.12)'
    : 'rgba(16, 185, 129, 0.1)';
  const border = isCloud
    ? '1px solid rgba(245, 158, 11, 0.35)'
    : '1px solid rgba(16, 185, 129, 0.3)';
  const color = isCloud ? '#f59e0b' : 'var(--defense-pass)';
  const glow = isCloud
    ? '0 0 10px rgba(245, 158, 11, 0.2)'
    : '0 0 10px rgba(16, 185, 129, 0.15)';

  return (
    <div
      style={{
        background: bg,
        border: border,
        borderRadius: '16px',
        padding: '5px 12px',
        color: color,
        fontSize: '0.78rem',
        fontWeight: 700,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'default',
        userSelect: 'none',
        boxShadow: glow,
        transition: 'all 0.3s ease',
      }}
      title={
        isCloud
          ? `Runtime Mode: ${runtimeMode} — Seamless fallback active (Local hardware limits bypassed)`
          : 'Runtime Mode: OFFLINE (Strict local execution via Ollama — zero outbound inference data)'
      }
    >
      {isCloud ? (
        <GlobeIcon size={14} color="#f59e0b" />
      ) : (
        <CheckShieldIcon size={14} color="var(--defense-pass)" />
      )}
      <span>Mode: <strong>{runtimeMode}</strong></span>
    </div>
  );
}

