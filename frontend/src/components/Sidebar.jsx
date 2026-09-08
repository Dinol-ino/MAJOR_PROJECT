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
  CheckShieldIcon,
  FolderIcon,
  EditIcon,
  CheckIcon
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
  shieldOn,
  activeVaultId,
  onSelectVault
}) {
  const [sessions, setSessions] = useState([]);
  const [vaults, setVaults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isCreatingVault, setIsCreatingVault] = useState(false);
  const [newVaultName, setNewVaultName] = useState('');
  const [editingChatId, setEditingChatId] = useState(null);
  const [editingChatTitle, setEditingChatTitle] = useState('');

  const fetchVaults = async () => {
    try {
      const data = await apiClient.getVaults();
      setVaults(data.vaults || []);
    } catch (e) {
      console.warn("Failed to load vaults:", e);
    }
  };

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
    fetchVaults();
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

  const handleCreateVault = async (e) => {
    e.preventDefault();
    if (!newVaultName.trim()) return;
    try {
      const v = await apiClient.createVault(newVaultName.trim());
      setNewVaultName('');
      setIsCreatingVault(false);
      fetchVaults();
      if (onSelectVault) onSelectVault(v.id);
    } catch (err) {
      console.error("Failed to create vault:", err);
    }
  };

  const handleDeleteVault = async (e, vid) => {
    e.stopPropagation();
    if (!window.confirm("Delete this Project Vault and its indexed document vectors?")) return;
    try {
      await apiClient.deleteVault(vid);
      fetchVaults();
      if (activeVaultId === vid && onSelectVault) {
        onSelectVault(null);
      }
    } catch (err) {
      console.error("Failed to delete vault:", err);
    }
  };

  const handleStartRename = (e, session) => {
    e.stopPropagation();
    setEditingChatId(session.session_id);
    setEditingChatTitle(session.title);
  };

  const handleSaveRename = async (e, sid) => {
    e.stopPropagation();
    if (!editingChatTitle.trim()) {
      setEditingChatId(null);
      return;
    }
    try {
      await apiClient.renameConversation(sid, editingChatTitle.trim());
      setEditingChatId(null);
      fetchSessions();
    } catch (err) {
      console.error("Failed to rename conversation:", err);
      setEditingChatId(null);
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
    { key: 'settings', label: 'Settings', icon: EditIcon, color: 'var(--accent)' },
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

      {/* Project Vaults Section (Spec 01) */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', padding: '0 8px' }}>
          <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Project Vaults
          </span>
          <button
            type="button"
            onClick={() => setIsCreatingVault(!isCreatingVault)}
            style={{ background: 'none', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '2px' }}
            title="Create new matter vault"
          >
            <PlusIcon size={12} />
            <span>New</span>
          </button>
        </div>

        {isCreatingVault && (
          <form onSubmit={handleCreateVault} style={{ padding: '4px 8px', marginBottom: '8px' }}>
            <input
              type="text"
              placeholder="Matter name (e.g. Tata Arbitration)..."
              value={newVaultName}
              onChange={(e) => setNewVaultName(e.target.value)}
              autoFocus
              style={{
                width: '100%',
                padding: '5px 8px',
                fontSize: '0.76rem',
                borderRadius: '6px',
                border: '1px solid var(--accent-cyan)',
                background: 'var(--bg-card)',
                color: 'var(--text-primary)',
                outline: 'none',
                boxSizing: 'border-box',
              }}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setIsCreatingVault(false);
              }}
            />
          </form>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxHeight: '140px', overflowY: 'auto' }}>
          {vaults.map((v) => {
            const isSelected = activeVaultId === v.id;
            return (
              <div
                key={v.id}
                onClick={() => {
                  if (onSelectVault) {
                    onSelectVault(isSelected ? null : v.id);
                  }
                }}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  background: isSelected ? 'rgba(0, 210, 180, 0.12)' : 'transparent',
                  border: isSelected ? '1px solid rgba(0, 210, 180, 0.3)' : '1px solid transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
                title={v.description || v.vault_name}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden', flex: 1 }}>
                  <FolderIcon size={14} color={isSelected ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.vault_name}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.65rem', background: 'rgba(255, 255, 255, 0.06)', padding: '1px 5px', borderRadius: '4px', color: 'var(--text-dim)' }}>
                    {v.document_count || 0} doc
                  </span>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteVault(e, v.id)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-dim)', opacity: 0.5, cursor: 'pointer', padding: 1 }}
                    title="Delete Project Vault"
                  >
                    <TrashIcon size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Task History Section (Persistent Chats & Renaming) */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', minHeight: '80px' }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px', paddingLeft: '8px' }}>
          Conversations
        </div>

        {sessions.length === 0 ? (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', padding: '8px 10px' }}>
            No conversations yet — start by asking a question
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {sessions.map((s) => {
              const isActive = s.session_id === activeSessionId && activeView === 'chat';
              const isEditing = editingChatId === s.session_id;

              return (
                <div
                  key={s.session_id}
                  onClick={() => {
                    if (!isEditing) {
                      onSelectSession(s.session_id);
                      setActiveView('chat');
                    }
                  }}
                  style={{
                    padding: '6px 8px',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: isActive ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {isEditing ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={editingChatTitle}
                        onChange={(e) => setEditingChatTitle(e.target.value)}
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename(e, s.session_id);
                          if (e.key === 'Escape') setEditingChatId(null);
                        }}
                        style={{
                          width: '100%',
                          fontSize: '0.78rem',
                          background: 'var(--bg-card)',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--accent-cyan)',
                          borderRadius: '4px',
                          padding: '2px 6px',
                          outline: 'none',
                        }}
                      />
                      <button
                        type="button"
                        onClick={(e) => handleSaveRename(e, s.session_id)}
                        style={{ background: 'none', border: 'none', color: 'var(--defense-pass)', cursor: 'pointer' }}
                        title="Save rename"
                      >
                        <CheckIcon size={13} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <span
                        onDoubleClick={(e) => handleStartRename(e, s)}
                        style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}
                        title="Double-click to rename"
                      >
                        {s.title}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <button
                          type="button"
                          onClick={(e) => handleStartRename(e, s)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dim)', opacity: 0.5, cursor: 'pointer', padding: 2 }}
                          title="Rename chat"
                        >
                          <EditIcon size={12} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDelete(e, s.session_id)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dim)', opacity: 0.5, cursor: 'pointer', padding: 2 }}
                          title="Delete chat"
                        >
                          <TrashIcon size={12} />
                        </button>
                      </div>
                    </>
                  )}
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
