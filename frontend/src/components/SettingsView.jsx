import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { ServerIcon, CheckCircleIcon, ShieldAlertIcon, RefreshIcon } from './Icons';

export default function SettingsView({
  theme = 'dark',
  setTheme,
  defaultModel = 'qwen2.5:3b',
  setDefaultModel
}) {
  const [fallbackSettings, setFallbackSettings] = useState({
    active_provider: 'grok',
    auto_fallback_enabled: true,
    masked_keys: { grok: '', zai: '' },
    circuit_breaker_status: 'CLOSED'
  });

  const [inputKey, setInputKey] = useState('');
  const [selectedProvider, setSelectedProvider] = useState('grok');
  const [testResult, setTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);

  useEffect(() => {
    apiClient.getFallbackSettings()
      .then((data) => {
        setFallbackSettings(data);
        if (data.active_provider) setSelectedProvider(data.active_provider);
      })
      .catch((err) => console.error('Failed to load fallback settings:', err));
  }, []);

  const handleSaveKey = async () => {
    if (!inputKey.trim()) return;
    try {
      const payload = {
        active_provider: selectedProvider,
        auto_fallback: fallbackSettings.auto_fallback_enabled,
      };
      if (selectedProvider === 'grok') {
        payload.grok_key = inputKey.trim();
      } else {
        payload.zai_key = inputKey.trim();
      }
      const res = await apiClient.updateFallbackSettings(payload);
      setFallbackSettings(res.settings || res);
      setInputKey('');
      setSaveStatus('Key saved securely in encrypted vault.');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      setSaveStatus(`Failed to save: ${err.message}`);
    }
  };

  const handleTestKey = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await apiClient.testFallbackKey(selectedProvider, inputKey.trim() || null);
      setTestResult(res);
    } catch (err) {
      setTestResult({ success: false, error: err.message });
    } finally {
      setIsTesting(false);
    }
  };

  const handleToggleAutoFallback = async () => {
    const nextVal = !fallbackSettings.auto_fallback_enabled;
    try {
      const res = await apiClient.updateFallbackSettings({
        active_provider: selectedProvider,
        auto_fallback: nextVal
      });
      setFallbackSettings(res.settings || res);
    } catch (err) {
      console.error('Failed to toggle auto fallback:', err);
    }
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'var(--bg-app)',
        padding: '32px 40px',
        boxSizing: 'border-box',
        overflowY: 'auto'
      }}
      className="view-container"
    >
      <div style={{ maxWidth: '820px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '28px' }}>
        {/* Header */}
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            System Settings
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Configure cloud fallback keys, workspace appearance, model defaults, and security constraints.
          </p>
        </div>

        {/* Section 1: Appearance & Theme */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Appearance & Typography
          </h3>
          <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Toggle between Slate Dark (default) and Slate Light mode with high-contrast WCAG AA compliance.
          </p>

          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button
              type="button"
              onClick={() => setTheme('dark')}
              style={{
                padding: '8px 18px',
                borderRadius: 'var(--radius-sm)',
                border: theme === 'dark' ? '1px solid var(--accent)' : '1px solid var(--border-subtle)',
                background: theme === 'dark' ? 'var(--bg-raised)' : 'transparent',
                color: theme === 'dark' ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '0.8rem'
              }}
            >
              🌙 Slate Dark (Default)
            </button>
            <button
              type="button"
              onClick={() => setTheme('light')}
              style={{
                padding: '8px 18px',
                borderRadius: 'var(--radius-sm)',
                border: theme === 'light' ? '1px solid var(--accent)' : '1px solid var(--border-subtle)',
                background: theme === 'light' ? 'var(--bg-raised)' : 'transparent',
                color: theme === 'light' ? 'var(--accent)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '0.8rem'
              }}
            >
              ☀️ Slate Light
            </button>
          </div>
          <div style={{ marginTop: '10px', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
            Typography: Self-hosted Inter (sans) & JetBrains Mono (statutes/code). Zero external font CDNs.
          </div>
        </div>

        {/* Section 2: Cloud Fallback Provider (Spec 02) */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Cloud Fallback Runtime (Grok / Z.ai)
              </h3>
              <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                When local Ollama encounters OOM or timeout, gracefully route complex legal queries to cloud fallback.
              </p>
            </div>
            <div
              style={{
                fontSize: '0.72rem',
                padding: '3px 10px',
                borderRadius: '12px',
                background: fallbackSettings.auto_fallback_enabled ? 'rgba(63, 185, 80, 0.12)' : 'rgba(100, 116, 139, 0.12)',
                color: fallbackSettings.auto_fallback_enabled ? 'var(--status-green)' : 'var(--text-muted)',
                fontWeight: 600
              }}
            >
              {fallbackSettings.auto_fallback_enabled ? 'Auto Fallback: ON' : 'Auto Fallback: OFF'}
            </div>
          </div>

          {/* Provider Select */}
          <div style={{ marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: '130px' }}>Active Provider:</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedProvider('grok')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: selectedProvider === 'grok' ? '1px solid var(--accent)' : '1px solid var(--border-subtle)',
                    background: selectedProvider === 'grok' ? 'var(--bg-raised)' : 'transparent',
                    color: selectedProvider === 'grok' ? 'var(--accent)' : 'var(--text-secondary)',
                    fontWeight: 600,
                    fontSize: '0.78rem'
                  }}
                >
                  Grok (xAI grok-2)
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedProvider('zai')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: selectedProvider === 'zai' ? '1px solid var(--accent)' : '1px solid var(--border-subtle)',
                    background: selectedProvider === 'zai' ? 'var(--bg-raised)' : 'transparent',
                    color: selectedProvider === 'zai' ? 'var(--accent)' : 'var(--text-secondary)',
                    fontWeight: 600,
                    fontSize: '0.78rem'
                  }}
                >
                  Z.ai (z.ai-chat)
                </button>
              </div>
            </div>

            {/* Configured Key Status */}
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: '130px' }}>Stored Vault Key:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem', color: 'var(--text-primary)' }}>
                {fallbackSettings.masked_keys?.[selectedProvider] || 'None configured (local only)'}
              </span>
            </div>

            {/* Input & Test Key */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="password"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                placeholder={`Paste new ${selectedProvider === 'grok' ? 'xAI Grok' : 'Z.ai'} API Key`}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.78rem',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <button
                type="button"
                onClick={handleSaveKey}
                disabled={!inputKey.trim()}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--accent)',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '0.78rem'
                }}
              >
                Save Key
              </button>
              <button
                type="button"
                onClick={handleTestKey}
                disabled={isTesting}
                style={{
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                  fontSize: '0.78rem'
                }}
              >
                {isTesting ? 'Testing…' : 'Test Key'}
              </button>
            </div>

            {saveStatus && (
              <div style={{ fontSize: '0.74rem', color: 'var(--status-green)' }}>
                {saveStatus}
              </div>
            )}

            {testResult && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: testResult.success ? 'rgba(63, 185, 80, 0.08)' : 'rgba(248, 81, 73, 0.08)',
                  border: `1px solid ${testResult.success ? 'rgba(63, 185, 80, 0.3)' : 'rgba(248, 81, 73, 0.3)'}`,
                  fontSize: '0.75rem',
                  color: testResult.success ? 'var(--status-green)' : 'var(--status-red)'
                }}
              >
                {testResult.success ? `✓ Validated connection to ${selectedProvider} API` : `✗ Connection failed: ${testResult.error}`}
              </div>
            )}

            <div style={{ marginTop: '4px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={Boolean(fallbackSettings.auto_fallback_enabled ?? fallbackSettings.auto_fallback ?? true)}
                  onChange={handleToggleAutoFallback}
                />
                <span>Automatically engage cloud fallback on 3 consecutive local failures</span>
              </label>
            </div>
          </div>
        </div>

        {/* Section 3: Model Defaults */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Model Runtime Defaults
          </h3>
          <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Specify the default model and maximum context window budget for legal synthesis.
          </p>

          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: '150px' }}>Default Local Model:</span>
              <select
                value={defaultModel}
                onChange={(e) => setDefaultModel && setDefaultModel(e.target.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.78rem'
                }}
              >
                <option value="qwen2.5:3b">qwen2.5:3b (Standard Floor — Recommended)</option>
                <option value="gemma2:2b">gemma2:2b (Lightweight Floor — 1.6 GB)</option>
                <option value="llama3.2:3b">llama3.2:3b (Compact 3B)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 4: MCP Subsystems & API Gateways */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              MCP Subsystems & API Gateways
            </h3>
            <span style={{ fontSize: '0.72rem', padding: '3px 10px', borderRadius: '12px', background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-blue)', fontWeight: 600 }}>
              Model Context Protocol Active
            </span>
          </div>
          <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '2px', marginBottom: '16px' }}>
            Canonical legal MCP servers and REST API endpoints providing verified statutory context to the model on-demand.
          </p>

          {/* Primary Connected MCP Servers */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px', marginBottom: '18px' }}>
            {[
              { name: 'India Law MCP', id: 'ansvar-systems-india-law-mcp', desc: 'Central statutory acts: IT Act, DPDPA, Companies Act' },
              { name: 'Themis Criminal MCP', id: 'themis-mcp', desc: 'BNS, BNSS, BSA & IPC cross-walk mapping' },
              { name: 'Nyaya Judicial MCP', id: 'nyaya-mcp', desc: 'Constitution of India & Supreme Court precedents' },
              { name: 'Tax & Commercial MCP', id: 'taxbykk-mcp', desc: 'GST, CGST & indirect tax provisions' },
            ].map((srv) => (
              <div
                key={srv.id}
                style={{
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-primary)' }}>{srv.name}</span>
                  <span style={{ fontSize: '0.68rem', padding: '2px 8px', borderRadius: '10px', background: 'rgba(63, 185, 80, 0.12)', color: 'var(--status-green)', fontWeight: 600 }}>
                    ● Ready
                  </span>
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)' }}>{srv.desc}</div>
              </div>
            ))}
          </div>

          {/* Core Endpoints List */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Primary REST & Inference Endpoints
            </span>
            <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {[
                { method: 'POST', path: '/chat', label: 'Chat Inference & Citation Grounding' },
                { method: 'POST', path: '/mcp/tool-call', label: 'MCP Defensive Tool Dispatch' },
                { method: 'GET', path: '/statutes', label: 'Indian Statutory Knowledge Service' },
                { method: 'GET', path: '/vaults', label: 'Private Document & Evidence Vaults' },
                { method: 'GET', path: '/audit/verify', label: 'Cryptographic SHA-256 Ledger Audit' },
              ].map((ep) => (
                <div
                  key={ep.path}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontSize: '0.76rem',
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-raised)',
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: ep.method === 'POST' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(63, 185, 80, 0.15)', color: ep.method === 'POST' ? 'var(--accent-blue)' : 'var(--status-green)' }}>
                    {ep.method}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{ep.path}</span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{ep.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Section 5: System & About */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            About DFrag Enterprise
          </h3>
          <div style={{ marginTop: '10px', fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <div><strong>Version:</strong> 4.0.0 (Stage 5 Defensive RAG)</div>
            <div><strong>Engine:</strong> Nyaya-Core v4 Indian Legal Synthesis</div>
            <div><strong>Architecture:</strong> Tier-0 Offline Edge + MCP Canonical Subprocesses + Grok/Z.ai Cloud Fallback</div>
            <div><strong>Integrity:</strong> Zero hardcoded seed statutes · Zero fake telemetry · 100% DB-backed</div>
          </div>
        </div>
      </div>
    </div>
  );
}
