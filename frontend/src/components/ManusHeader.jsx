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
  CheckShieldIcon
} from './Icons';

export default function ManusHeader({
  selectedModel,
  setSelectedModel,
  recommendedModels,
  shieldOn,
  setShieldOn,
  onToggleHardwareDrawer,
  activeView,
  onClearThread
}) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  const viewTitles = {
    chat: { title: 'Legal Copilot', icon: SparklesIcon, color: 'var(--accent-indigo)', badge: null },
    graph: { title: 'Citation Graph', icon: GraphIcon, color: 'var(--accent-cyan)', badge: 'BETA' },
    statutes: { title: 'Statute Knowledge', icon: LibraryIcon, color: 'var(--accent-blue)', badge: null },
    audit: { title: 'Cryptographic Audit', icon: AuditIcon, color: 'var(--defense-pass)', badge: null },
    hardware: { title: 'Hardware Engine', icon: CpuIcon, color: 'var(--accent-cyan)', badge: null },
    mcp: { title: 'API & MCP Tools', icon: CodeIcon, color: 'var(--accent-blue)', badge: null },
  };

  const currentView = viewTitles[activeView] || viewTitles.chat;
  const ViewIcon = currentView.icon;

  const defaultModelsList = [
    { model_id: 'dfrag-legal:7b', display_name: 'DFrag Legal 7B (Indian Law)', tier: 'Tier 1' },
    { model_id: 'saullm:7b', display_name: 'SaulLM 7B (Legal Domain)', tier: 'Tier 1' },
    { model_id: 'qwen2.5:7b', display_name: 'Qwen 2.5 7B (High Accuracy)', tier: 'Tier 1' },
    { model_id: 'qwen2.5:3b', display_name: 'Qwen 2.5 3B (Standard Floor)', tier: 'Tier 0' },
    { model_id: 'gemma2:2b', display_name: 'Gemma 2 2B (Lightweight Floor)', tier: 'Tier 0' },
    { model_id: 'qwen2.5:14b', display_name: 'Qwen 2.5 14B (Enterprise)', tier: 'Tier 2' },
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
          <span style={{ fontSize: '0.62rem', background: 'rgba(0, 210, 180, 0.15)', color: 'var(--accent-cyan)', padding: '1px 6px', borderRadius: '10px', fontWeight: 700 }}>
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
            borderRadius: '20px',
            padding: '6px 14px',
            color: 'var(--text-primary)',
            fontSize: '0.82rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <span style={{ color: 'var(--accent-cyan)', fontSize: '0.75rem' }}>MODEL:</span>
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
              borderRadius: '12px',
              width: '280px',
              padding: '8px 0',
              boxShadow: 'var(--shadow-lg)',
              zIndex: 100,
            }}
          >
            <div style={{ padding: '6px 14px', fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Local AI Model Selection
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
                    fontSize: '0.83rem',
                    color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)',
                    background: isSelected ? 'rgba(0, 210, 180, 0.1)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: isSelected ? 700 : 500 }}>{m.display_name || mId}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{m.tier || 'Local Model'}</div>
                  </div>
                  {isSelected && <SparklesIcon size={14} color="var(--accent-cyan)" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right Controls: Clear Thread, Hardware Specs & Security Shield */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {activeView === 'chat' && onClearThread && (
          <button
            type="button"
            onClick={onClearThread}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
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
            borderRadius: '8px',
            padding: '6px 12px',
            color: 'var(--text-secondary)',
            fontSize: '0.78rem',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <CpuIcon size={14} color="var(--accent-cyan)" />
          <span>Hardware Specs</span>
        </button>

        <ModeIndicator />
        <ShieldToggle shieldOn={shieldOn} onToggle={setShieldOn} />
      </div>
    </header>
  );
}
