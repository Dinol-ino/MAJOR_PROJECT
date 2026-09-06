import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { CheckShieldIcon, GlobeIcon } from './Icons';

export default function ModeIndicator() {
  const [networkMode, setNetworkMode] = useState('OFFLINE');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function fetchMode() {
      try {
        const response = await fetch('/api/research/mode');
        if (response.ok) {
          const data = await response.json();
          if (isMounted && data.mode) {
            setNetworkMode(data.mode.toUpperCase());
          }
        }
      } catch (err) {
        // Default to OFFLINE mode on fallback
        if (isMounted) setNetworkMode('OFFLINE');
      }
    }
    fetchMode();
    return () => {
      isMounted = false;
    };
  }, []);

  const isOffline = networkMode === 'OFFLINE';

  return (
    <div
      style={{
        background: isOffline ? 'rgba(16, 185, 129, 0.1)' : 'rgba(56, 189, 248, 0.1)',
        border: `1px solid ${isOffline ? 'rgba(16, 185, 129, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`,
        borderRadius: '16px',
        padding: '5px 12px',
        color: isOffline ? 'var(--defense-pass)' : 'var(--accent-cyan)',
        fontSize: '0.78rem',
        fontWeight: 700,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'default',
        userSelect: 'none',
        boxShadow: isOffline ? '0 0 10px rgba(16, 185, 129, 0.15)' : '0 0 10px rgba(56, 189, 248, 0.15)',
      }}
      title={
        isOffline
          ? 'Network Mode: OFFLINE (Strict local air-gapped execution — zero outbound network requests guaranteed)'
          : 'Network Mode: ONLINE (SSRF-protected outbound retrieval restricted strictly to allowlisted legal domains)'
      }
    >
      {isOffline ? (
        <CheckShieldIcon size={14} color="var(--defense-pass)" />
      ) : (
        <GlobeIcon size={14} color="var(--accent-cyan)" />
      )}
      <span>Mode: <strong>{networkMode}</strong></span>
    </div>
  );
}
