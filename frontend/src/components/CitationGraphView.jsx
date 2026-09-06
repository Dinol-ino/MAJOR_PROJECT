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

// Comprehensive Statutory Graph Nodes & Edges dataset
const INITIAL_GRAPH_DATA = {
  nodes: [
    { id: 'act_it', label: 'IT Act 2000', type: 'act', color: '#38bdf8', category: 'Cyber Law', desc: 'Information Technology Act, 2000 governs electronic commerce, cybercrimes, and digital signatures.' },
    { id: 'sec_66', label: 'Section 66', type: 'section', color: '#00d2b4', act: 'IT Act 2000', title: 'Computer Related Offences', desc: 'If any person, dishonestly or fraudulently, does any act referred to in section 43, he shall be punishable.' },
    { id: 'sec_43', label: 'Section 43', type: 'section', color: '#00d2b4', act: 'IT Act 2000', title: 'Penalty for Damage to Computer', desc: 'Penalty and compensation for damage to computer systems, data theft, and unauthorized access.' },
    { id: 'sec_66b', label: 'Section 66B', type: 'section', color: '#00d2b4', act: 'IT Act 2000', title: 'Stolen Computer Resource', desc: 'Punishment for dishonestly receiving stolen computer resource or communication device.' },
    { id: 'pen_66', label: '3 Yrs Jail / ₹5L Fine', type: 'penalty', color: '#f59e0b', desc: 'Maximum statutory criminal penalty under IT Act Section 66.' },
    { id: 'prec_shreya', label: 'Shreya Singhal v. UOI (2015)', type: 'precedent', color: '#a855f7', desc: 'Supreme Court landmark ruling establishing constitutional boundaries on online free speech under Section 66A.' },

    { id: 'act_ca', label: 'Companies Act 2013', type: 'act', color: '#38bdf8', category: 'Corporate Law', desc: 'Comprehensive statute regulating incorporation, responsibilities of directors, auditing, and corporate governance.' },
    { id: 'sec_134', label: 'Section 134', type: 'section', color: '#00d2b4', act: 'Companies Act 2013', title: 'Financial Statements & Board Report', desc: 'Board responsibilities to certify internal financial controls and risk management policy.' },
    { id: 'sec_166', label: 'Section 166', type: 'section', color: '#00d2b4', act: 'Companies Act 2013', title: 'Duties of Directors', desc: 'Fiduciary duties of directors to act in good faith and avoid conflicts of interest.' },
    { id: 'pen_ca', label: 'Director Disqualification', type: 'penalty', color: '#f59e0b', desc: 'Statutory disqualification under Sec 164 and liability under Sec 447 for corporate fraud.' },

    { id: 'act_bns', label: 'Bharatiya Nyaya Sanhita 2023', type: 'act', color: '#38bdf8', category: 'Criminal Code', desc: 'Replaced Indian Penal Code 1860; primary substantive criminal statute of India.' },
    { id: 'sec_bns_318', label: 'Section 318 (Old 420)', type: 'section', color: '#00d2b4', act: 'BNS 2023', title: 'Cheating & Dishonesty', desc: 'Cheating and dishonestly inducing delivery of property or alteration of valuable security.' },

    { id: 'act_contract', label: 'Indian Contract Act 1872', type: 'act', color: '#38bdf8', category: 'Commercial Law', desc: 'Fundamental legislation governing contracts, consideration, breach of obligations, and indemnities.' },
    { id: 'sec_73', label: 'Section 73', type: 'section', color: '#00d2b4', act: 'Contract Act 1872', title: 'Compensation for Breach', desc: 'Compensation for loss or damage caused by breach of contract arising naturally from breach.' },
    { id: 'doc_user', label: 'Active Session Uploads', type: 'document', color: '#10b981', desc: 'User uploaded PDF agreements, master services agreements, or statutory filings indexed in Tier 2.' },
  ],
  links: [
    { source: 'act_it', target: 'sec_66', relation: 'Contains' },
    { source: 'act_it', target: 'sec_43', relation: 'Contains' },
    { source: 'act_it', target: 'sec_66b', relation: 'Contains' },
    { source: 'sec_66', target: 'sec_43', relation: 'Requires Violation of' },
    { source: 'sec_66', target: 'pen_66', relation: 'Penalizes With' },
    { source: 'sec_66', target: 'prec_shreya', relation: 'Judicially Construed In' },
    { source: 'sec_66', target: 'sec_bns_318', relation: 'Cross-Applies Criminal Intent' },

    { source: 'act_ca', target: 'sec_134', relation: 'Contains' },
    { source: 'act_ca', target: 'sec_166', relation: 'Contains' },
    { source: 'sec_166', target: 'pen_ca', relation: 'Sanctions With' },
    { source: 'sec_134', target: 'doc_user', relation: 'Validates Corporate Governance' },

    { id: 'bns_rel', source: 'act_bns', target: 'sec_bns_318', relation: 'Contains' },
    { source: 'sec_bns_318', target: 'sec_73', relation: 'Civil vs Criminal Remit' },

    { source: 'act_contract', target: 'sec_73', relation: 'Contains' },
    { source: 'sec_73', target: 'doc_user', relation: 'Governs Indemnity in' },
  ]
};

export default function CitationGraphView({ onAskCopilot }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState(INITIAL_GRAPH_DATA.nodes[1]); // Default Section 66
  const [filterType, setFilterType] = useState('all'); // all | act | section | penalty | precedent
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Filtered nodes
  const filteredNodes = INITIAL_GRAPH_DATA.nodes.filter((n) => {
    const matchesFilter = filterType === 'all' || n.type === filterType;
    const matchesSearch = !searchQuery.trim() || 
      n.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (n.title && n.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (n.desc && n.desc.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  const nodeMap = new Map(filteredNodes.map((n) => [n.id, n]));

  const filteredLinks = INITIAL_GRAPH_DATA.links.filter(
    (l) => nodeMap.has(l.source) && nodeMap.has(l.target)
  );

  // Layout node positions on virtual canvas (circular/clustered distribution)
  const getNodePos = (node, index, total) => {
    // Custom fixed coordinates for clean aesthetic layout
    const positions = {
      act_it: { x: 280, y: 220 },
      sec_66: { x: 440, y: 160 },
      sec_43: { x: 440, y: 280 },
      sec_66b: { x: 440, y: 380 },
      pen_66: { x: 620, y: 140 },
      prec_shreya: { x: 620, y: 220 },

      act_ca: { x: 280, y: 520 },
      sec_134: { x: 440, y: 480 },
      sec_166: { x: 440, y: 580 },
      pen_ca: { x: 620, y: 580 },

      act_bns: { x: 280, y: 360 },
      sec_bns_318: { x: 620, y: 340 },

      act_contract: { x: 280, y: 700 },
      sec_73: { x: 480, y: 700 },
      doc_user: { x: 700, y: 520 },
    };

    if (positions[node.id]) {
      return positions[node.id];
    }
    const angle = (index / total) * 2 * Math.PI;
    const radius = 240;
    return {
      x: 450 + radius * Math.cos(angle),
      y: 350 + radius * Math.sin(angle),
    };
  };

  const handleMouseDown = (e) => {
    if (e.target.tagName === 'svg' || e.target.id === 'graph-canvas') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPanOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  const handleSeedSelect = (seedText) => {
    setSearchQuery(seedText);
  };

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: '100%',
        background: 'var(--bg-app)',
        overflow: 'hidden',
        position: 'relative',
      }}
      className="view-container"
    >
      {/* Main Graph Exploration Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* Consensus-style Graph Search Header */}
        <div
          style={{
            padding: '24px 32px 16px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-sidebar)',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(0, 210, 180, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <GraphIcon size={18} color="var(--accent-cyan)" />
              </div>
              <div>
                <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  Statutory Citation Graph
                  <span style={{ fontSize: '0.65rem', background: 'rgba(0, 210, 180, 0.15)', color: 'var(--accent-cyan)', padding: '2px 8px', borderRadius: '12px', fontWeight: 700, letterSpacing: '0.05em' }}>
                    BETA
                  </span>
                </h1>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Interactive relationship graph mapping statutory dependencies, criminal penalties, judicial precedents & user evidence.
                </p>
              </div>
            </div>

            {/* Quick Canvas Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.min(z + 0.2, 2.5))}
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', width: 32, height: 32, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                title="Zoom In"
              >
                <ZoomInIcon size={16} />
              </button>
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.max(z - 0.2, 0.5))}
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', width: 32, height: 32, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                title="Zoom Out"
              >
                <ZoomOutIcon size={16} />
              </button>
              <button
                type="button"
                onClick={handleResetZoom}
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '6px', width: 32, height: 32, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                title="Reset View"
              >
                <ResetIcon size={16} />
              </button>
            </div>
          </div>

          {/* Search & Seed Bar */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <div
              style={{
                flex: 1,
                background: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: '24px',
                padding: '8px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <SearchIcon size={16} color="var(--text-muted)" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Start by searching for seed statutes or acts (e.g. Section 66, Director Duties, Shreya Singhal)..."
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--text-primary)',
                  fontSize: '0.9rem',
                }}
              />
              {searchQuery && (
                <button type="button" onClick={() => setSearchQuery('')} style={{ background: 'none', border: 'none', color: 'var(--text-muted)' }}>
                  ✕
                </button>
              )}
            </div>

            {/* Filter Pill Dropdown */}
            <div style={{ display: 'flex', gap: '6px' }}>
              {['all', 'act', 'section', 'penalty', 'precedent'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setFilterType(t)}
                  style={{
                    background: filterType === t ? 'rgba(0, 210, 180, 0.15)' : 'var(--bg-card)',
                    border: `1px solid ${filterType === t ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                    color: filterType === t ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    borderRadius: '16px',
                    padding: '6px 12px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'capitalize',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Seed Statute Chips */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Seed Statutes:
            </span>
            {['IT Act Sec 66', 'Companies Act Sec 166', 'Shreya Singhal', 'Contract Sec 73'].map((seed) => (
              <button
                key={seed}
                type="button"
                onClick={() => handleSeedSelect(seed)}
                style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '12px',
                  padding: '3px 10px',
                  fontSize: '0.74rem',
                  color: 'var(--text-secondary)',
                }}
              >
                + {seed}
              </button>
            ))}
          </div>
        </div>

        {/* SVG Canvas */}
        <div
          id="graph-canvas"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          style={{
            flex: 1,
            position: 'relative',
            cursor: isDragging ? 'grabbing' : 'grab',
            overflow: 'hidden',
            background: 'radial-gradient(circle at center, #151824 0%, #0d0f14 100%)',
          }}
        >
          <svg
            width="100%"
            height="100%"
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
              transformOrigin: 'center center',
              transition: isDragging ? 'none' : 'transform 0.1s ease-out',
            }}
          >
            <defs>
              <marker id="arrowhead" markerWidth="7" markerHeight="7" refX="16" refY="3.5" orient="auto">
                <polygon points="0 0, 7 3.5, 0 7" fill="rgba(255,255,255,0.25)" />
              </marker>
            </defs>

            {/* Links / Edges */}
            {filteredLinks.map((link, idx) => {
              const srcNode = nodeMap.get(link.source);
              const tgtNode = nodeMap.get(link.target);
              if (!srcNode || !tgtNode) return null;

              const srcPos = getNodePos(srcNode, 0, filteredNodes.length);
              const tgtPos = getNodePos(tgtNode, 0, filteredNodes.length);

              const isConnected = selectedNode && (selectedNode.id === link.source || selectedNode.id === link.target);

              return (
                <g key={idx}>
                  <line
                    x1={srcPos.x}
                    y1={srcPos.y}
                    x2={tgtPos.x}
                    y2={tgtPos.y}
                    stroke={isConnected ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.15)'}
                    strokeWidth={isConnected ? 2 : 1}
                    strokeDasharray={link.relation.includes('Penal') ? '4,4' : 'none'}
                    markerEnd="url(#arrowhead)"
                  />
                  {/* Edge Label */}
                  <text
                    x={(srcPos.x + tgtPos.x) / 2}
                    y={(srcPos.y + tgtPos.y) / 2 - 4}
                    fill={isConnected ? 'var(--accent-cyan)' : '#64748b'}
                    fontSize="9px"
                    textAnchor="middle"
                    fontWeight="500"
                  >
                    {link.relation}
                  </text>
                </g>
              );
            })}

            {/* Nodes */}
            {filteredNodes.map((node, index) => {
              const pos = getNodePos(node, index, filteredNodes.length);
              const isSelected = selectedNode && selectedNode.id === node.id;

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onClick={() => setSelectedNode(node)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Selection Ring */}
                  {isSelected && (
                    <circle
                      r="32"
                      fill="none"
                      stroke={node.color}
                      strokeWidth="2"
                      strokeDasharray="4,4"
                      opacity="0.8"
                    />
                  )}

                  {/* Main Node Bubble */}
                  <circle
                    r={node.type === 'act' ? 26 : 22}
                    fill="var(--bg-card)"
                    stroke={node.color}
                    strokeWidth={isSelected ? 3 : 1.5}
                    style={{
                      filter: isSelected ? `drop-shadow(0 0 12px ${node.color}66)` : 'none',
                      transition: 'all 0.2s ease',
                    }}
                  />

                  {/* Node Icon/Label */}
                  <text
                    textAnchor="middle"
                    dy="4"
                    fill="var(--text-primary)"
                    fontSize={node.type === 'act' ? '10px' : '9px'}
                    fontWeight="700"
                    pointerEvents="none"
                  >
                    {node.label.length > 14 ? node.label.substring(0, 12) + '..' : node.label}
                  </text>

                  {/* Secondary Type Pill */}
                  <text
                    textAnchor="middle"
                    dy="36"
                    fill="#94a3b8"
                    fontSize="8px"
                    fontWeight="600"
                    textTransform="uppercase"
                  >
                    {node.type}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Right-Side Node Details Inspector Drawer */}
      {selectedNode && (
        <div
          style={{
            width: '360px',
            height: '100%',
            background: 'var(--bg-sidebar)',
            borderLeft: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            padding: '24px',
            boxSizing: 'border-box',
            overflowY: 'auto',
            zIndex: 20,
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                color: selectedNode.color,
                background: `${selectedNode.color}1a`,
                padding: '3px 10px',
                borderRadius: '12px',
              }}
            >
              {selectedNode.type} Node
            </span>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.1rem' }}
            >
              ✕
            </button>
          </div>

          <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {selectedNode.label}
          </h2>

          {selectedNode.title && (
            <div style={{ fontSize: '0.88rem', color: 'var(--accent-blue)', fontWeight: 600, marginBottom: '12px' }}>
              {selectedNode.title}
            </div>
          )}

          {selectedNode.act && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <BookIcon size={14} color="var(--accent-cyan)" />
              <span>Parent Statute: <strong>{selectedNode.act}</strong></span>
            </div>
          )}

          {/* Description / Legal Text */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '14px', marginBottom: '20px' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '6px' }}>
              Statutory Provision / Meaning
            </div>
            <p style={{ fontSize: '0.85rem', lineHeight: '1.55', color: 'var(--text-primary)' }}>
              {selectedNode.desc}
            </p>
          </div>

          {/* Connected Entities in Knowledge Graph */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '10px' }}>
              Connected Statutory Relationships
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {INITIAL_GRAPH_DATA.links
                .filter((l) => l.source === selectedNode.id || l.target === selectedNode.id)
                .map((link, i) => {
                  const otherId = link.source === selectedNode.id ? link.target : link.source;
                  const otherNode = INITIAL_GRAPH_DATA.nodes.find((n) => n.id === otherId);
                  if (!otherNode) return null;

                  return (
                    <div
                      key={i}
                      onClick={() => setSelectedNode(otherNode)}
                      style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '8px 12px',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {otherNode.label}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)' }}>
                          {link.relation}
                        </div>
                      </div>
                      <ChevronRightIcon size={14} color="var(--text-muted)" />
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Action CTA: Ask Copilot */}
          {onAskCopilot && (
            <button
              type="button"
              onClick={() => onAskCopilot(`Explain statutory implications and case law surrounding ${selectedNode.label} (${selectedNode.title || selectedNode.act || ''})`)}
              style={{
                marginTop: 'auto',
                background: 'var(--accent-gradient)',
                border: 'none',
                borderRadius: '8px',
                padding: '12px',
                color: 'white',
                fontWeight: 700,
                fontSize: '0.88rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <SparklesIcon size={16} />
              <span>Ask Copilot About This Node</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
