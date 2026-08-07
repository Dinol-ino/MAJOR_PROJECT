import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import { CpuIcon, DownloadIcon, CheckCircleIcon, RefreshIcon, ServerIcon } from './Icons';

export default function HardwareForm({
  onModelRecommended,
  selectedModel,
  setSelectedModel,
  isOpen,
  onClose,
  setRecommendedModels
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
  
  let hwTier = 'MEDIUM';
  let uploadLimit = 'Up to 20 files';
  if (vramAvailable >= 8 || ramAvailable >= 16) {
    hwTier = 'HIGH';
    uploadLimit = 'Up to 35 files';
  } else if (vramAvailable >= 12 || ramAvailable >= 32) {
    hwTier = 'ULTRA';
    uploadLimit = 'Up to 50 files';
  } else if (ramAvailable < 6 && vramAvailable < 2) {
    hwTier = 'MINIMUM';
    uploadLimit = 'Up to 5 files';
  }

  if (isOpen === false) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '380px',
        height: '100vh',
        background: '#18181b',
        borderLeft: '1px solid #27272a',
        boxShadow: '-10px 0 30px rgba(0,0,0,0.6)',
        padding: '24px',
        zIndex: 1000,
        boxSizing: 'border-box',
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ fontFamily: 'var(--font-title)', fontSize: '1.1rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CpuIcon size={20} color="var(--accent-color)" />
          System Hardware Specs
        </h3>
        <button
          type="button"
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '1.2rem', cursor: 'pointer' }}
        >
          ✕
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Mode</span>
        <button
          type="button"
          onClick={() => setManualOverride(!manualOverride)}
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid #27272a',
            borderRadius: '6px',
            color: '#f8fafc',
            fontSize: '0.75rem',
            padding: '4px 10px',
            cursor: 'pointer',
          }}
        >
          {manualOverride ? 'Auto-Detect' : 'Manual Override'}
        </button>
      </div>

      {detectedHw && !manualOverride && (
        <div style={{ background: '#121214', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid #27272a' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-color)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ServerIcon size={16} />
            Hardware Profile ({hwTier} Tier)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem', color: '#94a3b8' }}>
            <div>CPU: {detectedHw.cpu_cores || 4} cores</div>
            <div>RAM: {Math.round(detectedHw.ram_total_gb || 8)} GB</div>
            <div>GPU: {detectedHw.gpu_name || (detectedHw.gpu_available ? 'Active GPU' : 'None (CPU-only)')}</div>
            <div>VRAM: {detectedHw.gpu_vram_gb || 0} GB</div>
          </div>
          <div style={{ marginTop: '10px', fontSize: '0.78rem', color: '#cbd5e1', borderTop: '1px solid #27272a', paddingTop: '8px' }}>
            File Upload Limit: <strong style={{ color: 'var(--safe-color)' }}>{uploadLimit}</strong>
          </div>
        </div>
      )}

      {manualOverride && (
        <form onSubmit={handleManualSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>System RAM</label>
            <select
              value={ram}
              onChange={(e) => setRam(parseInt(e.target.value))}
              style={{ width: '100%', background: '#121214', color: '#f8fafc', border: '1px solid #27272a', borderRadius: '6px', padding: '8px' }}
            >
              <option value={4}>4 GB</option>
              <option value={8}>8 GB</option>
              <option value={16}>16 GB</option>
              <option value={32}>32 GB</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>VRAM / GPU</label>
            <select
              value={vram}
              onChange={(e) => setVram(parseInt(e.target.value))}
              style={{ width: '100%', background: '#121214', color: '#f8fafc', border: '1px solid #27272a', borderRadius: '6px', padding: '8px' }}
            >
              <option value={0}>CPU-only (0 GB)</option>
              <option value={2}>2 GB</option>
              <option value={4}>4 GB</option>
              <option value={8}>8 GB</option>
              <option value={12}>12 GB+</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={loading}
            style={{ background: 'var(--accent-color)', border: 'none', borderRadius: '6px', padding: '8px', color: 'white', fontWeight: 600, cursor: 'pointer' }}
          >
            Update Hardware Override
          </button>
        </form>
      )}

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 600 }}>Recommended Models:</span>
          <button type="button" onClick={() => fetchRecommendationsAndHealth(manualOverride ? ram : null, manualOverride ? vram : null)} style={{ background: 'none', border: 'none', color: 'var(--accent-color)', cursor: 'pointer' }}>
            <RefreshIcon size={14} />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {recommendations.map((rec) => {
            const mId = rec.model_id || rec.model;
            const isInstalled = installedModels.some((im) => im.includes(mId) || mId.includes(im));
            const prog = pullProgress[mId];
            const isSelected = selectedModel === mId;

            return (
              <div
                key={mId}
                onClick={() => setSelectedModel && setSelectedModel(mId)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: isSelected ? 'rgba(99, 102, 241, 0.12)' : '#121214',
                  border: `1px solid ${isSelected ? 'var(--accent-color)' : '#27272a'}`,
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>{rec.display_name || mId}</div>
                    <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Size: {rec.size_gb || 2.0} GB | Context: {rec.context_window || 8192}</div>
                  </div>

                  <div>
                    {isInstalled ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: 'var(--safe-color)', background: 'rgba(34, 197, 94, 0.1)', padding: '3px 8px', borderRadius: '12px' }}>
                        <CheckCircleIcon size={12} /> Installed
                      </span>
                    ) : prog && prog.percent < 100 ? (
                      <span style={{ fontSize: '0.72rem', color: 'var(--accent-color)' }}>Downloading {prog.percent}%</span>
                    ) : (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAutoPull(mId);
                        }}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          background: 'var(--accent-color)',
                          border: 'none',
                          borderRadius: '6px',
                          color: 'white',
                          fontSize: '0.72rem',
                          padding: '4px 10px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        <DownloadIcon size={12} /> Auto-Pull
                      </button>
                    )}
                  </div>
                </div>

                {prog && prog.percent < 100 && (
                  <div style={{ marginTop: '8px', background: '#0f172a', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                    <div style={{ width: `${prog.percent}%`, height: '100%', background: 'var(--accent-color)', transition: 'width 0.3s ease' }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
