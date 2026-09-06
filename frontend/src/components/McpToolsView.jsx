import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  CodeIcon,
  ServerIcon,
  CheckShieldIcon,
  CheckIcon,
  RefreshIcon,
  ExternalLinkIcon
} from './Icons';

export default function McpToolsView() {
  const [mcpData, setMcpData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchMcpData = async () => {
    setLoading(true);
    try {
      const data = await apiClient.getMcpStatus();
      setMcpData(data);
    } catch (e) {
      console.warn("MCP Status error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMcpData();
  }, []);

  const fallbackServers = [
    {
      name: 'local-statute-server',
      description: 'In-process statutory retrieval and provision lookup against local ChromaDB and BM25 index.',
      status: 'Connected (Offline)',
      toolsCount: 3,
      tools: ['local_statute_search', 'local_provision_lookup', 'user_document_search']
    },
    {
      name: 'indian-legal-gateway',
      description: 'External allowlisted gateway for IndiaCode gazettes and Indian Kanoon case precedents.',
      status: 'Planned (Online Clearance Pending)',
      toolsCount: 3,
      tools: ['indiacode_fetcher', 'kanoon_case_search', 'live_statute_checker']
    }
  ];


  const apiEndpoints = [
    { method: 'POST', path: '/chat', desc: 'Secure 3-layer defensive chat inference with citation grounding and Presidio PII anonymization.' },
    { method: 'POST', path: '/mcp/tool-call', desc: 'Policy-gated, schema-validated MCP tool dispatch with output sanitization and L6 audit logging.' },
    { method: 'GET', path: '/mcp/status', desc: 'Real-time MCP Gateway status, registered categories, active servers, and typed tool schemas.' },
    { method: 'POST', path: '/upload/batch', desc: 'Multi-PDF batch ingestion with section-aware chunking and Tier 2 indexation.' },
    { method: 'POST', path: '/recommend', desc: 'Hardware-aware model selection matching RAM, VRAM, and AVX2 capabilities.' },
    { method: 'GET', path: '/audit/verify', desc: 'Cryptographic SHA-256 hash-chain verification across all logged system actions.' },
  ];

  const activeServers = mcpData?.active_servers?.length ? mcpData.active_servers : fallbackServers;
  const categories = mcpData?.categories || ['LOCAL_RETRIEVAL', 'DOCUMENT_SEARCH', 'LEGAL_SEARCH', 'CURRENT_LAW', 'CASE_LAW_SEARCH', 'GOVERNMENT_SOURCE', 'DEEP_RESEARCH'];
  const totalTools = mcpData?.total_registered_tools || 15;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        background: 'var(--bg-app)',
        padding: '32px 40px',
        boxSizing: 'border-box',
        overflowY: 'auto',
      }}
      className="view-container"
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(56, 189, 248, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CodeIcon size={18} color="var(--accent-blue)" />
            </div>
            <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              MCP Gateway & Tool Permissions
            </h1>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Policy-gated, schema-validated Model Context Protocol subsystem with runtime rate limiting and context sanitization.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ fontSize: '0.8rem', padding: '6px 12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
            Mode: <strong style={{ color: 'var(--accent-cyan)' }}>{mcpData?.current_network_mode || 'OFFLINE'}</strong>
          </div>
          <button
            type="button"
            onClick={fetchMcpData}
            disabled={loading}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-medium)',
              borderRadius: '8px',
              padding: '8px 14px',
              color: 'var(--text-secondary)',
              fontSize: '0.8rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <RefreshIcon size={14} className={loading ? 'pulse-text' : ''} />
            <span>Refresh MCP Status</span>
          </button>
        </div>
      </div>

      {/* Categories & Quotas Banner */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '18px 24px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
            Active Tool Categories & Policies ({categories.length} Categories, {totalTools} Tools)
          </div>
          <span style={{ fontSize: '0.72rem', color: 'var(--defense-pass)', fontWeight: 700 }}>
            Policy Engine: Active
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {categories.map((cat) => (
            <span
              key={cat}
              style={{
                fontSize: '0.72rem',
                fontFamily: 'monospace',
                background: 'rgba(56, 189, 248, 0.08)',
                color: 'var(--accent-blue)',
                border: '1px solid rgba(56, 189, 248, 0.2)',
                padding: '4px 10px',
                borderRadius: '6px',
                fontWeight: 600,
              }}
            >
              {cat}
            </span>
          ))}
        </div>
      </div>

      {/* MCP Servers Section */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ServerIcon size={16} color="var(--accent-cyan)" />
          <span>Registered MCP Servers & Permissions</span>
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          {activeServers.map((srv) => (
            <div key={srv.name} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>{srv.name}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--defense-pass)', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
                  ● {srv.enabled !== false ? 'Allowlisted' : 'Disabled'}
                </span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.4', marginBottom: '12px' }}>
                {srv.description || `Policy: ${srv.policy || 'allow'}`}
              </p>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600, textTransform: 'uppercase' }}>
                Allowed Tools:
              </div>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {(srv.allowed_tools || srv.tools || []).map((t) => (
                  <span key={t} style={{ fontSize: '0.68rem', fontFamily: 'monospace', background: 'rgba(255,255,255,0.04)', color: 'var(--accent-cyan)', padding: '2px 6px', borderRadius: '4px' }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* REST API Reference Section */}
      <div>
        <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CodeIcon size={16} color="var(--accent-indigo)" />
          <span>Core REST API Endpoints</span>
        </h2>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', overflow: 'hidden' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {apiEndpoints.map((ep, i) => (
              <div
                key={ep.path}
                style={{
                  padding: '14px 20px',
                  borderBottom: i < apiEndpoints.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}
              >
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    background: ep.method === 'POST' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                    color: ep.method === 'POST' ? 'var(--accent-blue)' : 'var(--defense-pass)',
                    width: '45px',
                    textAlign: 'center',
                  }}
                >
                  {ep.method}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', width: '220px' }}>
                  {ep.path}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', flex: 1 }}>
                  {ep.desc}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
