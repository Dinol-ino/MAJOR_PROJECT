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
      const res = await apiClient.updateFallbackSettings({
        provider: selectedProvider,
        api_key: inputKey.trim(),
        auto_fallback_enabled: fallbackSettings.auto_fallback_enabled
      });
      setFallbackSettings(res);
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
        provider: selectedProvider,
        auto_fallback_enabled: nextVal
      });
      setFallbackSettings(res);
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
                  checked={fallbackSettings.auto_fallback_enabled}
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
                <option value="qwen2.5:3b">qwen2.5:3b (Standard Floor — Tier 0/1)</option>
                <option value="gemma2:2b">gemma2:2b (Lightweight Floor — Tier 0)</option>
                <option value="llama3.2:3b">llama3.2:3b (3B Compact)</option>
                <option value="qwen2.5:7b">qwen2.5:7b (High Accuracy — Tier 1)</option>
                <option value="dfrag-legal:7b">dfrag-legal:7b (Specialized Indian Law)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 4: System & About */}
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
