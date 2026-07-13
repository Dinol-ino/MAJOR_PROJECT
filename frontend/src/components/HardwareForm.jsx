import React, { useState } from 'react';
import { apiClient } from '../api/client';

export default function HardwareForm({ onModelRecommended }) {
  const [ram, setRam] = useState(8);
  const [vram, setVram] = useState(0);
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState([]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await apiClient.recommend(ram, vram);
      setRecommendations(response.recommended);
      if (onModelRecommended && response.recommended.length > 0) {
        onModelRecommended(response.recommended[0].model);
      }
    } catch (err) {
      console.error(err);
      alert('Failed to get hardware recommendations.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="hardware-form-container glass-panel" style={{ padding: '20px', marginBottom: '20px' }}>
      <h3 style={{ fontFamily: 'var(--font-title)', marginBottom: '12px' }}>💻 Hardware Model Recommender</h3>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>System RAM (GB)</label>
          <select 
            value={ram} 
            onChange={(e) => setRam(parseInt(e.target.value))}
            style={{
              background: '#1e293b',
              color: 'var(--text-primary)',
              border: '1px solid var(--panel-border)',
              borderRadius: '8px',
              padding: '8px 12px',
            }}
          >
            <option value={4}>4 GB</option>
            <option value={8}>8 GB</option>
            <option value={16}>16 GB</option>
            <option value={32}>32 GB</option>
            <option value={64}>64 GB</option>
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>VRAM / GPU (GB)</label>
          <select 
            value={vram} 
            onChange={(e) => setVram(parseInt(e.target.value))}
            style={{
              background: '#1e293b',
              color: 'var(--text-primary)',
              border: '1px solid var(--panel-border)',
              borderRadius: '8px',
              padding: '8px 12px',
            }}
          >
            <option value={0}>No GPU (CPU-only)</option>
            <option value={2}>2 GB</option>
            <option value={4}>4 GB</option>
            <option value={8}>8 GB</option>
            <option value={12}>12 GB</option>
            <option value={16}>16 GB+</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={loading}
          style={{
            background: 'var(--accent-color)',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 20px',
            color: 'white',
            fontWeight: '600',
          }}
        >
          {loading ? 'Recommending...' : 'Get Recommendation'}
        </button>
      </form>

      {recommendations.length > 0 && (
        <div style={{ marginTop: '16px', background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
          <h4 style={{ fontSize: '0.9rem', marginBottom: '8px', color: 'var(--text-secondary)' }}>Recommended Models:</h4>
          <ul style={{ listStyle: 'none' }}>
            {recommendations.map((rec) => (
              <li key={rec.model} style={{ fontSize: '0.95rem', marginBottom: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>🤖 <strong>{rec.model}</strong></span>
                <code style={{ background: '#0f172a', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>{rec.pull}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
