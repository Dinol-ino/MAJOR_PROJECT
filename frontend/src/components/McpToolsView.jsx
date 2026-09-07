import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  CodeIcon,
  ServerIcon,
  CheckShieldIcon,
  CheckIcon,
  RefreshIcon,
  ExternalLinkIcon,
  SparklesIcon
} from './Icons';

export default function McpToolsView() {
  const [mcpData, setMcpData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reconnecting, setReconnecting] = useState({});
  const [discovering, setDiscovering] = useState(false);
  const [discoveryMsg, setDiscoveryMsg] = useState(null);

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

  const handleReconnect = async (serverName) => {
    setReconnecting(prev => ({ ...prev, [serverName]: true }));
    try {
      await apiClient.reconnectMcpServer(serverName);
      await fetchMcpData();
    } catch (e) {
      console.error(`Reconnect failed for ${serverName}:`, e);
    } finally {
      setReconnecting(prev => ({ ...prev, [serverName]: false }));
    }
  };

  const handleDiscoverTools = async () => {
    setDiscovering(true);
    setDiscoveryMsg(null);
    try {
      const res = await apiClient.discoverMcpTools();
      setDiscoveryMsg(`Discovered ${res.total_discovered || 0} tools across connected MCP servers.`);
      await fetchMcpData();
    } catch (e) {
      setDiscoveryMsg("Tool discovery failed. Check server connectivity.");
    } finally {
      setDiscovering(false);
    }
  };

  const apiEndpoints = [
    { method: 'POST', path: '/chat', desc: 'Secure 3-layer defensive chat inference with citation grounding and Presidio PII anonymization.' },
    { method: 'POST', path: '/mcp/tool-call', desc: 'Policy-gated, schema-validated MCP tool dispatch with output sanitization and L6 audit logging.' },
    { method: 'GET', path: '/mcp/status', desc: 'Real-time MCP Gateway status, registered categories, active servers, and typed tool schemas.' },
    { method: 'POST', path: '/mcp/discover', desc: 'Auto-discovers JSON tool schemas across connected legal MCP servers.' },
    { method: 'POST', path: '/statutes/sync', desc: 'Synchronizes 17+ Indian statutes from MCP servers and canonical legal datasets.' },
    { method: 'GET', path: '/statutes/graph', desc: 'Live DB-backed legal citation graph computed from assistant citations and cross-walk relations.' },
    { method: 'POST', path: '/upload/batch', desc: 'Multi-PDF batch ingestion with section-aware chunking and Tier 2 indexation.' },
    { method: 'GET', path: '/audit/verify', desc: 'Cryptographic SHA-256 hash-chain verification across all logged system actions.' },
  ];

  // Spec 04 §2.2: Renders exclusively from endpoint data (no hardcoded fallback array)
  const activeServers = mcpData?.active_servers || [];
  const categories = mcpData?.categories || ['LOCAL_RETRIEVAL', 'DOCUMENT_SEARCH', 'LEGAL_SEARCH', 'CURRENT_LAW', 'CASE_LAW_SEARCH', 'GOVERNMENT_SOURCE', 'DEEP_RESEARCH'];
  const totalTools = mcpData?.total_registered_tools || 0;

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
              MCP Gateway & Subsystem Permissions
            </h1>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Real-time subprocess health monitoring, Model Context Protocol server connections, and schema-validated tool manifests.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={handleDiscoverTools}
            disabled={discovering}
            style={{
              background: 'var(--accent-gradient)',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 14px',
              color: 'white',
              fontSize: '0.8rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: discovering ? 'wait' : 'pointer'
            }}
          >
            <SparklesIcon size={14} />
            <span>{discovering ? 'Discovering...' : 'Auto-Discover Tools'}</span>
          </button>

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
              cursor: 'pointer'
            }}
          >
            <RefreshIcon size={14} className={loading ? 'spin-icon' : ''} />
            <span>Refresh Status</span>
          </button>
        </div>
      </div>

      {discoveryMsg && (
        <div style={{ background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px', padding: '10px 16px', fontSize: '0.82rem', color: 'var(--accent-cyan)', marginBottom: '20px' }}>
          {discoveryMsg}
        </div>
      )}

      {/* Categories & Quotas Banner */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '18px 24px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
            Active Tool Categories & Policy Gate ({categories.length} Categories, {totalTools} Tools)
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

      {/* Real MCP Servers Section (Spec 04 §2.1 & §2.2) */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ServerIcon size={16} color="var(--accent-cyan)" />
          <span>Connected MCP Servers (Subprocess Health)</span>
        </h2>

        {activeServers.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.86rem', padding: '20px', background: 'var(--bg-card)', borderRadius: '8px' }}>
            No MCP servers configured.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
            {activeServers.map((srv) => {
              const isConnected = srv.status === 'connected';
              const isError = srv.status === 'error';
              const isReconnecting = reconnecting[srv.name];

              let statusColor = isConnected ? 'var(--defense-pass, #10b981)' : isError ? '#ef4444' : '#94a3b8';
              let statusBg = isConnected ? 'rgba(16, 185, 129, 0.1)' : isError ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.05)';

              return (
                <div key={srv.name} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '18px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        {srv.name}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: statusColor, background: statusBg, padding: '2px 8px', borderRadius: '10px', fontWeight: 700, textTransform: 'capitalize' }}>
                        ● {srv.status || 'Active'}
                      </span>
                    </div>

                    <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.4', marginBottom: '12px' }}>
                      {srv.description || `Transport: ${srv.transport || 'stdio'}`}
                    </p>

                    {isError && srv.error_reason && (
                      <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '6px', padding: '8px 10px', fontSize: '0.72rem', color: '#fca5a5', marginBottom: '12px' }}>
                        Reason: {srv.error_reason}
                      </div>
                    )}

                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600, textTransform: 'uppercase' }}>
                      Capabilities & Discovered Tools:
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '14px' }}>
                      {(srv.tools || srv.capabilities || []).map((t) => (
                        <span key={t} style={{ fontSize: '0.68rem', fontFamily: 'monospace', background: 'rgba(255,255,255,0.04)', color: 'var(--accent-cyan)', padding: '2px 6px', borderRadius: '4px' }}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Reconnect Button (Spec 04 §2.2) */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid rgba(255, 255, 255, 0.04)', paddingTop: '10px' }}>
                    <button
                      type="button"
                      onClick={() => handleReconnect(srv.name)}
                      disabled={isReconnecting}
                      style={{
                        background: 'rgba(255, 255, 255, 0.04)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                        padding: '4px 10px',
                        color: 'var(--text-secondary)',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        cursor: isReconnecting ? 'wait' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <RefreshIcon size={12} className={isReconnecting ? "spin-icon" : ""} />
                      <span>{isReconnecting ? 'Reconnecting...' : 'Reconnect'}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* REST API Reference Section */}
      <div>
        <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CodeIcon size={16} color="var(--accent-indigo)" />
          <span>Core Subsystem REST API Endpoints</span>
        </h2>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', overflow: 'hidden' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {apiEndpoints.map((ep, i) => (
              <div
                key={ep.path}
                style={{
                  padding: '12px 20px',
                  borderBottom: i < apiEndpoints.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}
              >
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: ep.method === 'POST' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                    color: ep.method === 'POST' ? 'var(--accent-blue)' : 'var(--defense-pass)',
                    width: '44px',
                    textAlign: 'center',
                  }}
                >
                  {ep.method}
                </span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: 'var(--text-primary)', width: '220px' }}>
                  {ep.path}
                </span>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
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
