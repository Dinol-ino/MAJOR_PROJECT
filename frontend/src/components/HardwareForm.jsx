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
    <div className="card" style={{ padding: 'var(--space-2)' }}>
      <div className="section-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
        <span className="section-title">Hardware Recommendation</span>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-1)' }}>
          <div>
            <label className="label">System RAM</label>
            <select
              className="select"
              value={ram}
              onChange={(e) => setRam(parseInt(e.target.value))}
              style={{ width: '100%' }}
            >
              <option value={4}>4 GB</option>
              <option value={8}>8 GB</option>
              <option value={16}>16 GB</option>
              <option value={32}>32 GB</option>
              <option value={64}>64 GB</option>
            </select>
          </div>
          <div>
            <label className="label">VRAM / GPU</label>
            <select
              className="select"
              value={vram}
              onChange={(e) => setVram(parseInt(e.target.value))}
              style={{ width: '100%' }}
            >
              <option value={0}>No GPU</option>
              <option value={2}>2 GB</option>
              <option value={4}>4 GB</option>
              <option value={8}>8 GB</option>
              <option value={12}>12 GB</option>
              <option value={16}>16 GB+</option>
            </select>
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Analyzing...' : 'Get Recommendation'}
        </button>
      </form>

      {recommendations.length > 0 && (
        <div style={{ marginTop: 'var(--space-2)', borderTop: '1px solid var(--border-default)', paddingTop: 'var(--space-2)' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 'var(--space-1)' }}>
            Recommended Models
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {recommendations.map((rec) => (
              <div
                key={rec.model}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px var(--space-1)',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/></svg>
                  {rec.model}
                </span>
                <code className="mono" style={{ background: 'var(--bg-primary)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-muted)' }}>
                  {rec.pull}
                </code>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
