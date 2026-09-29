import React, { useState } from 'react';

/**
 * Context use of the most recent answer, taken from the server's measurements.
 * Estimates (chars/4) are labelled as estimates; runtime token counts are shown when the
 * model reported them. Nothing here is a placeholder.
 */
export default function ContextMeter({ metrics }) {
  const [open, setOpen] = useState(false);
  if (!metrics || !metrics.max_context_tokens) return null;

  const budget = metrics.context_budget_tokens || metrics.max_context_tokens;
  const used = metrics.prompt_tokens ?? ((metrics.evidence_tokens_est || 0) + (metrics.system_prompt_tokens_est || 0));
  const pct = Math.min(100, Math.round((used / Math.max(1, budget)) * 100));
  const fmt = (n) => (n == null ? '—' : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: '0.72rem', cursor: 'pointer', display: 'inline-flex', gap: 8, alignItems: 'center' }}
        title="Context used by the last answer"
      >
        <span>{fmt(used)} / {fmt(budget)} tokens{metrics.prompt_tokens == null ? ' (est.)' : ''}</span>
        <span style={{ width: 60, height: 3, background: 'var(--bg-raised)', display: 'inline-block', position: 'relative' }}>
          <span style={{ position: 'absolute', inset: 0, width: `${pct}%`, background: pct >= 85 ? 'var(--status-amber)' : 'var(--accent)' }} />
        </span>
      </button>
      {open && (
        <div style={{ position: 'absolute', right: 0, bottom: 26, width: 280, background: 'var(--bg-modal)', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-md)', padding: 12, fontSize: '0.78rem', color: 'var(--text-secondary)', zIndex: 40, boxShadow: 'var(--shadow-lg)' }}>
          <Row k="Reasoning level" v={metrics.reasoning_level} />
          <Row k="Model context window" v={fmt(metrics.max_context_tokens)} />
          <Row k="Budget for this level" v={fmt(metrics.context_budget_tokens)} />
          <Row k="Evidence (est.)" v={`${fmt(metrics.evidence_tokens_est)} in ${metrics.evidence_chunks_used ?? 0} passages`} />
          {metrics.evidence_chunks_dropped > 0 && <Row k="Lower-ranked passages left out" v={metrics.evidence_chunks_dropped} />}
          {metrics.graph_neighbors_added > 0 && <Row k="Added via cross-references" v={metrics.graph_neighbors_added} />}
          <Row k="Prompt tokens (runtime)" v={fmt(metrics.prompt_tokens)} />
          <Row k="Answer tokens (runtime)" v={`${fmt(metrics.generation_tokens)} of max ${fmt(metrics.max_output_tokens)}`} />
          {metrics.tokens_per_sec != null && <Row k="Generation speed" v={`${metrics.tokens_per_sec} tok/s`} />}
          {metrics.retrieval_ms != null && <Row k="Retrieval" v={`${metrics.retrieval_ms} ms`} />}
          {metrics.model_latency_ms != null && <Row k="Model" v={`${Math.round(metrics.model_latency_ms)} ms`} />}
          {metrics.total_latency_ms != null && <Row k="Total" v={`${Math.round(metrics.total_latency_ms)} ms`} />}
        </div>
      )}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '2px 0' }}>
      <span style={{ color: 'var(--text-muted)' }}>{k}</span>
      <span style={{ color: 'var(--text-primary)', textAlign: 'right' }}>{v ?? '—'}</span>
    </div>
  );
}
