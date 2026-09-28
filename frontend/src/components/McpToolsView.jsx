import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

/**
 * Sources & Research: what the assistant can actually draw on right now.
 * Local corpus statistics, built-in research capabilities (and whether the current network mode
 * allows them), and any external research servers an operator has configured. Nothing is shown
 * as "connected" unless the backend reports it.
 */
export default function McpToolsView() {
  const [corpus, setCorpus] = useState(null);
  const [mcp, setMcp] = useState(null);
  const [mode, setMode] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([apiClient.getCorpusStatus(), apiClient.getMcpStatus(), apiClient.getNetworkMode()])
      .then(([c, m, n]) => { setCorpus(c); setMcp(m); setMode(n); })
      .catch((err) => setError(err.message));
  }, []);

  const tools = mcp?.tools || [];
  const localTools = tools.filter((t) => ['LOCAL_RETRIEVAL', 'DOCUMENT_SEARCH', 'LEGAL_SEARCH'].includes(t.category));
  const onlineTools = tools.filter((t) => !['LOCAL_RETRIEVAL', 'DOCUMENT_SEARCH', 'LEGAL_SEARCH'].includes(t.category));

  return (
    <div style={st.page}>
      {error && <p style={st.warn}>{error}</p>}

      <section style={st.section}>
        <h2 style={st.h2}>Statutory corpus (local)</h2>
        {!corpus ? <p style={st.muted}>Loading…</p> : corpus.total_chunks === 0 ? (
          <p style={st.p}>No statutes are indexed. Add act text files and their provenance to the corpus folder (<code>data/acts_raw</code> with <code>manifest.yaml</code>) and re-index from the Statute Library.</p>
        ) : (
          <>
            <p style={st.p}>
              {corpus.total_distinct_acts} act(s), {corpus.total_distinct_sections} sections, {corpus.total_chunks} indexed passages.
              Search: keyword index{corpus.dense_retrieval?.available ? ' + semantic embeddings' : ' only (no embedding model loaded)'}.
              Provenance verified for {corpus.provenance_coverage_pct}% of acts.
            </p>
            {(corpus.acts || []).map((a) => (
              <div key={a.act_name} style={st.row}>
                <div style={{ flex: 1 }}>
                  <div>{a.act_name}</div>
                  <div style={st.meta}>{a.sections_count} sections · {a.version || 'version not recorded'} · status: {a.legal_status}</div>
                </div>
                <span style={{ ...st.tag, color: a.provenance_verified ? 'var(--status-green)' : 'var(--status-amber)' }}>
                  {a.provenance_verified ? `Verified ${a.verified_at}` : 'Unverified'}
                </span>
              </div>
            ))}
          </>
        )}
      </section>

      <section style={st.section}>
        <h2 style={st.h2}>Research capabilities</h2>
        <p style={st.p}>Network mode is <strong>{mode?.mode || 'unknown'}</strong>. {mode?.mode === 'OFFLINE' ? 'Only local sources are used.' : 'Online sources are limited to the allowlist below and every call is audited.'}</p>
        {localTools.map((t) => <Tool key={t.name} tool={t} available />)}
        {onlineTools.map((t) => <Tool key={t.name} tool={t} available={false} reason={mode?.mode === 'OFFLINE' ? 'Requires ONLINE mode' : 'No live connector configured'} />)}
      </section>

      <section style={st.section}>
        <h2 style={st.h2}>External research servers</h2>
        {mcp?.active_servers?.length ? mcp.active_servers.map((s) => (
          <div key={s.name} style={st.row}>
            <div style={{ flex: 1 }}>
              <div>{s.name}</div>
              <div style={st.meta}>{s.description}</div>
              {s.error_reason && <div style={st.meta}>{s.error_reason}</div>}
            </div>
            <span style={st.tag}>{s.status}</span>
          </div>
        )) : (
          <p style={st.p}>None configured. External servers are declared by an administrator in <code>backend/app/config/mcp_servers.yaml</code>.</p>
        )}
        {mode?.allowlisted_sources?.length > 0 && (
          <p style={st.meta}>Allowlisted domains for ONLINE mode: {mode.allowlisted_sources.map((d) => d.domain).join(', ')}</p>
        )}
      </section>
    </div>
  );
}

function Tool({ tool, available, reason }) {
  return (
    <div style={st.row}>
      <div style={{ flex: 1 }}>
        <div>{tool.description}</div>
        <div style={st.meta}>{tool.category.replace(/_/g, ' ').toLowerCase()}</div>
      </div>
      <span style={{ ...st.tag, color: available ? 'var(--status-green)' : 'var(--text-muted)' }}>{available ? 'Available' : reason}</span>
    </div>
  );
}

const st = {
  page: { height: '100%', overflowY: 'auto', padding: '28px 40px 64px', maxWidth: 980 },
  section: { borderTop: '1px solid var(--border-subtle)', padding: '20px 0 12px' },
  h2: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.15rem', marginBottom: 8 },
  p: { color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6, maxWidth: 720, marginBottom: 10 },
  muted: { color: 'var(--text-muted)', fontSize: '0.85rem' },
  warn: { color: 'var(--status-amber)', fontSize: '0.85rem' },
  row: { display: 'flex', alignItems: 'center', gap: 16, padding: '10px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: '0.9rem' },
  meta: { color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: 3 },
  tag: { fontSize: '0.74rem', border: '1px solid var(--border-medium)', borderRadius: 'var(--radius-full)', padding: '2px 10px', whiteSpace: 'nowrap' },
};
