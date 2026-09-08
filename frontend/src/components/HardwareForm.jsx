import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';
import {
  CpuIcon,
  DownloadIcon,
  CheckCircleIcon,
  RefreshIcon,
  ServerIcon,
  SparklesIcon,
  CheckShieldIcon,
  ShieldAlertIcon
} from './Icons';

export default function HardwareForm({
  onModelRecommended,
  selectedModel,
  setSelectedModel,
  isOpen,
  onClose,
  setRecommendedModels,
  isFullView = false
}) {
  const [telemetry, setTelemetry] = useState(null);
  const [streamStatus, setStreamStatus] = useState('connecting'); // 'live' | 'offline' | 'connecting'
  const [sparklineData, setSparklineData] = useState([]);
  const [catalogData, setCatalogData] = useState(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [pullProgress, setPullProgress] = useState({});

  const pullControllers = useRef({});
  const onModelRecommendedRef = useRef(onModelRecommended);
  onModelRecommendedRef.current = onModelRecommended;

  const selectedModelRef = useRef(selectedModel);
  selectedModelRef.current = selectedModel;

  const setRecommendedModelsRef = useRef(setRecommendedModels);
  setRecommendedModelsRef.current = setRecommendedModels;

  // Append sample to sparkline ring buffer (max 30 points)
  const addSparklineSample = useCallback((val) => {
    setSparklineData((prev) => {
      const next = [...prev, val];
      if (next.length > 30) return next.slice(next.length - 30);
      return next;
    });
  }, []);

  // 1. Fetch Dynamic Model Recommendations
  const fetchModels = useCallback(async () => {
    setModelsLoading(true);
    try {
      const res = await apiClient.getRecommendedModels();
      setCatalogData(res);
      if (setRecommendedModelsRef.current) {
        setRecommendedModelsRef.current(res.recommended || []);
      }
      if (!selectedModelRef.current && res.recommended && res.recommended.length > 0) {
        const firstInstalled = res.recommended.find((m) => m.installed) || res.recommended[0];
        if (onModelRecommendedRef.current) {
          onModelRecommendedRef.current(firstInstalled.model_id);
        }
      }
    } catch (e) {
      console.error('Failed to load recommended models:', e);
    } finally {
      setModelsLoading(false);
    }
  }, []);

  // 2. Persistent SSE Telemetry Stream + Initial Fast Hydration
  useEffect(() => {
    let es = null;
    let reconnectTimeout = null;
    let active = true;

    // Instant initial hydration via fast <50ms snapshot
    apiClient.getTelemetrySample()
      .then((data) => {
        if (active && data) {
          setTelemetry(data);
          setStreamStatus('live');
          addSparklineSample(data.cpu?.load_percent || 0);
        }
      })
      .catch(() => {
        // Fallback silently if offline
      });

    fetchModels();

    const connect = () => {
      try {
        const streamUrl = `${apiClient.BASE_URL || ''}/api/telemetry/stream`;
        es = new EventSource(streamUrl);

        es.onopen = () => {
          if (active) setStreamStatus('live');
        };

        es.onmessage = (event) => {
          if (!active) return;
          try {
            const data = JSON.parse(event.data);
            if (data.cpu) {
              setTelemetry(data);
              setStreamStatus('live');
              addSparklineSample(data.cpu.load_percent || 0);
            }
          } catch (e) {
            console.debug('Telemetry chunk parse error:', e);
          }
        };

        es.onerror = () => {
          if (!active) return;
          setStreamStatus('offline');
          if (es) {
            es.close();
            es = null;
          }
          reconnectTimeout = setTimeout(connect, 3000);
        };
      } catch (err) {
        setStreamStatus('offline');
        reconnectTimeout = setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      active = false;
      if (es) es.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      // Abort any active pulls on unmount
      Object.values(pullControllers.current).forEach((ctrl) => ctrl && ctrl.abort());
    };
  }, [addSparklineSample, fetchModels]);

  // Handle Model Pull via SSE Stream
  const handlePullModel = (modelId) => {
    if (pullControllers.current[modelId]) return;

    setPullProgress((prev) => ({
      ...prev,
      [modelId]: { percent: 0, status: 'starting', completed: 0, total: 0 }
    }));

    const controller = apiClient.pullModelStream(
      modelId,
      (progress) => {
        setPullProgress((prev) => ({
          ...prev,
          [modelId]: {
            percent: Math.min(100, Math.round(progress.percent || 0)),
            status: progress.status || 'downloading',
            completed: progress.completed || 0,
            total: progress.total || 0,
            digest: progress.digest
          }
        }));
      },
      () => {
        delete pullControllers.current[modelId];
        setPullProgress((prev) => ({
          ...prev,
          [modelId]: { percent: 100, status: 'done' }
        }));
        fetchModels();
        if (setSelectedModel) setSelectedModel(modelId);
        if (onModelRecommended) onModelRecommended(modelId);
      },
      (err) => {
        delete pullControllers.current[modelId];
        setPullProgress((prev) => ({
          ...prev,
          [modelId]: { status: 'error', error: err.message }
        }));
      }
    );

    pullControllers.current[modelId] = controller;
  };

  const handleCancelPull = (modelId) => {
    if (pullControllers.current[modelId]) {
      pullControllers.current[modelId].abort();
      delete pullControllers.current[modelId];
    }
    setPullProgress((prev) => {
      const copy = { ...prev };
      delete copy[modelId];
      return copy;
    });
  };

  if (!isFullView && isOpen === false) return null;

  // Derived telemetry presentation
  const cpu = telemetry?.cpu || {
    name: 'Multi-Core Processor',
    load_percent: 0,
    cores_physical: 4,
    cores_logical: 8,
    arch: 'x86_64'
  };

  const ram = telemetry?.ram || {
    total_gb: 16.0,
    available_gb: 8.0,
    used_percent: 50
  };

  const gpu = telemetry?.gpu || {
    detected: false,
    name: 'No Dedicated GPU (CPU Only)',
    vram_total_gb: 0.0,
    vram_used_gb: 0.0,
    util_percent: 0,
    mode: 'cpu'
  };

  const disk = telemetry?.disk || {
    free_gb: 100.0,
    total_gb: 512.0
  };

  const tier = telemetry?.tier || {
    tier_code: 'tier_0',
    tier_label: 'Tier 0 (Lightweight)',
    reason: 'Tier 0 — CPU mode active',
    max_model: '3B (Q4)'
  };

  let tierColor = 'var(--accent-cyan)';
  if (tier.tier_code === 'tier_1') tierColor = 'var(--accent-blue)';
  else if (tier.tier_code === 'tier_2') tierColor = 'var(--defense-pass)';
  else if (tier.tier_code === 'tier_3') tierColor = '#c084fc';

  const modelsList = catalogData?.recommended || [];
  const ollamaOnline = catalogData?.ollama_online ?? true;

  const content = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: 'rgba(0, 210, 180, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <CpuIcon size={20} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                Hardware Engine & Model Manager
              </h2>
              <span
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '10px',
                  background: streamStatus === 'live' ? 'rgba(46, 204, 113, 0.15)' : 'rgba(231, 76, 60, 0.15)',
                  color: streamStatus === 'live' ? '#2ecc71' : '#e74c3c',
                  border: `1px solid ${streamStatus === 'live' ? 'rgba(46, 204, 113, 0.3)' : 'rgba(231, 76, 60, 0.3)'}`
                }}
              >
                {streamStatus === 'live' ? '● SSE Live' : '○ Telemetry Offline'}
              </span>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
              Live telemetry via Server-Sent Events, deterministic hardware tiering, and real-time model streaming.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => fetchModels()}
            disabled={modelsLoading}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              padding: '6px 12px',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.75rem',
              cursor: 'pointer'
            }}
          >
            <RefreshIcon size={13} className={modelsLoading ? 'pulse-text' : ''} />
            <span>Refresh Models</span>
          </button>

          {!isFullView && onClose && (
            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '1.2rem',
                cursor: 'pointer',
                padding: '4px'
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Hardware Tier Banner & Deterministic Reason Tooltip */}
      <div
        style={{
          background: 'rgba(255, 255, 255, 0.02)',
          border: `1px solid ${tierColor}44`,
          borderLeft: `4px solid ${tierColor}`,
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Evaluated Hardware Tier
            </span>
            <span
              style={{
                background: `${tierColor}22`,
                color: tierColor,
                border: `1px solid ${tierColor}66`,
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '4px'
              }}
            >
              {tier.tier_label}
            </span>
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', marginTop: '4px' }}>
            {tier.reason}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Max Model Ceiling</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
            {tier.max_model}
          </div>
        </div>
      </div>

      {/* Live Telemetry Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: isFullView ? 'repeat(4, 1fr)' : 'repeat(2, 1fr)', gap: '12px' }}>
        {/* CPU Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>CPU Processor</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
              {!telemetry ? <span className="pulse-text">Sampling…</span> : `${cpu.load_percent}% Load`}
            </span>
          </div>
          <div style={{ fontSize: '1.02rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={cpu.name}>
            {!telemetry ? <span style={{ opacity: 0.5 }}>Probing CPU architecture…</span> : cpu.name}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {!telemetry ? 'Hardware detection in progress' : `${cpu.cores_physical} Physical / ${cpu.cores_logical} Logical Cores (${cpu.arch})`}
          </div>

          {/* Sparkline Graph */}
          {sparklineData.length > 1 && (
            <div style={{ marginTop: '10px', height: '24px', width: '100%', display: 'flex', alignItems: 'flex-end', gap: '2px' }}>
              {sparklineData.map((val, idx) => (
                <div
                  key={idx}
                  style={{
                    flex: 1,
                    height: `${Math.max(10, Math.min(100, val))}%`,
                    background: 'var(--accent-cyan)',
                    opacity: 0.3 + (idx / sparklineData.length) * 0.7,
                    borderRadius: '1px'
                  }}
                  title={`${val}% load`}
                />
              ))}
            </div>
          )}
        </div>

        {/* System RAM Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>System RAM</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: ram.used_percent > 85 ? '#e74c3c' : 'var(--accent-cyan)' }}>
              {!telemetry ? <span className="pulse-text">Measuring…</span> : `${ram.used_percent}% Used`}
            </span>
          </div>
          <div style={{ fontSize: '1.02rem', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '4px' }}>
            {!telemetry ? <span style={{ opacity: 0.5 }}>Reading virtual memory…</span> : `${ram.available_gb} GB Free / ${ram.total_gb} GB Total`}
          </div>
          <div style={{ width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', height: '5px', marginTop: '6px', overflow: 'hidden' }}>
            <div
              style={{
                width: !telemetry ? '40%' : `${ram.used_percent}%`,
                height: '100%',
                background: ram.used_percent > 85 ? '#e74c3c' : 'var(--accent-cyan)',
                transition: 'width 0.4s ease'
              }}
              className={!telemetry ? 'pulse-text' : ''}
            />
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '6px' }}>
            {!telemetry ? 'Checking OS memory buffers' : (ram.available_gb < 3.0 ? '⚠️ High memory pressure — CPU offload limited' : 'Available for In-Memory Vectors & Model Weights')}
          </div>
        </div>

        {/* GPU / VRAM Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>GPU Acceleration</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: gpu.detected ? 'var(--accent-blue)' : 'var(--text-muted)' }}>
              {!telemetry ? <span className="pulse-text">Scanning…</span> : (gpu.detected ? `${gpu.util_percent}% Utilized` : 'CPU Mode')}
            </span>
          </div>
          <div style={{ fontSize: '1.02rem', fontWeight: 700, color: gpu.detected ? 'var(--accent-blue)' : 'var(--text-secondary)', marginTop: '4px' }}>
            {!telemetry ? <span style={{ opacity: 0.5 }}>Checking CUDA / NVML…</span> : (gpu.detected ? `${gpu.vram_used_gb || 0} / ${gpu.vram_total_gb || 0} GB VRAM` : 'No CUDA GPU')}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={gpu.name}>
            {!telemetry ? 'Evaluating GPU acceleration' : (gpu.detected ? gpu.name : 'Running in CPU-Only Mode (Tier 0 Qualified)')}
          </div>
        </div>

        {/* Storage Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Disk Storage</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Model Weights</span>
          </div>
          <div style={{ fontSize: '1.02rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
            {!telemetry ? <span style={{ opacity: 0.5 }}>Measuring disk…</span> : `${disk.free_gb} GB Free`}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            Sufficient space for legal LLM downloads & ChromaDB vectors
          </div>
        </div>
      </div>

      {/* Recommended Models Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Hardware-Matched Model Catalog
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
              Dynamically evaluated against your live hardware capacity and Ollama installations.
            </p>
          </div>

          {!ollamaOnline && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', background: 'rgba(231, 76, 60, 0.12)', border: '1px solid rgba(231, 76, 60, 0.3)', borderRadius: '6px', color: '#e74c3c', fontSize: '0.72rem' }}>
              <ShieldAlertIcon size={14} />
              <span>Ollama unreachable at 127.0.0.1:11434</span>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {modelsList.map((model) => {
            const mId = model.model_id;
            const isSelected = selectedModel === mId;
            const progress = pullProgress[mId];
            const isPulling = progress && progress.status !== 'done' && progress.status !== 'error';

            return (
              <div
                key={mId}
                style={{
                  background: isSelected ? 'rgba(0, 210, 180, 0.05)' : 'var(--bg-card)',
                  border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {model.display_name}
                      </span>
                      {model.parameter_size && (
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '1px 6px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                          {model.parameter_size}
                        </span>
                      )}
                      {model.quantization && (
                        <span style={{ fontSize: '0.68rem', padding: '1px 6px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '4px', color: 'var(--text-dim)' }}>
                          {model.quantization.toUpperCase()}
                        </span>
                      )}
                      {model.recommended_for_tier && (
                        <span style={{ fontSize: '0.68rem', fontWeight: 600, padding: '1px 6px', background: 'rgba(46, 204, 113, 0.12)', color: '#2ecc71', borderRadius: '4px' }}>
                          Tier Matched
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '4px', display: 'flex', gap: '14px' }}>
                      <span>Size: ~{model.size_gb} GB</span>
                      <span>RAM Needed: {model.ram_required_gb} GB</span>
                      {model.vram_required_gb && <span>VRAM Needed: {model.vram_required_gb} GB</span>}
                      <span>Context: {model.context_window} tokens</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {model.installed ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', fontWeight: 600, color: '#2ecc71' }}>
                          <CheckCircleIcon size={14} />
                          <span>Installed</span>
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            if (setSelectedModel) setSelectedModel(mId);
                            if (onModelRecommended) onModelRecommended(mId);
                            if (!isFullView && onClose) onClose();
                          }}
                          style={{
                            background: isSelected ? 'var(--accent-cyan)' : 'var(--bg-input)',
                            color: isSelected ? '#0d0f14' : 'var(--text-primary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '6px',
                            padding: '6px 12px',
                            fontSize: '0.74rem',
                            fontWeight: 700,
                            cursor: 'pointer'
                          }}
                        >
                          {isSelected ? 'Active Model' : 'Select'}
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {isPulling ? (
                          <button
                            type="button"
                            onClick={() => handleCancelPull(mId)}
                            style={{
                              background: 'rgba(231, 76, 60, 0.15)',
                              color: '#e74c3c',
                              border: '1px solid rgba(231, 76, 60, 0.3)',
                              borderRadius: '6px',
                              padding: '6px 10px',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              cursor: 'pointer'
                            }}
                          >
                            Cancel
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handlePullModel(mId)}
                            style={{
                              background: 'var(--accent-gradient)',
                              color: 'white',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '6px 14px',
                              fontSize: '0.74rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}
                          >
                            <DownloadIcon size={13} />
                            <span>{model.action_label}</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Pulling Progress Bar & Details */}
                {isPulling && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                      <span>Status: {progress.status}</span>
                      <span>{progress.percent}%</span>
                    </div>
                    <div style={{ width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${progress.percent}%`,
                          height: '100%',
                          background: 'var(--accent-cyan)',
                          transition: 'width 0.2s ease'
                        }}
                      />
                    </div>
                  </div>
                )}

                {progress?.status === 'error' && (
                  <div style={{ fontSize: '0.72rem', color: '#e74c3c', marginTop: '4px' }}>
                    ⚠️ {progress.error || 'Failed to pull model'}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  if (isFullView) {
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
        <div style={{ maxWidth: '960px', margin: '0 auto' }}>
          {content}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '440px',
        height: '100vh',
        background: 'var(--bg-sidebar)',
        borderLeft: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-lg)',
        padding: '24px',
        zIndex: 1000,
        boxSizing: 'border-box',
        overflowY: 'auto'
      }}
      className="view-container"
    >
      {content}
    </div>
  );
}
