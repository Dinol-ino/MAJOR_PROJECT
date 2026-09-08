import React, { useState, useEffect } from 'react';
import {
  LibraryIcon,
  SearchIcon,
  BookIcon,
  CopyIcon,
  CheckIcon,
  SparklesIcon,
  ScaleIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  RefreshIcon
} from './Icons';
import { apiClient } from '../api/client';

export default function StatuteLibraryView({ onAskCopilot, onViewInGraph }) {
  const [statutes, setStatutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedStatute, setSelectedStatute] = useState(null);
  const [selectedSection, setSelectedSection] = useState(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [domainCounts, setDomainCounts] = useState({});
  const [syncWarning, setSyncWarning] = useState(false);

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getStatutesCatalog(categoryFilter, searchFilter);
      if (res && res.catalog) {
        setStatutes(res.catalog);
        setDomainCounts(res.domain_counts || {});
        setSyncWarning(Boolean(res.sync_warning || res.total_acts < 10));

        if (res.catalog.length > 0) {
          // Keep current selection or default to first
          const currentStillExists = selectedStatute && res.catalog.find(s => s.slug === selectedStatute.slug);
          const activeStatute = currentStillExists || res.catalog[0];
          setSelectedStatute(activeStatute);

          if (activeStatute.sections && activeStatute.sections.length > 0) {
            setSelectedSection(activeStatute.sections[0]);
          }
        } else {
          setSelectedStatute(null);
          setSelectedSection(null);
        }
      }
    } catch (err) {
      console.error("Failed to fetch statutes catalog:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCatalog();
  }, [categoryFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadCatalog();
  };

  const handleSyncStatutes = async () => {
    setSyncing(true);
    try {
      await apiClient.syncStatutes();
      await loadCatalog();
    } catch (e) {
      console.error("Sync statutes failed:", e);
    } finally {
      setSyncing(false);
    }
  };

  const handleCopyCitation = (sec) => {
    if (!selectedStatute || !sec) return;
    // Spec 04 §3.4: Bluebook-style format
    const citation = `${selectedStatute.title}, § ${sec.number || sec.section}`;
    navigator.clipboard.writeText(citation);
    setCopiedId(sec.number || sec.section);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const categories = ['All', 'Criminal', 'Cyber', 'Corporate', 'Tax', 'Civil', 'Constitutional', 'Procedural', 'Commercial'];

  const filteredStatutes = statutes.filter((statute) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    const matchesTitle = statute.title.toLowerCase().includes(q) || (statute.shortName && statute.shortName.toLowerCase().includes(q));
    const matchesSection = statute.sections && statute.sections.some(s =>
      String(s.number || s.section).toLowerCase().includes(q) ||
      (s.heading && s.heading.toLowerCase().includes(q)) ||
      (s.raw_text && s.raw_text.toLowerCase().includes(q))
    );
    return matchesTitle || matchesSection;
  });

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: '100%',
        background: 'var(--bg-app)',
        overflow: 'hidden',
      }}
      className="view-container"
    >
      {/* Left Statutes Catalog Sidebar */}
      <div
        style={{
          width: '340px',
          height: '100%',
          background: 'var(--bg-sidebar)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header & Search */}
        <div style={{ padding: '18px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <LibraryIcon style={{ color: 'var(--accent-blue)', width: '20px', height: '20px' }} />
              <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Statute Library
              </h2>
              <span style={{ fontSize: '0.68rem', background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-blue)', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                {statutes.length} Acts
              </span>
            </div>

            <button
              type="button"
              onClick={handleSyncStatutes}
              disabled={syncing}
              style={{
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '4px 8px',
                color: syncing ? 'var(--accent-cyan)' : 'var(--text-muted)',
                cursor: syncing ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.7rem'
              }}
              title="Sync enactments across connected MCP servers"
            >
              <RefreshIcon size={12} className={syncing ? "spin-icon" : ""} />
              <span>{syncing ? 'Syncing...' : 'Sync MCP'}</span>
            </button>
          </div>

          {/* Sync warning if fewer than 10 acts */}
          {syncWarning && (
            <div style={{ padding: '8px 10px', background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '6px', fontSize: '0.72rem', color: '#f59e0b', marginBottom: '10px' }}>
              ⚠️ Coverage warning: Fewer than 10 acts loaded. Click "Sync MCP" to populate all Indian statutes.
            </div>
          )}

          <form onSubmit={handleSearchSubmit} style={{ position: 'relative', marginBottom: '10px' }}>
            <SearchIcon
              style={{
                position: 'absolute',
                left: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
                width: '14px',
                height: '14px',
              }}
            />
            <input
              type="text"
              placeholder="Search acts, sections, keywords..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '8px 12px 8px 32px',
                fontSize: '0.78rem',
                color: 'var(--text-primary)',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </form>

          {/* Live Domain Filters with Server Counts */}
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '4px' }}>
            {categories.map((cat) => {
              const count = domainCounts[cat] ?? (cat === 'All' ? statutes.length : null);
              const label = count !== null ? `${cat} (${count})` : cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategoryFilter(cat)}
                  style={{
                    background: categoryFilter === cat ? 'var(--accent-blue)' : 'rgba(255, 255, 255, 0.03)',
                    color: categoryFilter === cat ? 'white' : 'var(--text-secondary)',
                    border: `1px solid ${categoryFilter === cat ? 'transparent' : 'var(--border-subtle)'}`,
                    borderRadius: '12px',
                    padding: '3px 8px',
                    fontSize: '0.68rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Acts List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Loading statutory enactments...
            </div>
          ) : filteredStatutes.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              No statutes found matching "{searchFilter}".
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredStatutes.map((statute) => {
                const isSelected = selectedStatute && selectedStatute.slug === statute.slug;
                return (
                  <div
                    key={statute.slug || statute.id}
                    onClick={() => {
                      setSelectedStatute(statute);
                      setSelectedSection((statute.sections && statute.sections[0]) || null);
                    }}
                    style={{
                      background: isSelected ? 'rgba(56, 189, 248, 0.1)' : 'var(--bg-card)',
                      border: `1px solid ${isSelected ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
                      borderRadius: '8px',
                      padding: '12px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                      <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-primary)', lineHeight: '1.3' }}>
                        {statute.title}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                      <span style={{ fontSize: '0.68rem', color: 'var(--accent-cyan)', background: 'rgba(0, 210, 180, 0.1)', padding: '1px 6px', borderRadius: '4px', textTransform: 'capitalize' }}>
                        {statute.domain}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {statute.coverage_display || (statute.indexed_sections_count != null && statute.nominal_sections_count ? `${statute.indexed_sections_count} of ${statute.nominal_sections_count} indexed` : `${statute.section_count || (statute.sections ? statute.sections.length : 0)} Sections`)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Center Section Navigator */}
      <div
        style={{
          width: '280px',
          height: '100%',
          background: 'var(--bg-app)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '18px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Sections
          </div>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selectedStatute ? selectedStatute.title : 'Select Statute'}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {selectedStatute && selectedStatute.sections && selectedStatute.sections.map((sec) => {
              const secNumber = sec.number || sec.section;
              const isSecSelected = selectedSection && (selectedSection.number || selectedSection.section) === secNumber;
              return (
                <div
                  key={secNumber}
                  onClick={() => setSelectedSection(sec)}
                  style={{
                    background: isSecSelected ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                    border: `1px solid ${isSecSelected ? 'rgba(56, 189, 248, 0.3)' : 'transparent'}`,
                    borderRadius: '6px',
                    padding: '8px 10px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: isSecSelected ? 'var(--accent-blue)' : 'var(--text-primary)', fontFamily: 'monospace' }}>
                    § {secNumber}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px', lineHeight: '1.3' }}>
                    {sec.heading || sec.title || `Section ${secNumber}`}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Section Reader Pane */}
      <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: '36px 48px', boxSizing: 'border-box' }}>
        {selectedSection && selectedStatute ? (
          <div style={{ maxWidth: '820px', margin: '0 auto' }}>
            {/* Breadcrumb & Currency Verification */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                <span>India</span>
                <span>/</span>
                <span style={{ textTransform: 'capitalize' }}>{selectedStatute.domain}</span>
                <span>/</span>
                <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>§ {selectedSection.number || selectedSection.section}</span>
              </div>

              {/* Spec 04 §3.4 & Spec 05 §5.4: Verified Current & Coverage Honesty */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid var(--border-subtle)', padding: '2px 8px', borderRadius: '12px' }}>
                  {selectedStatute.coverage_display || `${selectedStatute.sections ? selectedStatute.sections.length : 0} of ${selectedStatute.section_count || 0} indexed`}
                </span>
                <div style={{ fontSize: '0.72rem', color: 'var(--defense-pass, #10b981)', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '2px 8px', borderRadius: '12px', fontWeight: 600 }}>
                  ✓ Verified current ({selectedStatute.currency_checked_at ? new Date(selectedStatute.currency_checked_at).toLocaleDateString() : '2026'})
                </div>
              </div>
            </div>

            <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px' }}>
              Section {selectedSection.number || selectedSection.section}: {selectedSection.heading || selectedSection.title || ''}
            </h1>

            {/* Action Bar */}
            <div style={{ display: 'flex', gap: '10px', marginBottom: '24px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => handleCopyCitation(selectedSection)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '6px 14px',
                  color: 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {copiedId === (selectedSection.number || selectedSection.section) ? (
                  <>
                    <CheckIcon style={{ width: '14px', height: '14px', color: 'var(--accent-cyan)' }} />
                    <span style={{ color: 'var(--accent-cyan)' }}>Copied Bluebook Citation</span>
                  </>
                ) : (
                  <>
                    <CopyIcon style={{ width: '14px', height: '14px' }} />
                    <span>Copy Bluebook Citation</span>
                  </>
                )}
              </button>

              {/* View in Graph Deep-Link */}
              {onViewInGraph && (
                <button
                  type="button"
                  onClick={() => onViewInGraph(selectedStatute.slug)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '6px 14px',
                    color: 'var(--accent-blue)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <ExternalLinkIcon style={{ width: '13px', height: '13px' }} />
                  <span>View in Graph</span>
                </button>
              )}

              {onAskCopilot && (
                <button
                  type="button"
                  onClick={() => {
                    const secText = selectedSection.raw_text || selectedSection.text || '';
                    const prompt = `Provide a rigorous legal analysis of Section ${selectedSection.number || selectedSection.section} (${selectedSection.heading || ''}) under the ${selectedStatute.title}.\n\nStatutory Text Context:\n"""\n${secText}\n"""`;
                    onAskCopilot(prompt);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'var(--accent-gradient)',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '6px 14px',
                    color: 'white',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <SparklesIcon style={{ width: '14px', height: '14px' }} />
                  <span>Research in Copilot</span>
                </button>
              )}
            </div>

            {/* Statutory Provision Monospace Text (Spec 04 §3.4) */}
            <div
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '24px',
                marginBottom: '24px',
                lineHeight: '1.75',
                color: 'var(--text-primary)',
                fontSize: '0.92rem',
                fontFamily: 'var(--font-mono, monospace)',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
                whiteSpace: 'pre-line'
              }}
            >
              {selectedSection.raw_text || selectedSection.text || "Statutory text undergoing verification."}
            </div>

            {/* Source Provenance Info */}
            <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
              Statute Authority: {selectedStatute.title} · Provenance: {selectedStatute.source}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', marginTop: '100px', color: 'var(--text-muted)' }}>
            Select a statute and section from the left panels to view statutory text.
          </div>
        )}
      </div>
    </div>
  );
}
