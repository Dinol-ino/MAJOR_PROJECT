import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

/** Workspace settings: appearance, network mode (explicit + audited), opt-in cloud fallback. */
export default function SettingsView({ theme = 'dark', setTheme }) {
  const [mode, setMode] = useState(null);
  const [modeBusy, setModeBusy] = useState(false);
  const [fallback, setFallback] = useState(null);
  const [provider, setProvider] = useState('grok');
  const [keyInput, setKeyInput] = useState('');
  const [message, setMessage] = useState(null);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    apiClient.getNetworkMode().then(setMode).catch(() => setMode(null));
    apiClient.getFallbackSettings().then((f) => { setFallback(f); if (f.active_provider) setProvider(f.active_provider); }).catch(() => setFallback(null));
  }, []);

  const switchMode = async (next) => {
    const warning = next === 'ONLINE'
      ? 'Switch to ONLINE? Research may contact allowlisted legal sources. This change is recorded in the security log.'
      : 'Switch to OFFLINE? All outbound network calls will be blocked.';
    if (!window.confirm(warning)) return;
    setModeBusy(true);
    try {
      await apiClient.setNetworkMode(next);
      setMode(await apiClient.getNetworkMode());
    } catch (err) {
      setMessage({ kind: 'error', text: err.message });
    } finally {
      setModeBusy(false);
    }
  };

  const updateFallback = async (patch, okText) => {
    try {
      const res = await apiClient.updateFallbackSettings({ active_provider: provider, ...patch });
      setFallback(res.settings || res);
      if (okText) setMessage({ kind: 'ok', text: okText });
    } catch (err) {
      setMessage({ kind: 'error', text: err.message });
    }
  };

  const saveKey = async () => {
    if (!keyInput.trim()) return;
    await updateFallback({ [provider === 'grok' ? 'grok_key' : 'zai_key']: keyInput.trim() }, 'Key stored encrypted on the server. It is never sent back to the browser.');
    setKeyInput('');
  };

  const testKey = async () => {
    setTestResult(null);
    try {
      setTestResult(await apiClient.testFallbackKey(provider, keyInput.trim() || null));
    } catch (err) {
      setTestResult({ success: false, error: err.message });
    }
  };

  const masked = fallback ? (provider === 'grok' ? fallback.grok_masked : fallback.zai_masked) : null;

  return (
    <div style={st.page}>
      <Section title="Appearance">
        <div style={{ display: 'flex', gap: 8 }}>
          {['dark', 'light'].map((t) => (
            <button key={t} type="button" onClick={() => setTheme(t)} style={theme === t ? st.btnOn : st.btn}>{t === 'dark' ? 'Dark' : 'Light'}</button>
          ))}
        </div>
      </Section>

      <Section title="Network mode" note="OFFLINE blocks every outbound call: research sources, model-hub search and cloud key tests. Changes are audited.">
        {mode ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={st.value}>Currently <strong>{mode.mode}</strong></span>
            <button type="button" style={st.btn} disabled={modeBusy} onClick={() => switchMode(mode.mode === 'OFFLINE' ? 'ONLINE' : 'OFFLINE')}>
              Switch to {mode.mode === 'OFFLINE' ? 'ONLINE' : 'OFFLINE'}
            </button>
          </div>
        ) : <span style={st.muted}>Unavailable</span>}
      </Section>

      <Section
        title="Cloud fallback (opt-in)"
        note="Off by default. The standard pipeline answers only with your local model. Cloud fallback applies only to the legacy direct pipeline, only after a local failure, and never to requests that include project-vault documents."
      >
        {!fallback ? <span style={st.muted}>Unavailable</span> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label style={st.check}>
              <input type="checkbox" checked={!!fallback.enabled} onChange={(e) => updateFallback({ enabled: e.target.checked })} /> Enable cloud fallback
            </label>
            <label style={st.check}>
              <input type="checkbox" checked={!!fallback.auto_fallback} disabled={!fallback.enabled} onChange={(e) => updateFallback({ auto_fallback: e.target.checked })} /> Use automatically when the local model fails
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select value={provider} onChange={(e) => setProvider(e.target.value)} style={st.input}>
                <option value="grok">xAI Grok</option>
                <option value="zai">Z.ai</option>
              </select>
              <span style={st.muted}>{masked ? `Stored key: ${masked}` : 'No key stored'}</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input type="password" autoComplete="off" placeholder="Paste API key (write-only)" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} style={{ ...st.input, flex: 1 }} />
              <button type="button" style={st.btn} onClick={saveKey} disabled={!keyInput.trim()}>Save</button>
              <button type="button" style={st.btn} onClick={testKey}>Test</button>
            </div>
            {testResult && (
              <span style={{ color: testResult.success ? 'var(--status-green)' : 'var(--status-red)', fontSize: '0.84rem' }}>
                {testResult.success ? testResult.message : (testResult.error || testResult.message || testResult.detail || 'Test failed')}
              </span>
            )}
          </div>
        )}
      </Section>

      {message && <p role="status" style={{ color: message.kind === 'ok' ? 'var(--status-green)' : 'var(--status-red)', fontSize: '0.85rem' }}>{message.text}</p>}
    </div>
  );
}

function Section({ title, note, children }) {
  return (
    <section style={st.section}>
      <h2 style={st.h2}>{title}</h2>
      {note && <p style={st.note}>{note}</p>}
      {children}
    </section>
  );
}

const st = {
  page: { height: '100%', overflowY: 'auto', padding: '28px 40px 64px', maxWidth: 820 },
  section: { borderTop: '1px solid var(--border-subtle)', padding: '20px 0 16px' },
  h2: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.15rem', marginBottom: 6 },
  note: { color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.5, marginBottom: 12, maxWidth: 640 },
  value: { fontSize: '0.92rem' },
  muted: { color: 'var(--text-muted)', fontSize: '0.84rem' },
  check: { display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.9rem' },
  input: { background: 'var(--bg-input)', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', padding: '8px 10px', fontSize: '0.88rem' },
  btn: { background: 'transparent', border: '1px solid var(--border-medium)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)', padding: '7px 14px', cursor: 'pointer', fontSize: '0.84rem' },
  btnOn: { background: 'var(--accent-blue-subtle)', border: '1px solid var(--accent)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)', padding: '7px 14px', cursor: 'pointer', fontSize: '0.84rem' },
};
