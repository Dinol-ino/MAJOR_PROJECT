import React, { useState } from 'react';
import ShieldToggle from './ShieldToggle';
import ModeIndicator from './ModeIndicator';
import {
  ChevronDownIcon,
  CpuIcon,
  SparklesIcon,
  GraphIcon,
  LibraryIcon,
  AuditIcon,
  CodeIcon,
  ClearIcon,
  CheckShieldIcon,
  SettingsIcon
} from './Icons';
import CloudFallbackModal from './CloudFallbackModal';

export default function ManusHeader({
  selectedModel,
  setSelectedModel,
  recommendedModels,
  shieldOn,
  setShieldOn,
  onToggleHardwareDrawer,
  activeView,
  onClearThread,
  theme,
  setTheme
}) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [fallbackModalOpen, setFallbackModalOpen] = useState(false);

  const viewTitles = {
    chat: { title: 'Legal Copilot', icon: SparklesIcon, color: 'var(--accent-blue)', badge: null },
    graph: { title: 'Citation Graph', icon: GraphIcon, color: 'var(--accent-pink)', badge: 'BETA' },
    statutes: { title: 'Statute Knowledge', icon: LibraryIcon, color: 'var(--accent-blue)', badge: null },
    audit: { title: 'Cryptographic Audit', icon: AuditIcon, color: 'var(--accent-pink)', badge: null },
    settings: { title: 'System Settings', icon: SettingsIcon, color: 'var(--accent-blue)', badge: null },
  };

  const currentView = viewTitles[activeView] || viewTitles.chat;
  const ViewIcon = currentView.icon;

  const defaultModelsList = [
    { model_id: 'qwen2.5:3b', display_name: 'Qwen 2.5 3B (Standard Floor)', tier: 'Standard' },
    { model_id: 'gemma2:2b', display_name: 'Gemma 2 2B (Lightweight Floor)', tier: 'Lightweight' },
    { model_id: 'llama3.2:3b', display_name: 'Llama 3.2 3B (Compact)', tier: 'Standard' },
  ];

  const modelsToShow = recommendedModels && recommendedModels.length > 0
    ? recommendedModels
    : defaultModelsList;


  return (
    <header
      style={{
        height: '54px',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--bg-sidebar)',
        boxSizing: 'border-box',
        zIndex: 20,
      }}
    >
      {/* Left: View Breadcrumb & Section Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <ViewIcon size={18} color={currentView.color} />
        <span style={{ fontFamily: 'var(--font-title)', fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)' }}>
          {currentView.title}
        </span>
        {currentView.badge && (
          <span style={{ fontSize: '0.62rem', background: 'rgba(255, 0, 127, 0.15)', color: 'var(--accent-pink)', border: '1px solid rgba(255, 0, 127, 0.35)', padding: '1px 6px', borderRadius: '10px', fontWeight: 700 }}>
            {currentView.badge}
          </span>
        )}
      </div>

      {/* Center: Model Selector Dropdown */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-medium)',
            borderRadius: '0px',
            padding: '6px 14px',
            color: 'var(--text-primary)',
            fontSize: '0.78rem',
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: 'var(--shadow-sm)',
            cursor: 'pointer'
          }}
        >
          <span style={{ color: 'var(--accent-gold)', fontSize: '0.72rem', fontWeight: 700 }}>MODEL:</span>
          <span>{selectedModel ? selectedModel.toUpperCase() : 'GEMMA2:2B'}</span>
          <ChevronDownIcon size={13} color="var(--text-muted)" />
        </button>

        {modelDropdownOpen && (
          <div
            style={{
              position: 'absolute',
              top: '42px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'var(--bg-modal)',
              border: '1px solid var(--border-medium)',
              borderTop: '2px solid var(--accent-gold)',
              borderRadius: '0px',
              width: '280px',
              padding: '8px 0',
              boxShadow: 'var(--shadow-lg)',
              zIndex: 100,
            }}
          >
            <div style={{ padding: '6px 14px', fontSize: '0.68rem', color: 'var(--accent-gold)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>
              ✦ Local Model Architecture
            </div>
            {modelsToShow.map((m) => {
              const mId = m.model_id || m.model || m;
              const isSelected = selectedModel === mId;
              return (
                <div
                  key={mId}
                  onClick={() => {
                    setSelectedModel(mId);
                    setModelDropdownOpen(false);
                  }}
                  style={{
                    padding: '9px 14px',
                    fontSize: '0.80rem',
                    fontFamily: 'var(--font-mono)',
                    color: isSelected ? 'var(--accent-gold)' : 'var(--text-primary)',
                    background: isSelected ? 'rgba(212, 175, 55, 0.12)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderLeft: isSelected ? '2px solid var(--accent-gold)' : '2px solid transparent',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: isSelected ? 700 : 500 }}>{m.display_name || mId}</div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{m.tier || 'Local Model'}</div>
                  </div>
                  {isSelected && <SparklesIcon size={14} color="var(--accent-gold)" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right Controls: Theme Switcher, Clear Thread, Hardware Specs & Security Shield */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {setTheme && (
          <button
            type="button"
            onClick={() => setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-medium)',
              borderRadius: '0px',
              padding: '6px 12px',
              color: 'var(--text-secondary)',
              fontSize: '0.70rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              letterSpacing: '0.14em',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
            }}
            title="Toggle Luxury Palette (Alabaster Paper / Charcoal Noir)"
          >
            <span style={{ color: 'var(--accent-gold)' }}>✦</span>
            <span>{theme === 'light' ? 'CHARCOAL' : 'ALABASTER'}</span>
          </button>
        )}

        {activeView === 'chat' && onClearThread && (
          <button
            type="button"
            onClick={onClearThread}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '0px',
              padding: '6px 12px',
              color: 'var(--text-secondary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Clear active conversation"
          >
            <ClearIcon size={13} />
            <span>Clear</span>
          </button>
        )}

        <button
          type="button"
          onClick={onToggleHardwareDrawer}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '0px',
            padding: '6px 12px',
            color: 'var(--text-secondary)',
            fontSize: '0.78rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <CpuIcon size={14} color="var(--accent-gold)" />
          <span>Hardware Specs</span>
        </button>

        <button
          type="button"
          onClick={() => setFallbackModalOpen(true)}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '0px',
            padding: '6px 12px',
            color: 'var(--text-secondary)',
            fontSize: '0.78rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
          title="Configure Cloud Fallback (Grok API & Z.ai)"
        >
          <SettingsIcon size={14} color="var(--accent-gold)" />
          <span>Cloud Fallback</span>
        </button>

        <ModeIndicator />
        <ShieldToggle shieldOn={shieldOn} onToggle={setShieldOn} />
      </div>

      <CloudFallbackModal
        isOpen={fallbackModalOpen}
        onClose={() => setFallbackModalOpen(false)}
      />
    </header>
  );
}

