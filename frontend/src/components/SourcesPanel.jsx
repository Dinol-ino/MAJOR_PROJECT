import React from 'react';
import { BookIcon, CheckShieldIcon, ScaleIcon } from './Icons';
import ProvenancePanel from './ProvenancePanel';

export default function SourcesPanel({ sources, citations }) {
  const [showAll, setShowAll] = React.useState(false);

  if (!sources || sources.length === 0) {
    return null;
  }

  // Show what the answer actually relied on, not the whole retrieved set.
  // Retrieval fetches 5-8 chunks; an answer typically cites one or two. Listing all of
  // them presented unused statutory records as if they backed the answer.
  // Falls back to the full list when nothing parsed, so a citation-less answer still
  // shows its evidence rather than showing nothing.
  const norm = (v) => String(v || '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  const stripSection = (v) => String(v || '').replace(/^\s*(?:section|sec|s)\.?\s*(?=\d)/i, '');
  const cited = Array.isArray(citations) ? citations.filter((c) => c && c.resolved !== false) : [];

  const matchesCitation = (src) =>
    cited.some((c) => {
      const slugHit = norm(c.act_slug) && (norm(c.act_slug) === norm(src.act_slug) || norm(c.act_slug) === norm(src.act));
      const actHit = norm(c.act) && norm(c.act) === norm(src.act);
      const secHit = norm(stripSection(c.section)) && norm(stripSection(c.section)) === norm(stripSection(src.section));
      return slugHit || actHit || secHit;
    });

  const citedSources = cited.length > 0 ? sources.filter(matchesCitation) : [];
  const usingSubset = citedSources.length > 0 && citedSources.length < sources.length && !showAll;
  const visible = usingSubset ? citedSources : sources;
  const hiddenCount = sources.length - citedSources.length;

  const hasStatutes = sources.some(s => s.doc_type === 'statutory_law' || !s.doc_type || s.act?.includes('Act') || s.act?.includes('Code'));
  const hasUserDocs = sources.some(s => s.doc_type === 'user_document' || s.act?.endsWith('.pdf'));
  
  let panelTitle = 'Grounded Sources & Citations';
  if (hasStatutes && !hasUserDocs) {
    panelTitle = 'Grounded Statutory Provisions & Citations';
  } else if (!hasStatutes && hasUserDocs) {
    panelTitle = 'Referenced User Document Sources';
  }

  return (
    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
      <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', fontWeight: 700 }}>
        <BookIcon size={14} color="var(--accent-blue)" />
        <span>{panelTitle} ({visible.length})</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {visible.map((src, index) => {
          const actName = src.act || src.title || 'Source Reference';
          const hasPage = src.page_start != null;
          const pageLabel = hasPage
            ? (src.page_end != null && src.page_end !== src.page_start ? `pp. ${src.page_start}\u2013${src.page_end}` : `p. ${src.page_start}`)
            : null;
          // "Page 2" style chunk labels are locators, not statutory sections.
          const isStatutorySection = src.section && !/^(page|chunk|general)\b/i.test(String(src.section));
          const sectionNum = isStatutorySection ? `Section ${src.section}` : null;
          const trustPct = src.trust_score != null ? Math.round(src.trust_score * (src.trust_score > 1.0 ? 1 : 100)) : null;
          const simPct = src.similarity_score != null ? Math.round(src.similarity_score * (src.similarity_score > 1.0 ? 1 : 100)) : null;
          const isExternal = src.source_kind === 'external_source';
          const isUserDoc = src.source_kind
            ? src.source_kind === 'user_document'
            : (src.doc_type === 'user_document' || actName.endsWith('.pdf'));

          return (
            <div
              key={index}
              style={{
                background: 'var(--bg-app)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              {/* Card Header with Badges */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 700, color: isUserDoc ? 'var(--accent-pink)' : 'var(--accent-blue)' }}>
                    [{index + 1}] {actName}
                  </span>
                  <span style={{ fontSize: '0.65rem', background: isUserDoc ? 'rgba(255, 0, 127, 0.15)' : 'rgba(0, 132, 255, 0.15)', color: isUserDoc ? 'var(--accent-pink)' : 'var(--accent-blue)', border: `1px solid ${isUserDoc ? 'rgba(255, 0, 127, 0.3)' : 'rgba(0, 132, 255, 0.3)'}`, padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
                    {isExternal ? 'EXTERNAL SOURCE' : isUserDoc ? 'YOUR DOCUMENT' : 'STATUTE'}
                  </span>
                  {pageLabel && (
                    <span style={{ color: 'var(--text-secondary)', background: 'rgba(255, 255, 255, 0.05)', padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                      {pageLabel}
                    </span>
                  )}
                  {sectionNum && (
                    <span style={{ color: 'var(--accent-blue)', background: 'rgba(0, 132, 255, 0.1)', border: '1px solid rgba(0, 132, 255, 0.25)', padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                      {sectionNum}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {trustPct !== null && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--defense-pass)', background: 'rgba(16, 185, 129, 0.1)', padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>
                      Trust: {trustPct}%
                    </span>
                  )}
                  {simPct !== null && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', background: 'rgba(255, 255, 255, 0.05)', padding: '1px 6px', borderRadius: '4px' }}>
                      Sim: {simPct}%
                    </span>
                  )}
                </div>
              </div>

              {/* Source Text Snippet */}
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.45', margin: 0 }}>
                "{src.text}"
              </p>

              {/* Progressive Disclosure Provenance Panel */}
              <ProvenancePanel source={src} />
            </div>
          );
        })}
      </div>

      {(usingSubset || showAll) && hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setShowAll(!showAll)}
          style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer', padding: '8px 0 0',
          }}
        >
          {showAll
            ? 'Show only cited sources'
            : `Show ${hiddenCount} more retrieved but uncited source${hiddenCount === 1 ? '' : 's'}`}
        </button>
      )}
    </div>
  );
}

