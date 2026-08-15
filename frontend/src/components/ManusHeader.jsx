import React, { useState } from 'react';
import ShieldToggle from './ShieldToggle';
import { ChevronDownIcon, CpuIcon, SparklesIcon } from './Icons';

export default function ManusHeader({
  selectedModel,
  setSelectedModel,
  recommendedModels,
  shieldOn,
  setShieldOn,
  onToggleHardwareDrawer
}) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  return (
    <header
      style={{
        height: '52px',
        borderBottom: '1px solid #27272a',
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#121214',
        boxSizing: 'border-box',
        zIndex: 10,
      }}
    >
      {/* Left: Model Selector Dropdown */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
          style={{
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid #27272a',
            borderRadius: '8px',
            padding: '6px 12px',
            color: '#f8fafc',
            fontSize: '0.88rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
          }}
        >
          <span>Model: {selectedModel ? selectedModel.toUpperCase() : 'QWEN2.5:3B'}</span>
          <ChevronDownIcon size={14} color="#94a3b8" />
        </button>

        {modelDropdownOpen && (
          <div
            style={{
              position: 'absolute',
              top: '42px',
              left: 0,
              background: '#1e1e22',
              border: '1px solid #27272a',
              borderRadius: '8px',
              width: '240px',
              padding: '6px 0',
              boxShadow: '0 10px 25px rgba(0,0,0,0.6)',
              zIndex: 100,
            }}
          >
            <div style={{ padding: '6px 12px', fontSize: '0.72rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
              Recommended Local Models
            </div>
            {recommendedModels.map((m) => {
              const mId = m.model_id || m.model;
              return (
                <div
                  key={mId}
                  onClick={() => {
                    setSelectedModel(mId);
                    setModelDropdownOpen(false);
                  }}
                  style={{
                    padding: '8px 12px',
                    fontSize: '0.85rem',
                    color: selectedModel === mId ? 'var(--accent-color)' : '#f8fafc',
                    background: selectedModel === mId ? 'rgba(99,102,241,0.12)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span>{m.display_name || mId}</span>
                  {selectedModel === mId && <SparklesIcon size={14} color="var(--accent-color)" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right Controls: Hardware Specs & Security Shield */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          type="button"
          onClick={onToggleHardwareDrawer}
          style={{
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid #27272a',
            borderRadius: '16px',
            padding: '4px 12px',
            color: '#94a3b8',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
        >
          <CpuIcon size={14} color="var(--accent-color)" />
          <span>Hardware Specs</span>
        </button>

        <ShieldToggle shieldOn={shieldOn} onToggle={setShieldOn} />
      </div>
    </header>
  );
}
