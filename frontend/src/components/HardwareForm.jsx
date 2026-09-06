import React, { useState, useEffect, useCallback } from 'react';
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
  const [detectedHw, setDetectedHw] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [installedModels, setInstalledModels] = useState([]);
  const [pullProgress, setPullProgress] = useState({});
  const [manualOverride, setManualOverride] = useState(false);
  const [ram, setRam] = useState(8);
  const [vram, setVram] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchRecommendationsAndHealth = useCallback(async (manualRam = null, manualVram = null) => {
    setLoading(true);
    try {
      const recData = await apiClient.recommend(manualRam, manualVram);
      setRecommendations(recData.recommended || []);
      setDetectedHw(recData.detected_hardware || null);

      if (setRecommendedModels) {
        setRecommendedModels(recData.recommended || []);
      }

      if (recData.recommended && recData.recommended.length > 0 && onModelRecommended && !selectedModel) {
        onModelRecommended(recData.recommended[0].model_id);
      }

      try {
        const healthData = await apiClient.getHealth();
        if (healthData.ollama && healthData.ollama.installed_models) {
          setInstalledModels(healthData.ollama.installed_models);
        }
      } catch (e) {
        console.warn("Could not fetch installed models health:", e);
      }
    } catch (err) {
      console.error("Hardware detection error:", err);
    } finally {
      setLoading(false);
    }
  }, [onModelRecommended, selectedModel, setRecommendedModels]);

  useEffect(() => {
    fetchRecommendationsAndHealth();
  }, [fetchRecommendationsAndHealth]);

  const handleManualSubmit = (e) => {
    e.preventDefault();
    fetchRecommendationsAndHealth(ram, vram);
  };

  const handleAutoPull = async (modelId) => {
    try {
      const response = await apiClient.pullModel(modelId);
      const taskId = response.task_id;
      setPullProgress((prev) => ({
        ...prev,
        [modelId]: { task_id: taskId, percent: 0, status: 'starting' },
      }));

      const interval = setInterval(async () => {
        try {
          const prog = await apiClient.getPullProgress(taskId);
          setPullProgress((prev) => ({
            ...prev,
            [modelId]: {
              task_id: taskId,
              percent: Math.round(prog.percent || 0),
              status: prog.status || 'downloading',
            },
          }));

          if (prog.status === 'done' || prog.percent >= 100) {
            clearInterval(interval);
            const h = await apiClient.getHealth();
            if (h.ollama && h.ollama.installed_models) {
              setInstalledModels(h.ollama.installed_models);
            }
          }
        } catch (err) {
          console.error("Polling progress error:", err);
          clearInterval(interval);
        }
      }, 1000);
    } catch (err) {
      console.error("Auto pull failed:", err);
      alert(`Auto pull failed: ${err.message}`);
    }
  };

  const ramAvailable = detectedHw ? (detectedHw.ram_available_gb || detectedHw.ram_total_gb || 0) : ram;
  const vramAvailable = detectedHw ? (detectedHw.gpu_vram_gb || 0) : vram;

  let hwTier = 'TIER 0 (Lightweight)';
  let tierColor = 'var(--accent-cyan)';
  let uploadLimit = 'Up to 10 files';
  if (vramAvailable >= 16 || ramAvailable >= 32) {
    hwTier = 'TIER 2 (High Performance)';
    tierColor = 'var(--defense-pass)';
    uploadLimit = 'Up to 50 files';
  } else if (vramAvailable >= 8 || ramAvailable >= 16) {
    hwTier = 'TIER 1 (Standard Legal)';
    tierColor = 'var(--accent-blue)';
    uploadLimit = 'Up to 25 files';
  }

  if (!isFullView && isOpen === false) return null;

  const content = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(0, 210, 180, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CpuIcon size={18} color="var(--accent-cyan)" />
          </div>
          <div>
            <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Hardware & AI Model Engine
            </h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Live telemetry, hardware tier mapping, and local open-source LLM management.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => fetchRecommendationsAndHealth()}
            disabled={loading}
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '6px 10px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
          >
            <RefreshIcon size={12} className={loading ? 'pulse-text' : ''} />
            <span>Refresh</span>
          </button>

          {!isFullView && onClose && (
            <button
              type="button"
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.1rem', cursor: 'pointer' }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Mode Switcher: Auto Detect vs Manual Simulation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-input)', padding: '6px 10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Detection Mode</span>
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            type="button"
            onClick={() => { setManualOverride(false); fetchRecommendationsAndHealth(); }}
            style={{
              padding: '4px 10px',
              fontSize: '0.74rem',
              fontWeight: 600,
              borderRadius: '6px',
              border: 'none',
              background: !manualOverride ? 'var(--accent-cyan)' : 'transparent',
              color: !manualOverride ? '#0d0f14' : 'var(--text-secondary)',
            }}
          >
            Physical Auto
          </button>
          <button
            type="button"
            onClick={() => setManualOverride(true)}
            style={{
              padding: '4px 10px',
              fontSize: '0.74rem',
              fontWeight: 600,
              borderRadius: '6px',
              border: 'none',
              background: manualOverride ? 'var(--accent-blue)' : 'transparent',
              color: manualOverride ? 'white' : 'var(--text-secondary)',
            }}
          >
            Manual Simulation
          </button>
        </div>
      </div>

      {/* Live Telemetry Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: isFullView ? 'repeat(4, 1fr)' : 'repeat(2, 1fr)', gap: '12px' }}>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>CPU Processor</div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
            {detectedHw ? `${detectedHw.cpu_cores} Physical Cores` : 'Detecting...'}
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {detectedHw ? detectedHw.cpu_name : 'x86_64 / ARM'}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>System RAM</div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px' }}>
            {detectedHw ? `${detectedHw.ram_available_gb} GB / ${detectedHw.ram_total_gb} GB` : `${ram} GB`}
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {detectedHw && detectedHw.ram_available_gb < 2 ? '⚠️ Low RAM - CPU Mode' : 'Available for Inference'}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>GPU / VRAM</div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--accent-blue)', marginTop: '2px' }}>
            {detectedHw && detectedHw.gpu_available ? `${detectedHw.gpu_vram_gb} GB VRAM` : 'No CUDA GPU'}
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {detectedHw ? (detectedHw.gpu_name || 'CPU GGML Offload') : 'CPU Mode'}
          </div>
        </div>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Hardware Tier</div>
          <div style={{ fontSize: '1.05rem', fontWeight: 700, color: tierColor, marginTop: '2px' }}>
            {hwTier}
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            Batch Limit: {uploadLimit}
          </div>
        </div>
      </div>

      {/* Manual Override Form if enabled */}
      {manualOverride && (
        <form onSubmit={handleManualSubmit} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-medium)', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Simulate Hardware Specifications
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>RAM (GB)</label>
              <input
                type="number"
                min="2"
                max="128"
                value={ram}
                onChange={(e) => setRam(Number(e.target.value))}
                style={{ width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-medium)', color: 'white', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>VRAM (GB)</label>
              <input
                type="number"
                min="0"
                max="96"
                value={vram}
                onChange={(e) => setVram(Number(e.target.value))}
                style={{ width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-medium)', color: 'white', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem' }}
              />
            </div>
          </div>
          <button
            type="submit"
            style={{ background: 'var(--accent-blue)', border: 'none', borderRadius: '6px', padding: '8px', color: 'white', fontWeight: 600, fontSize: '0.8rem' }}
          >
            Calculate Recommended Models
          </button>
        </form>
      )}

      {/* Model Catalog & Pull Manager */}
      <div>
        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>Recommended Local Models</span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Ollama Engine</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {recommendations.map((model) => {
            const mId = model.model_id;
            const isSelected = selectedModel === mId;
            const isInstalled = installedModels.some((im) => im.toLowerCase().startsWith(mId.toLowerCase()));
            const progress = pullProgress[mId];

            return (
              <div
                key={mId}
                style={{
                  background: isSelected ? 'rgba(0, 210, 180, 0.08)' : 'var(--bg-card)',
                  border: `1px solid ${isSelected ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                  borderRadius: '10px',
                  padding: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        {model.display_name || mId}
                      </span>
                      {isSelected && (
                        <span style={{ fontSize: '0.65rem', background: 'rgba(0, 210, 180, 0.15)', color: 'var(--accent-cyan)', padding: '1px 6px', borderRadius: '10px', fontWeight: 700 }}>
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Size: {model.size_gb} GB • Min RAM: {model.ram_required_gb} GB • {model.tier}
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {isInstalled ? (
                      <button
                        type="button"
                        onClick={() => setSelectedModel(mId)}
                        style={{
                          background: isSelected ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.06)',
                          color: isSelected ? '#0d0f14' : 'var(--text-primary)',
                          border: 'none',
                          borderRadius: '6px',
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                        }}
                      >
                        {isSelected ? 'Selected' : 'Use Model'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleAutoPull(mId)}
                        disabled={progress && progress.status !== 'error' && progress.status !== 'done'}
                        style={{
                          background: 'var(--accent-gradient)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '6px',
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <DownloadIcon size={12} />
                        <span>{progress ? `${progress.percent}%` : 'Auto-Pull'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Pull Progress Bar */}
                {progress && progress.status !== 'done' && (
                  <div style={{ width: '100%', background: 'var(--bg-input)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${progress.percent}%`,
                        height: '100%',
                        background: 'var(--accent-gradient)',
                        transition: 'width 0.3s ease',
                      }}
                    />
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
          overflowY: 'auto',
        }}
        className="view-container"
      >
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>
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
        width: '400px',
        height: '100vh',
        background: 'var(--bg-sidebar)',
        borderLeft: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-lg)',
        padding: '24px',
        zIndex: 1000,
        boxSizing: 'border-box',
        overflowY: 'auto',
      }}
      className="view-container"
    >
      {content}
    </div>
  );
}
