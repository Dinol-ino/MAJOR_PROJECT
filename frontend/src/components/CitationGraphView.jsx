import React, { useState, useRef, useEffect } from 'react';
import {
  GraphIcon,
  SearchIcon,
  FilterIcon,
  ClearIcon,
  ZoomInIcon,
  ZoomOutIcon,
  ResetIcon,
  BookIcon,
  SparklesIcon,
  ScaleIcon,
  DownloadIcon,
  CheckCircleIcon,
  ChevronRightIcon
} from './Icons';
import { apiClient } from '../api/client';

export default function CitationGraphView({ onAskCopilot, sessionId, activeVaultId }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState('conversation'); // conversation | vault | global
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [backendInfo, setBackendInfo] = useState({ backend: 'in_process_sqlite', tier: 0 });
  const containerRef = useRef(null);

  const seedPills = [
    { label: '+ IT Act Sec 66', query: '66', act: 'it_act_2000' },
    { label: '+ Companies Act Sec 166', query: '166', act: 'companies_act_2013' },
    { label: '+ Shreya Singhal', query: 'Shreya Singhal', act: 'it_act_2000' },
    { label: '+ Contract Sec 73', query: '73', act: 'contract_act_1872' },
  ];

  const fetchGraph = async (forcedQuery = null) => {
    setLoading(true);
    const q = forcedQuery !== null ? forcedQuery : searchQuery;
    try {
      const res = await apiClient.getStatuteGraph(scope, sessionId, activeVaultId, q);
      if (res) {
        setGraphData({
          nodes: res.nodes || [],
          links: res.links || [],
          empty_state: Boolean(res.empty_state || (res.nodes && res.nodes.length === 0))
        });
        if (res.backend_used) {
          setBackendInfo({
            backend: res.backend_used,
            tier: res.hardware_tier ?? 0
          });
        }
        if (res.nodes && res.nodes.length > 0) {
          setSelectedNode(res.nodes[0]);
        } else {
          setSelectedNode(null);
        }
      }
    } catch (err) {
      console.warn("Could not fetch real dynamic citation graph:", err);
      setGraphData({ nodes: [], links: [], empty_state: true });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [scope, sessionId, activeVaultId]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchGraph();
  };

  const handleSeedClick = (pill) => {
    setSearchQuery(pill.query);
    setScope('global');
    fetchGraph(pill.query);
  };

  const handleZoom = (delta) => {
    setZoomLevel((prev) => Math.min(Math.max(0.4, prev + delta), 2.5));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  // Dragging / panning
  const handleMouseDown = (e) => {
    if (e.target.tagName === 'circle' || e.target.tagName === 'text') return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPanOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  // Compute node positions on circle / force layout
  const nodes = graphData.nodes || [];
  const links = graphData.links || [];

  const width = 800;
  const height = 550;
  const centerX = width / 2;
  const centerY = height / 2;

  // Calculate coordinates with scaling
  const positionedNodes = nodes.map((node, i) => {
    if (nodes.length === 1) {
      return { ...node, x: centerX, y: centerY };
    }
    const angle = (i / nodes.length) * 2 * Math.PI;
    const radius = node.type === 'statute' ? 130 : (node.type === 'precedent' ? 220 : 180);
    return {
      ...node,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  });

  const nodePosMap = new Map(positionedNodes.map(n => [n.id, n]));

  // Connected edges for the selected node
  const connectedEdges = selectedNode ? links.filter(l => l.source === selectedNode.id || l.target === selectedNode.id) : [];

  const getDerivationTag = (deriv) => {
    switch (deriv) {
      case 'corpus_structure':
        return { label: 'Corpus Structure', bg: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8' };
      case 'text_extraction':
        return { label: 'Text Extraction (Penalty)', bg: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b' };
      case 'curated_legal_relationship':
        return { label: 'Curated Legal Relation', bg: 'rgba(0, 210, 180, 0.12)', color: '#00d2b4' };
      case 'mcp_case_law_lookup':
        return { label: 'MCP Precedent Lookup', bg: 'rgba(168, 85, 247, 0.12)', color: '#a855f7' };
      case 'llm_suggested_unverified':
        return { label: 'AI Suggested — Unverified', bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' };
      case 'user_document_reference':
        return { label: 'User Matter Document', bg: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' };
      default:
        return { label: deriv || 'Mechanical', bg: 'rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)' };
    }
  };

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
      {/* Left Canvas Area */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        {/* Top Control Bar */}
        <div
          style={{
            padding: '14px 24px',
            background: 'var(--bg-sidebar)',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            zIndex: 10,
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GraphIcon style={{ color: 'var(--accent-cyan)', width: '20px', height: '20px' }} />
              <h1 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Citation Graph
              </h1>
              {/* Backend indicator pill */}
              <span
                style={{
                  fontSize: '0.66rem',
                  background: backendInfo.backend === 'memgraph' ? 'rgba(0, 210, 180, 0.12)' : 'rgba(56, 189, 248, 0.12)',
                  color: backendInfo.backend === 'memgraph' ? '#00d2b4' : '#38bdf8',
                  border: `1px solid ${backendInfo.backend === 'memgraph' ? 'rgba(0, 210, 180, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`,
                  padding: '2px 7px',
                  borderRadius: '12px',
                  fontWeight: 600
                }}
                title={backendInfo.backend === 'memgraph' ? 'Memgraph Community Edition Cypher Engine' : 'In-Process DB Fallback Engine'}
              >
                {backendInfo.backend === 'memgraph' ? '⚡ Memgraph (Cypher)' : 'In-Process DB'}
              </span>
            </div>

            {/* Scope Segmented Control (Spec 04 §4.4) */}
            <div style={{ display: 'flex', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '2px' }}>
              <button
                type="button"
                onClick={() => setScope('conversation')}
                style={{
                  background: scope === 'conversation' ? 'var(--accent-gradient)' : 'transparent',
                  color: scope === 'conversation' ? 'white' : 'var(--text-secondary)',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Current Session
              </button>
              <button
                type="button"
                onClick={() => setScope('vault')}
                style={{
                  background: scope === 'vault' ? 'var(--accent-gradient)' : 'transparent',
                  color: scope === 'vault' ? 'white' : 'var(--text-secondary)',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Project Vault
              </button>
              <button
                type="button"
                onClick={() => setScope('global')}
                style={{
                  background: scope === 'global' ? 'var(--accent-gradient)' : 'transparent',
                  color: scope === 'global' ? 'white' : 'var(--text-secondary)',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Global Statutory Cross-Walk
              </button>
            </div>
          </div>

          {/* Right Search & Zoom Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <form onSubmit={handleSearchSubmit} style={{ position: 'relative' }}>
              <SearchIcon
                style={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                  width: '13px',
                  height: '13px',
                }}
              />
              <input
                type="text"
                placeholder="Filter graph..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '6px 10px 6px 30px',
                  fontSize: '0.76rem',
                  color: 'var(--text-primary)',
                  outline: 'none',
                  width: '150px'
                }}
              />
            </form>

            <button
              type="button"
              onClick={() => handleZoom(0.15)}
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '6px', color: 'var(--text-secondary)', cursor: 'pointer' }}
              title="Zoom In"
            >
              <ZoomInIcon size={14} />
            </button>
            <button
              type="button"
              onClick={() => handleZoom(-0.15)}
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '6px', color: 'var(--text-secondary)', cursor: 'pointer' }}
              title="Zoom Out"
            >
              <ZoomOutIcon size={14} />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '6px', color: 'var(--text-secondary)', cursor: 'pointer' }}
              title="Reset View"
            >
              <ResetIcon size={14} />
            </button>
          </div>
        </div>

        {/* Quick-Seed Shortcut Pills (Spec 05 §5.1) */}
        <div style={{ padding: '8px 24px', background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>
            Seed Shortcuts:
          </span>
          {seedPills.map((pill, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSeedClick(pill)}
              style={{
                background: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '12px',
                padding: '3px 10px',
                color: 'var(--accent-cyan)',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease'
              }}
            >
              {pill.label}
            </button>
          ))}
        </div>

        {/* SVG Interactive Canvas */}
        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          style={{
            flex: 1,
            position: 'relative',
            cursor: isDragging ? 'grabbing' : 'grab',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          {loading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              Computing dynamic citation topology...
            </div>
          ) : positionedNodes.length === 0 ? (
            /* Authentic Empty State */
            <div
              style={{
                textAlign: 'center',
                maxWidth: '420px',
                padding: '40px 24px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '16px',
                boxShadow: 'var(--shadow-md)'
              }}
            >
              <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(56, 189, 248, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                <GraphIcon size={22} color="var(--accent-cyan)" />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
                No Citations in {scope === 'conversation' ? 'This Session' : scope === 'vault' ? 'This Vault' : 'Network'}
              </h3>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '20px' }}>
                Ask a legal question in Legal Copilot or click any Seed Shortcut above to load live statutory relationships.
              </p>
              {onAskCopilot && (
                <button
                  type="button"
                  onClick={() => onAskCopilot("What are the key penalties and provisions under Section 66 of the IT Act, 2000?")}
                  style={{
                    background: 'var(--accent-gradient)',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '8px 18px',
                    color: 'white',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <SparklesIcon size={14} />
                  <span>Go to Legal Copilot</span>
                </button>
              )}
            </div>
          ) : (
            <svg
              width="100%"
              height="100%"
              viewBox={`0 0 ${width} ${height}`}
              style={{
                transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
                transformOrigin: 'center center',
                transition: isDragging ? 'none' : 'transform 0.1s ease-out'
              }}
            >
              {/* Edges with Derivation Method Styling */}
              {links.map((link, idx) => {
                const src = nodePosMap.get(link.source);
                const dst = nodePosMap.get(link.target);
                if (!src || !dst) return null;

                const midX = (src.x + dst.x) / 2;
                const midY = (src.y + dst.y) / 2;

                const isUnverified = link.is_unverified || link.derivation_method === 'llm_suggested_unverified';
                const isUserDoc = link.is_user_document || link.derivation_method === 'user_document_reference';
                const isPenalty = link.derivation_method === 'text_extraction' || link.relation === 'penalizes_with';
                const isPrecedent = link.derivation_method === 'mcp_case_law_lookup' || link.relation === 'judicially_construed_in';

                let strokeColor = 'rgba(255, 255, 255, 0.2)';
                let strokeDash = 'none';

                if (isUnverified) {
                  strokeColor = '#ef4444';
                  strokeDash = '3 3';
                } else if (isUserDoc) {
                  strokeColor = '#818cf8';
                  strokeDash = '6 3';
                } else if (isPenalty) {
                  strokeColor = '#f59e0b';
                } else if (isPrecedent) {
                  strokeColor = '#a855f7';
                } else if (link.relation === 'requires_violation_of' || link.relation === 'cross_applies') {
                  strokeColor = '#00d2b4';
                }

                return (
                  <g key={`edge-${idx}`}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={dst.x}
                      y2={dst.y}
                      stroke={strokeColor}
                      strokeWidth={isUnverified ? 2 : 1.5}
                      strokeDasharray={strokeDash}
                    />
                    <text
                      x={midX}
                      y={midY - 4}
                      fill={isUnverified ? '#ef4444' : 'var(--text-muted)'}
                      fontSize="9"
                      fontWeight={isUnverified ? 700 : 500}
                      textAnchor="middle"
                      style={{ userSelect: 'none' }}
                    >
                      {link.relation}
                      {isUnverified && ' (Unverified)'}
                    </text>
                  </g>
                );
              })}

              {/* Nodes */}
              {positionedNodes.map((node) => {
                const isSelected = selectedNode && selectedNode.id === node.id;
                const baseR = node.type === 'statute' ? 24 : (node.type === 'penalty' ? 14 : 18);
                const sizeBonus = node.cited_in_conversations ? Math.min(node.cited_in_conversations * 2, 8) : 0;
                const r = baseR + sizeBonus;

                return (
                  <g
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={isSelected ? r + 5 : r}
                      fill={node.color || '#38bdf8'}
                      fillOpacity={isSelected ? 0.35 : 0.2}
                      stroke={node.color || '#38bdf8'}
                      strokeWidth={isSelected ? 3 : 1.5}
                      style={{ transition: 'all 0.2s ease' }}
                    />
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={r * 0.4}
                      fill={node.color || '#38bdf8'}
                    />
                    <text
                      x={node.x}
                      y={node.y + r + 14}
                      fill="var(--text-primary)"
                      fontSize="11"
                      fontWeight={isSelected ? 700 : 500}
                      textAnchor="middle"
                      style={{ userSelect: 'none' }}
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>

      {/* Right Node Detail Side Panel */}
      <div
        style={{
          width: '340px',
          height: '100%',
          background: 'var(--bg-sidebar)',
          borderLeft: '1px solid var(--border-subtle)',
          padding: '24px 20px',
          boxSizing: 'border-box',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}
      >
        {selectedNode ? (
          <>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {selectedNode.category || selectedNode.type || 'Legal Entity'}
                </div>
                {selectedNode.cited_in_conversations > 0 && (
                  <span style={{ fontSize: '0.68rem', background: 'rgba(0, 210, 180, 0.12)', color: 'var(--accent-cyan)', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                    Cited {selectedNode.cited_in_conversations}× in Chat
                  </span>
                )}
              </div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', margin: '4px 0 8px' }}>
                {selectedNode.label}
              </h2>
            </div>

            {selectedNode.desc && (
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '14px', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                {selectedNode.desc}
              </div>
            )}

            {/* Connected Statutory Relationships with Provenance Tags (Spec 05 §5.2.2) */}
            {connectedEdges.length > 0 && (
              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
                  Connected Relationships ({connectedEdges.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {connectedEdges.map((edge, i) => {
                    const otherKey = edge.source === selectedNode.id ? edge.target : edge.source;
                    const isOutgoing = edge.source === selectedNode.id;
                    const tag = getDerivationTag(edge.derivation_method);

                    return (
                      <div
                        key={i}
                        style={{
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '6px',
                          padding: '8px 10px',
                          fontSize: '0.75rem'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {isOutgoing ? `→ ${edge.relation}` : `← ${edge.relation}`}
                          </span>
                          <span
                            style={{
                              fontSize: '0.64rem',
                              background: tag.bg,
                              color: tag.color,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontWeight: 600
                            }}
                          >
                            {tag.label}
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', wordBreak: 'break-all' }}>
                          Target: {otherKey}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Ask Copilot About Node (Spec 04 §4.4) */}
            {onAskCopilot && (
              <button
                type="button"
                onClick={() => onAskCopilot(`Provide a rigorous legal analysis of ${selectedNode.label} including applicable statutory standards and recent case law interpretations.`)}
                style={{
                  background: 'var(--accent-gradient)',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  color: 'white',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: 'var(--shadow-sm)',
                  marginTop: 'auto'
                }}
              >
                <SparklesIcon size={14} />
                <span>Ask Copilot About This Node</span>
              </button>
            )}

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Node ID: <code>{selectedNode.id}</code>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: '60px' }}>
            Click any node in the citation graph to inspect statutory relations.
          </div>
        )}
      </div>
    </div>
  );
}
