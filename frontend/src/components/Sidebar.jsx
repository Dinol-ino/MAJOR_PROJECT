import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import {
  ShieldIcon,
  PlusIcon,
  SidebarIcon,
  FolderIcon,
  BookIcon,
  AuditIcon,
  SparklesIcon,
  SettingsIcon,
  TrashIcon,
  LogOutIcon
} from './Icons';

export default function Sidebar({
  activeSessionId,
  onSelectSession,
  onNewTask,
  collapsed,
  onToggleCollapse,
  user,
  onLogout
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

  if (collapsed) {
    return (
      <aside
        style={{
          width: '64px',
          height: '100vh',
          background: '#121214',
          borderRight: '1px solid #27272a',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '16px 0',
          gap: '20px',
        }}
      >
        <button
          type="button"
          onClick={onToggleCollapse}
          style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          title="Expand sidebar"
        >
          <SidebarIcon size={20} />
        </button>

        <button
          type="button"
          onClick={onNewTask}
          style={{
            background: 'var(--accent-color)',
            border: 'none',
            borderRadius: '50%',
            width: '40px',
            height: '40px',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
          title="New Task"
        >
          <PlusIcon size={20} />
        </button>
      </aside>
    );
  }

  return (
    <aside
      style={{
        width: '260px',
        height: '100vh',
        background: '#121214',
        borderRight: '1px solid #27272a',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px',
        userSelect: 'none',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldIcon size={20} color="var(--accent-color)" />
          <span style={{ fontWeight: 800, fontSize: '1.1rem', color: '#f8fafc', letterSpacing: '-0.02em' }}>
            dfrag
          </span>
        </div>
        <button type="button" onClick={onToggleCollapse} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
          <SidebarIcon size={16} />
        </button>
      </div>

      {/* Primary Action Button */}
      <button
        type="button"
        onClick={onNewTask}
        style={{
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid #27272a',
          borderRadius: '8px',
          padding: '10px 14px',
          color: '#f8fafc',
          fontWeight: 600,
          fontSize: '0.88rem',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          cursor: 'pointer',
          marginBottom: '20px',
          transition: 'all 0.2s ease',
        }}
      >
        <PlusIcon size={16} color="var(--accent-color)" />
        <span>New task</span>
      </button>

      {/* Nav Links */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '24px' }}>
        <div style={{ padding: '8px 10px', borderRadius: '6px', color: '#cbd5e1', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(255,255,255,0.03)' }}>
          <SparklesIcon size={16} color="var(--accent-color)" /> Legal Copilot
        </div>
        <div style={{ padding: '8px 10px', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BookIcon size={16} /> Statute Knowledge
        </div>
        <div style={{ padding: '8px 10px', borderRadius: '6px', color: '#94a3b8', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AuditIcon size={16} /> Cryptographic Audit
        </div>
      </div>

      {/* Tasks History Section */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
          Task History
        </div>

        {sessions.length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: '#64748b', padding: '8px 10px' }}>
            No task history yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {sessions.map((s) => {
              const isActive = s.session_id === activeSessionId;
              return (
                <div
                  key={s.session_id}
                  onClick={() => onSelectSession(s.session_id)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '0.83rem',
                    color: isActive ? '#f8fafc' : '#94a3b8',
                    background: isActive ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                    {s.title}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, s.session_id)}
                    style={{ background: 'none', border: 'none', color: '#64748b', opacity: 0.6, cursor: 'pointer', padding: 2 }}
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

      {/* Profile / User Footer */}
      <div style={{ borderTop: '1px solid #27272a', paddingTop: '14px', marginTop: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--accent-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 700, fontSize: '0.8rem' }}>
            {user ? (user.username?.[0] || 'U').toUpperCase() : 'U'}
          </div>
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120 }}>
            {user ? user.username || user.email || 'Legal User' : 'Legal User'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {onLogout && (
            <button type="button" onClick={onLogout} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }} title="Logout">
              <LogOutIcon size={16} />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
