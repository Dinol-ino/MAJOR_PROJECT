import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  ShieldIcon,
  PlusIcon,
  SidebarIcon,
  HomeIcon,
  GraphIcon,
  LibraryIcon,
  AuditIcon,
  CpuIcon,
  CodeIcon,
  SparklesIcon,
  TrashIcon,
  LogOutIcon,
  CheckShieldIcon
} from './Icons';

export default function Sidebar({
  activeSessionId,
  onSelectSession,
  onNewTask,
  collapsed,
  onToggleCollapse,
  user,
  onLogout,
  activeView,
  setActiveView,
  shieldOn
}) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await apiClient.getSessions();
      setSessions(data.sessions || []);
    } catch (e) {
      console.warn("Failed to load sessions:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [activeSessionId]);

  const handleDelete = async (e, sid) => {
    e.stopPropagation();
    try {
      await apiClient.deleteSession(sid);
      fetchSessions();
      if (activeSessionId === sid) {
        onNewTask();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const navItems = [
    { key: 'chat', label: 'Legal Copilot', icon: SparklesIcon, color: 'var(--accent-indigo)' },
    { key: 'graph', label: 'Citation Graph', icon: GraphIcon, color: 'var(--accent-cyan)', badge: 'BETA' },
    { key: 'statutes', label: 'Statute Library', icon: LibraryIcon, color: 'var(--accent-blue)' },
    { key: 'audit', label: 'Cryptographic Audit', icon: AuditIcon, color: 'var(--defense-pass)' },
  ];

  const toolItems = [
    { key: 'hardware', label: 'Hardware Engine', icon: CpuIcon, color: 'var(--accent-cyan)' },
    { key: 'mcp', label: 'API & MCP Tools', icon: CodeIcon, color: 'var(--accent-blue)' },
  ];

  if (collapsed) {
    return (
      <aside
        style={{
          width: '64px',
          height: '100vh',
          background: 'var(--bg-sidebar)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '16px 0',
          gap: '16px',
          zIndex: 30,
        }}
      >
        <button
          type="button"
          onClick={onToggleCollapse}
          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
          title="Expand sidebar"
        >
          <SidebarIcon size={20} />
        </button>

        <button
          type="button"
          onClick={onNewTask}
          style={{
            background: 'var(--accent-gradient)',
            border: 'none',
            borderRadius: '50%',
            width: '38px',
            height: '38px',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-sm)',
          }}
          title="New Task"
        >
          <PlusIcon size={18} />
        </button>

        <div style={{ width: '32px', height: '1px', background: 'var(--border-subtle)', margin: '4px 0' }} />

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setActiveView(item.key)}
              style={{
                background: isActive ? 'rgba(0, 210, 180, 0.12)' : 'none',
                border: 'none',
                borderRadius: '8px',
                width: '38px',
                height: '38px',
                color: isActive ? item.color : 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title={item.label}
            >
              <Icon size={18} color={isActive ? item.color : 'var(--text-secondary)'} />
            </button>
          );
        })}
      </aside>
    );
  }

  return (
    <aside
      style={{
        width: '260px',
        height: '100vh',
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px',
        userSelect: 'none',
        boxSizing: 'border-box',
        zIndex: 30,
      }}
    >
      {/* Consensus-style Brand Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShieldIcon size={16} color="white" />
          </div>
          <span style={{ fontFamily: 'var(--font-title)', fontWeight: 800, fontSize: '1.2rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            dfrag<span style={{ color: 'var(--accent-cyan)' }}>.ai</span>
          </span>
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)' }}
          title="Collapse sidebar"
        >
          <SidebarIcon size={16} />
        </button>
      </div>

      {/* Primary Action Button: New Task */}
      <button
        type="button"
        onClick={() => {
          onNewTask();
          setActiveView('chat');
        }}
        style={{
          background: 'rgba(255, 255, 255, 0.04)',
          border: '1px solid var(--border-medium)',
          borderRadius: '8px',
          padding: '10px 14px',
          color: 'var(--text-primary)',
          fontWeight: 600,
          fontSize: '0.88rem',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '18px',
          boxShadow: 'var(--shadow-sm)',
        }}
        className="glow-pill"
      >
        <div style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(0, 210, 180, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <PlusIcon size={14} color="var(--accent-cyan)" />
        </div>
        <span>New Task</span>
      </button>

      {/* Main Navigation Items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '20px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.key;
          return (
            <div
              key={item.key}
              onClick={() => setActiveView(item.key)}
              style={{
                padding: '9px 12px',
                borderRadius: '8px',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: '0.85rem',
                fontWeight: isActive ? 600 : 500,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: isActive ? 'rgba(255, 255, 255, 0.06)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon size={16} color={isActive ? item.color : 'var(--text-muted)'} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span style={{ fontSize: '0.62rem', background: 'rgba(0, 210, 180, 0.15)', color: 'var(--accent-cyan)', padding: '1px 6px', borderRadius: '10px', fontWeight: 700 }}>
                  {item.badge}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Tools & System Section */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px', paddingLeft: '8px' }}>
          Tools
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {toolItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.key;
            return (
              <div
                key={item.key}
                onClick={() => setActiveView(item.key)}
                style={{
                  padding: '8px 12px',
                  borderRadius: '8px',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 600 : 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: isActive ? 'rgba(255, 255, 255, 0.06)' : 'transparent',
                  cursor: 'pointer',
                }}
              >
                <Icon size={15} color={isActive ? item.color : 'var(--text-muted)'} />
                <span>{item.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Task History Section */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', minHeight: '80px' }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px', paddingLeft: '8px' }}>
          History
        </div>

        {sessions.length === 0 ? (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', padding: '8px 10px' }}>
            No task history.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {sessions.map((s) => {
              const isActive = s.session_id === activeSessionId && activeView === 'chat';
              return (
                <div
                  key={s.session_id}
                  onClick={() => {
                    onSelectSession(s.session_id);
                    setActiveView('chat');
                  }}
                  style={{
                    padding: '7px 10px',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: isActive ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                    {s.title}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, s.session_id)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-dim)', opacity: 0.6, cursor: 'pointer', padding: 2 }}
                    title="Delete task"
                  >
                    <TrashIcon size={12} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer: User Profile & Security Shield Status */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Shield Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)', padding: '2px 4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckShieldIcon size={14} color={shieldOn ? 'var(--defense-pass)' : 'var(--defense-block)'} />
            <span>3-Layer Shield: <strong style={{ color: shieldOn ? 'var(--defense-pass)' : 'var(--defense-block)' }}>{shieldOn ? 'Active' : 'Bypassed'}</strong></span>
          </div>
        </div>

        {/* User Info */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 700, fontSize: '0.78rem' }}>
              {user ? (user.username?.[0] || 'D').toUpperCase() : 'D'}
            </div>
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 130 }}>
              {user ? user.username || user.email || 'Dinol Castelino' : 'Dinol Castelino'}
            </div>
          </div>

          {onLogout && (
            <button type="button" onClick={onLogout} style={{ background: 'none', border: 'none', color: 'var(--text-muted)' }} title="Logout">
              <LogOutIcon size={15} />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
