import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

/**
 * Security & Integrity: a compact, honest status view.
 * The hash-chained security log is verified live on the server; event rows are shown to the
 * workspace administrator only. No "100% secure" claims — just what was checked and when.
 */
export default function AuditLedgerView({ user }) {
  const [summary, setSummary] = useState(null);
  const [verify, setVerify] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showLog, setShowLog] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [s, v] = await Promise.all([apiClient.getAuditLogs('all'), apiClient.verifyAudit()]);
      setSummary(s);
      setVerify(v);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const isAdmin = user?.role === 'admin';

  return (
    <div style={st.page}>
      <section style={st.section}>
        <h2 style={st.h2}>Request protection</h2>
        <p style={st.p}>Every request is authenticated, screened for prompt injection and jailbreak attempts, restricted to Indian legal scope, answered only from your own documents and vaults, and checked against the retrieved evidence before the answer is returned. These checks run on the server and cannot be switched off from the browser.</p>
      </section>

      <section style={st.section}>
        <div style={st.head}>
          <h2 style={st.h2}>Security log integrity</h2>
          <button type="button" style={st.btn} onClick={load} disabled={loading}>{loading ? 'Checking…' : 'Verify again'}</button>
        </div>
        {error && <p style={st.warn}>{error}</p>}
        {verify && (
          <p style={{ ...st.p, color: verify.valid ? 'var(--status-green)' : 'var(--status-red)' }}>
            {verify.valid
              ? `Hash chain intact across ${verify.total_events} recorded events (checked ${new Date(verify.verified_at * 1000).toLocaleString()}).`
              : `Hash chain broken at event ${verify.broken_event_id}: ${verify.error_details}`}
          </p>
        )}
        {summary && (
          <div style={st.grid}>
            <Stat label="Recorded events" value={summary.total_count} />
            <Stat label="Chat requests" value={summary.chat_count} />
            <Stat label="Blocked or quarantined" value={summary.blocked_count} />
            <Stat label="Document uploads" value={summary.upload_count} />
            <Stat label="Research tool calls" value={summary.mcp_count} />
          </div>
        )}
      </section>

      {isAdmin && summary?.rows?.length > 0 && (
        <section style={st.section}>
          <div style={st.head}>
            <h2 style={st.h2}>Event log</h2>
            <button type="button" style={st.btn} onClick={() => setShowLog(!showLog)}>
              {showLog ? 'Hide log' : `Show ${Math.min(summary.rows.length, 100)} events`}
            </button>
          </div>
          <p style={st.p}>Administrator only. Identifiers are fingerprinted; document names and prompts are not recorded. The summary above is the normal view - per-request detail is rarely needed and is kept collapsed.</p>
          {showLog && (
          <table style={st.table}>
            <thead><tr><th style={st.th}>Time</th><th style={st.th}>Event</th><th style={st.th}>Layer</th><th style={st.th}>Result</th></tr></thead>
            <tbody>
              {summary.rows.slice(-100).reverse().map((r) => (
                <tr key={r.hash}>
                  <td style={st.td}>{new Date(r.ts).toLocaleString()}</td>
                  <td style={{ ...st.td, fontFamily: 'var(--font-mono)' }}>{r.action}</td>
                  <td style={st.td}>{r.layer || '—'}</td>
                  <td style={st.td}>{r.validation_pass_fail || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={st.stat}>
      <div style={st.statValue}>{value ?? '—'}</div>
      <div style={st.statLabel}>{label}</div>
    </div>
  );
}

const st = {
  page: { height: '100%', overflowY: 'auto', padding: '28px 40px 64px', maxWidth: 980 },
  section: { borderTop: '1px solid var(--border-subtle)', padding: '20px 0 12px' },
  head: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  h2: { fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '1.15rem', marginBottom: 8 },
  p: { color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6, maxWidth: 720, fontFamily: 'var(--font-serif)' },
  warn: { color: 'var(--status-amber)', fontSize: '0.85rem' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginTop: 14 },
  stat: { border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '12px 14px' },
  statValue: { fontFamily: 'var(--font-serif)', fontSize: '1.5rem' },
  statLabel: { color: 'var(--text-muted)', fontSize: '0.76rem', marginTop: 2 },
  btn: { background: 'transparent', border: '1px solid var(--border-medium)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', cursor: 'pointer', fontSize: '0.8rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
  th: { textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500, borderBottom: '1px solid var(--border-medium)', padding: '6px 8px' },
  td: { borderBottom: '1px solid var(--border-subtle)', padding: '6px 8px', color: 'var(--text-secondary)', verticalAlign: 'top' },
};
