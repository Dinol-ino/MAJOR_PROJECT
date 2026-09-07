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
  const containerRef = useRef(null);

  const fetchGraph = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getStatuteGraph(scope, sessionId, activeVaultId, searchQuery);
      if (res) {
        setGraphData({
          nodes: res.nodes || [],
          links: res.links || [],
          empty_state: Boolean(res.empty_state || (res.nodes && res.nodes.length === 0))
        });
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

  // Calculate coordinates
  const positionedNodes = nodes.map((node, i) => {
    if (nodes.length === 1) {
      return { ...node, x: centerX, y: centerY };
    }
    const angle = (i / nodes.length) * 2 * Math.PI;
    const radius = node.type === 'statute' ? 140 : 210;
    return {
      ...node,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  });

  const nodePosMap = new Map(positionedNodes.map(n => [n.id, n]));

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
            padding: '16px 24px',
            background: 'var(--bg-sidebar)',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            zIndex: 10
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GraphIcon style={{ color: 'var(--accent-cyan)', width: '20px', height: '20px' }} />
              <h1 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Citation Graph
              </h1>
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
                  width: '160px'
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
            /* Spec 04 §4.4: Authentic Empty State */
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
                Ask a legal question in Legal Copilot to automatically extract and grow your live citation graph.
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
              {/* Edges */}
              {links.map((link, idx) => {
                const src = nodePosMap.get(link.source);
                const dst = nodePosMap.get(link.target);
                if (!src || !dst) return null;

                const midX = (src.x + dst.x) / 2;
                const midY = (src.y + dst.y) / 2;

                return (
                  <g key={`edge-${idx}`}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={dst.x}
                      y2={dst.y}
                      stroke="rgba(255, 255, 255, 0.18)"
                      strokeWidth="1.5"
                      strokeDasharray={link.origin === 'mcp_relation' ? '4 2' : 'none'}
                    />
                    {/* Real relation label from DB (Spec 04 §4.4) */}
                    <text
                      x={midX}
                      y={midY - 4}
                      fill="var(--text-muted)"
                      fontSize="9"
                      textAnchor="middle"
                      style={{ userSelect: 'none' }}
                    >
                      {link.relation}
                    </text>
                  </g>
                );
              })}

              {/* Nodes */}
              {positionedNodes.map((node) => {
                const isSelected = selectedNode && selectedNode.id === node.id;
                const r = node.type === 'statute' ? 24 : 18;

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
          width: '320px',
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
              <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {selectedNode.category || selectedNode.type || 'Legal Entity'}
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
                  boxShadow: 'var(--shadow-sm)'
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
