import React, { useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { ChevronDownIcon, ClearIcon, CheckShieldIcon, GlobeIcon } from './Icons';

const VIEW_TITLES = {
  chat: 'Legal Copilot',
  graph: 'Citation Graph',
  statutes: 'Statute Library',
  hardware: 'Hardware & Models',
  sources: 'Sources & Research',
  security: 'Security & Integrity',
  settings: 'Settings',
};

/**
 * Top bar. The model selector lists ONLY models installed in the local runtime; switching
 * activates the model on the server (verify -> warm -> health -> persist). The conversation is kept.
 */
export default function ManusHeader({
  activeView,
  onClearThread,
  models,          // { installed: [], active: string|null, runtimeOnline: bool, loading: bool }
  onActivateModel, // async (name) => void
  onOpenModels,
}) {
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(null);
  const [switchError, setSwitchError] = useState('');
  const [mode, setMode] = useState(null);
  const menuRef = useRef(null);

  useEffect(() => {
    let active = true;
    apiClient.getNetworkMode().then((m) => active && setMode(m.mode)).catch(() => active && setMode(null));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const installed = models?.installed || [];
  const active = models?.active || null;

  const choose = async (name) => {
    if (name === active) { setOpen(false); return; }
    setSwitching(name);
    setSwitchError('');
    try {
      await onActivateModel(name);
      setOpen(false);
    } catch (err) {
      setSwitchError(err.message || 'Could not activate this model.');
    } finally {
      setSwitching(null);
    }
  };

  let modelLabel;
  if (models?.loading) modelLabel = 'Checking models…';
  else if (!models?.runtimeOnline) modelLabel = 'Model runtime offline';
  else if (!active) modelLabel = 'No local model active';
  else modelLabel = active;

  return (
    <header style={st.bar}>
      <h1 style={st.title}>{VIEW_TITLES[activeView] || VIEW_TITLES.chat}</h1>

      <div style={{ position: 'relative' }} ref={menuRef}>
        <button type="button" style={st.modelBtn} onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}>
          <span style={st.modelKey}>Model</span>
          <span style={{ color: active ? 'var(--text-primary)' : 'var(--status-amber)' }}>{modelLabel}</span>
          <ChevronDownIcon size={13} color="var(--text-muted)" />
        </button>
        {open && (
          <div style={st.menu} role="listbox">
            {installed.length === 0 && (
              <div style={st.empty}>
                {models?.runtimeOnline
                  ? 'No models are installed in the local runtime yet.'
                  : 'The local model runtime (Ollama) is not reachable.'}
              </div>
            )}
            {installed.map((m) => (
              <button
                type="button"
                key={m.name}
                role="option"
                aria-selected={m.name === active}
                disabled={!!switching}
                style={{ ...st.option, ...(m.name === active ? st.optionOn : null) }}
                onClick={() => choose(m.name)}
                title={m.fit_reason || ''}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{m.name}</span>
                <span style={st.optionMeta}>
                  {[m.parameter_size, m.quantization, m.safety_tier && m.safety_tier !== 'SAFE' ? m.safety_tier.toLowerCase() : null]
                    .filter(Boolean).join(' · ')}
                  {switching === m.name ? ' · loading…' : ''}
                  {m.name === active ? ' · active' : ''}
                </span>
              </button>
            ))}
            {switchError && <div role="alert" style={st.err}>{switchError}</div>}
            <button type="button" style={st.manage} onClick={() => { setOpen(false); onOpenModels(); }}>
              Download or manage models →
            </button>
          </div>
        )}
      </div>

      <div style={st.right}>
        {mode && (
          <span style={st.chip} title={mode === 'OFFLINE' ? 'No outbound network calls are made.' : 'Research may query allowlisted sources.'}>
            <GlobeIcon size={13} color={mode === 'OFFLINE' ? 'var(--text-muted)' : 'var(--status-amber)'} /> {mode === 'OFFLINE' ? 'Offline' : 'Online research'}
          </span>
        )}
        <span style={st.chip} title="Input, context and output guards run on every request.">
          <CheckShieldIcon size={13} color="var(--defense-pass)" /> Shield enforced
        </span>
        {activeView === 'chat' && (
          <button type="button" style={st.ghost} onClick={onClearThread} title="Start a fresh view of this thread">
            <ClearIcon size={13} /> Clear
          </button>
        )}
      </div>
    </header>
  );
}

const st = {
  bar: { height: 56, borderBottom: '1px solid var(--border-subtle)', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16, background: 'var(--bg-app)', zIndex: 20 },
  title: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.15rem', color: 'var(--text-primary)', flex: '0 0 auto', minWidth: 180 },
  modelBtn: { display: 'flex', alignItems: 'center', gap: 10, background: 'transparent', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.82rem' },
  modelKey: { color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em' },
  menu: { position: 'absolute', top: 40, left: 0, width: 320, background: 'var(--bg-modal)', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', padding: 6, zIndex: 50 },
  empty: { padding: '10px 10px', color: 'var(--text-muted)', fontSize: '0.82rem' },
  option: { width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2, background: 'transparent', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 10px', color: 'var(--text-primary)', cursor: 'pointer', textAlign: 'left' },
  optionOn: { background: 'var(--accent-blue-subtle)' },
  optionMeta: { color: 'var(--text-muted)', fontSize: '0.72rem' },
  err: { color: 'var(--status-red)', fontSize: '0.78rem', padding: '6px 10px' },
  manage: { width: '100%', background: 'transparent', border: 'none', borderTop: '1px solid var(--border-subtle)', marginTop: 4, padding: '8px 10px', textAlign: 'left', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.8rem' },
  right: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 },
  chip: { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.76rem', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', padding: '4px 10px' },
  ghost: { display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '5px 10px', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.78rem' },
};
