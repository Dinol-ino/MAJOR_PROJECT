import React, { useState } from 'react';
import { ChevronDownIcon } from './Icons';

/**
 * Provenance for a single retrieved source.
 *
 * Shows ONLY fields the backend actually returned. Every value here previously had a
 * plausible-looking fallback, which meant the panel asserted things the system did not
 * know:
 *   - document_version fell back to a literal "v2024.1"
 *   - status was rendered "Active Settled Law" for anything not explicitly superseded,
 *     while the corpus itself reports legal_status "unverified"
 *   - content_hash, when absent, was manufactured by hex-encoding the first 32
 *     characters of the chunk text and prefixing "sha256:" - a fabricated fingerprint
 *     presented as a cryptographic one
 *
 * A field with no value is now omitted. If nothing is known, the panel says so.
 */
export default function ProvenancePanel({ source }) {
  const [expanded, setExpanded] = useState(false);

  const rows = [];
  const push = (label, value, opts = {}) => {
    if (value === null || value === undefined || value === '') return;
    rows.push({ label, value, ...opts });
  };

  push('Jurisdiction', source.jurisdiction);
  push('Publication date', source.publication_date || source.effective_date);
  push('Version', source.document_version || source.source_version);
  push('Retrieval', source.retrieval_method, { mono: true });

  // Verification status comes from the backend, never from an assumption.
  const legalStatus = source.legal_status;
  const isSuperseded = source.is_superseded === true || source.superseded === true;
  let statusLabel = null;
  let statusTone = 'neutral';
  if (isSuperseded) {
    statusLabel = 'Superseded / amended';
    statusTone = 'bad';
  } else if (legalStatus === 'verified') {
    statusLabel = 'Verified against source';
    statusTone = 'good';
  } else if (legalStatus) {
    // e.g. "unverified" - shown honestly rather than dressed up as settled law
    statusLabel = String(legalStatus).replace(/_/g, ' ');
    statusTone = 'warn';
  }

  // Only a hash the backend computed. Never derived from the text here.
  const contentHash = source.content_hash || null;
  const sourceUrl = source.source_url || null;
  const hasAnything = rows.length > 0 || statusLabel || contentHash || sourceUrl;

  const toneColor = {
    good: 'var(--defense-pass)',
    bad: 'var(--defense-block)',
    warn: 'var(--accent-amber, #f59e0b)',
    neutral: 'var(--text-secondary)',
  }[statusTone];
  const toneBg = {
    good: 'rgba(16, 185, 129, 0.1)',
    bad: 'rgba(239, 68, 68, 0.1)',
    warn: 'rgba(245, 158, 11, 0.12)',
    neutral: 'rgba(255, 255, 255, 0.05)',
  }[statusTone];

  return (
    <div style={{ marginTop: '8px' }}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        style={{
          background: 'none',
          border: 'none',
          color: expanded ? 'var(--accent-cyan)' : 'var(--text-muted)',
          fontSize: '0.72rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          cursor: 'pointer',
          padding: '2px 0',
          transition: 'color 0.15s ease',
        }}
      >
        <span style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease', display: 'inline-flex' }}>
          <ChevronDownIcon size={12} />
        </span>
        <span>{expanded ? 'Hide provenance' : 'Show provenance'}</span>
      </button>

      {expanded && (
        <div
          style={{
            marginTop: '8px',
            padding: '10px 12px',
            background: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '6px',
            fontSize: '0.73rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '8px 16px',
            color: 'var(--text-secondary)',
          }}
        >
          {!hasAnything && (
            <div style={{ gridColumn: 'span 2', color: 'var(--text-muted)' }}>
              No provenance metadata recorded for this source.
            </div>
          )}

          {statusLabel && (
            <div>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Status: </span>
              <span style={{ color: toneColor, fontWeight: 700, background: toneBg, padding: '1px 6px', borderRadius: '4px', textTransform: 'capitalize' }}>
                {statusLabel}
              </span>
            </div>
          )}

          {rows.map((r) => (
            <div key={r.label}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{r.label}: </span>
              <span
                style={{
                  color: r.mono ? 'var(--accent-blue)' : 'var(--text-primary)',
                  fontFamily: r.mono ? 'monospace' : 'inherit',
                  fontSize: r.mono ? '0.7rem' : 'inherit',
                }}
              >
                {r.value}
              </span>
            </div>
          ))}

          {contentHash && (
            <div style={{ gridColumn: 'span 2', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Content hash: </span>
              <span style={{ fontFamily: 'monospace', color: 'var(--accent-cyan)', fontSize: '0.68rem', background: 'rgba(56, 189, 248, 0.08)', padding: '1px 6px', borderRadius: '4px' }}>
                {contentHash}
              </span>
            </div>
          )}

          {sourceUrl && (
            <div style={{ gridColumn: 'span 2' }}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Source: </span>
              <a href={sourceUrl} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent-blue)', fontSize: '0.7rem', wordBreak: 'break-all' }}>
                {sourceUrl}
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
