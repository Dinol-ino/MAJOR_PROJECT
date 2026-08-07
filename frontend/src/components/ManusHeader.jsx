import React, { useState } from 'react';
import ShieldToggle from './ShieldToggle';
import { ChevronDownIcon, CpuIcon, SparklesIcon } from './Icons';

export default function ManusHeader({
  selectedModel,
  setSelectedModel,
  recommendedModels,
  shieldOn,
  setShieldOn,
  onToggleHardwareDrawer,
  detectedHw
}) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  return (
    <header
      style={{
        height: '56px',
        borderBottom: '1px solid #27272a',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#121214',
        boxSizing: 'border-box',
        zIndex: 10,
      }}
    >
      {/* Left: Model Selector Dropdown (Manus 1.6 Lite style) */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
          style={{
            background: 'none',
            border: 'none',
            color: '#f8fafc',
            fontFamily: 'var(--font-title)',
            fontSize: '1rem',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
        >
          <span>{selectedModel ? selectedModel.toUpperCase() : 'MANUS 1.6 LITE'}</span>
          <ChevronDownIcon size={14} color="#94a3b8" />
        </button>

        {modelDropdownOpen && (
          <div
            style={{
              position: 'absolute',
              top: '40px',
              left: 0,
              background: '#1e1e22',
              border: '1px solid #27272a',
              borderRadius: '8px',
              width: '220px',
              padding: '6px 0',
              boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
              zIndex: 100,
            }}
          >
            <div style={{ padding: '6px 12px', fontSize: '0.72rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
              Dynamic Recommended Models
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

      {/* Right Controls: Hardware Drawer Trigger, Shield Toggle, Plan Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid #27272a', borderRadius: '16px', padding: '3px 10px', fontSize: '0.78rem', color: '#94a3b8' }}>
          <span>Free plan</span>
          <span style={{ color: 'var(--accent-color)', fontWeight: 600, cursor: 'pointer' }}>Upgrade</span>
        </div>

        <div style={{ fontSize: '0.8rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <SparklesIcon size={14} color="#64748b" />
          <span>1,242</span>
        </div>
      </div>
    </header>
  );
}
