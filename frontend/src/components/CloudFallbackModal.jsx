import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { SettingsIcon, CheckShieldIcon, GlobeIcon, CloseIcon } from './Icons';

export default function CloudFallbackModal({ isOpen, onClose }) {
  const [settings, setSettings] = useState({
    enabled: true,
    auto_fallback: true,
    active_provider: 'grok',
    grok_configured: false,
    zai_configured: false,
    grok_masked: null,
    zai_masked: null,
    grok_model: 'grok-2',
    zai_model: 'z.ai-chat',
  });

  const [grokInput, setGrokInput] = useState('');
  const [zaiInput, setZaiInput] = useState('');
  const [activeProvider, setActiveProvider] = useState('grok');
  const [autoFallback, setAutoFallback] = useState(true);
  const [enabled, setEnabled] = useState(true);

  const [testingProvider, setTestingProvider] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      setTestResult(null);
      setSaveSuccess(false);
      setGrokInput('');
      setZaiInput('');
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      const data = await apiClient.getFallbackSettings();
      setSettings(data);
      setActiveProvider(data.active_provider || 'grok');
      setAutoFallback(data.auto_fallback ?? true);
      setEnabled(data.enabled ?? true);
    } catch (err) {
      console.error('Failed to load fallback settings:', err);
    }
  };

  const handleTestKey = async (provider) => {
    setTestingProvider(provider);
    setTestResult(null);
    try {
      const testKey = provider === 'grok' ? (grokInput.trim() || null) : (zaiInput.trim() || null);
      const res = await apiClient.testFallbackKey(provider, testKey);
      setTestResult({ provider, ...res });
    } catch (err) {
      setTestResult({
        provider,
        success: false,
        error: err.message || 'Connection test failed',
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      const payload = {
        enabled,
        auto_fallback: autoFallback,
        active_provider: activeProvider,
      };
      if (grokInput.trim()) payload.grok_key = grokInput.trim();
      if (zaiInput.trim()) payload.zai_key = zaiInput.trim();

      await apiClient.updateFallbackSettings(payload);
      await loadSettings();
      setSaveSuccess(true);
      setGrokInput('');
      setZaiInput('');
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 10, 20, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-secondary, #111827)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '560px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(255, 255, 255, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
              }}
            >
              <GlobeIcon size={18} color="#f59e0b" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary, #fff)' }}>
                Cloud Fallback Settings
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '0.75rem', color: 'var(--text-secondary, #94a3b8)' }}>
                Zero-crash promotion to Grok (xAI) or Z.ai when local hardware hits limits
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary, #94a3b8)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px',
              display: 'flex',
            }}
          >
            <CloseIcon size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', maxHeight: '75vh', overflowY: 'auto' }}>
          {/* Master Toggle */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary, #fff)' }}>
                Cloud API Fallback
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #94a3b8)' }}>
                Prevent OOM failures by seamlessly continuing on cloud runtime
              </div>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                style={{ width: '18px', height: '18px', accentColor: 'var(--accent-cyan, #06b6d4)', cursor: 'pointer' }}
              />
            </label>
          </div>

          {/* Active Provider Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary, #94a3b8)', marginBottom: '8px' }}>
              Preferred Cloud Provider
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setActiveProvider('grok')}
                style={{
                  padding: '12px',
                  borderRadius: '10px',
                  border: activeProvider === 'grok' ? '1px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.08)',
                  background: activeProvider === 'grok' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  color: activeProvider === 'grok' ? '#f59e0b' : 'var(--text-primary, #fff)',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div>Grok (xAI)</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary, #94a3b8)', fontWeight: 400, marginTop: '2px' }}>
                  Model: {settings.grok_model}
                </div>
              </button>

              <button
                type="button"
                onClick={() => setActiveProvider('zai')}
                style={{
                  padding: '12px',
                  borderRadius: '10px',
                  border: activeProvider === 'zai' ? '1px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.08)',
                  background: activeProvider === 'zai' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                  color: activeProvider === 'zai' ? '#f59e0b' : 'var(--text-primary, #fff)',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div>Z.ai API</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary, #94a3b8)', fontWeight: 400, marginTop: '2px' }}>
                  Model: {settings.zai_model}
                </div>
              </button>
            </div>
          </div>

          {/* Grok API Key Field */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary, #94a3b8)' }}>
                Grok API Key (xAI)
              </label>
              <span style={{ fontSize: '0.72rem', color: settings.grok_configured ? 'var(--defense-pass, #10b981)' : '#94a3b8' }}>
                {settings.grok_configured ? `Configured (${settings.grok_masked})` : 'Not Configured'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="password"
                placeholder={settings.grok_configured ? 'Paste new key to update...' : 'xai-...'}
                value={grokInput}
                onChange={(e) => setGrokInput(e.target.value)}
                style={{
                  flex: 1,
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '9px 12px',
                  color: '#fff',
                  fontSize: '0.85rem',
                }}
              />
              <button
                type="button"
                disabled={testingProvider === 'grok' || (!grokInput.trim() && !settings.grok_configured)}
                onClick={() => handleTestKey('grok')}
                style={{
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid rgba(245, 158, 11, 0.4)',
                  color: '#f59e0b',
                  borderRadius: '8px',
                  padding: '0 14px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: (testingProvider === 'grok' || (!grokInput.trim() && !settings.grok_configured)) ? 'not-allowed' : 'pointer',
                  opacity: (testingProvider === 'grok' || (!grokInput.trim() && !settings.grok_configured)) ? 0.5 : 1,
                }}
              >
                {testingProvider === 'grok' ? 'Testing...' : 'Test'}
              </button>
            </div>
          </div>

          {/* Z.ai API Key Field */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary, #94a3b8)' }}>
                Z.ai API Key
              </label>
              <span style={{ fontSize: '0.72rem', color: settings.zai_configured ? 'var(--defense-pass, #10b981)' : '#94a3b8' }}>
                {settings.zai_configured ? `Configured (${settings.zai_masked})` : 'Not Configured'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="password"
                placeholder={settings.zai_configured ? 'Paste new key to update...' : 'zai-...'}
                value={zaiInput}
                onChange={(e) => setZaiInput(e.target.value)}
                style={{
                  flex: 1,
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '9px 12px',
                  color: '#fff',
                  fontSize: '0.85rem',
                }}
              />
              <button
                type="button"
                disabled={testingProvider === 'zai' || (!zaiInput.trim() && !settings.zai_configured)}
                onClick={() => handleTestKey('zai')}
                style={{
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid rgba(245, 158, 11, 0.4)',
                  color: '#f59e0b',
                  borderRadius: '8px',
                  padding: '0 14px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: (testingProvider === 'zai' || (!zaiInput.trim() && !settings.zai_configured)) ? 'not-allowed' : 'pointer',
                  opacity: (testingProvider === 'zai' || (!zaiInput.trim() && !settings.zai_configured)) ? 0.5 : 1,
                }}
              >
                {testingProvider === 'zai' ? 'Testing...' : 'Test'}
              </button>
            </div>
          </div>

          {/* Test Feedback Notice */}
          {testResult && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '0.78rem',
                background: testResult.success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${testResult.success ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                color: testResult.success ? 'var(--defense-pass, #10b981)' : '#ef4444',
              }}
            >
              {testResult.success
                ? `✓ ${testResult.message || 'Connected successfully'}`
                : `✗ ${testResult.error || 'Connection test failed'}`}
            </div>
          )}

          {/* Success Notice */}
          {saveSuccess && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '0.78rem',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: 'var(--defense-pass, #10b981)',
              }}
            >
              ✓ Settings saved and encrypted successfully.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
            background: 'rgba(255, 255, 255, 0.02)',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: 'var(--text-secondary, #94a3b8)',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            Close
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '8px 20px',
              borderRadius: '8px',
              background: 'var(--accent-cyan, #06b6d4)',
              border: 'none',
              color: '#000',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: saving ? 'not-allowed' : 'pointer',
              opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}
