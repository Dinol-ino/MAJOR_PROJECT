import React from 'react';

/**
 * FilePill — Claude-style attachment pill rendered above the chat input.
 * Supports lifecycle states: 'uploading' | 'indexing' | 'ready' | 'failed'
 */
export default function FilePill({
  file,
  onRemove,
  onRetry
}) {
  const {
    id,
    name = 'document.pdf',
    size_mb,
    size_str,
    status = 'ready', // 'uploading' | 'indexing' | 'ready' | 'failed'
    progress = 100,
    page_count,
    error_message
  } = file;

  const displaySize = size_str || (size_mb ? `${size_mb} MB` : '');

  // Status-dependent styling and badges
  let statusBadge = null;
  let pillBorder = 'var(--border-subtle)';
  let pillBg = 'var(--bg-raised)';

  if (status === 'uploading') {
    pillBorder = 'var(--border-medium)';
    statusBadge = (
      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--accent-blue)', fontSize: '0.7rem' }}>
        <span>●●○</span>
        <span>{Math.round(progress)}%</span>
      </span>
    );
  } else if (status === 'indexing') {
    pillBorder = 'rgba(210, 153, 34, 0.4)';
    pillBg = 'rgba(210, 153, 34, 0.06)';
    statusBadge = (
      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--accent-amber)', fontSize: '0.7rem' }}>
        <span className="pulse-text">⟳</span>
        <span>Indexing {Math.round(progress)}%</span>
      </span>
    );
  } else if (status === 'ready') {
    pillBorder = 'rgba(63, 185, 80, 0.35)';
    pillBg = 'rgba(63, 185, 80, 0.05)';
    statusBadge = (
      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--status-green)', fontSize: '0.7rem', fontWeight: 600 }}>
        <span>✓ Indexed</span>
        {page_count ? <span>· {page_count} pages</span> : null}
      </span>
    );
  } else if (status === 'failed') {
    pillBorder = 'rgba(248, 81, 73, 0.4)';
    pillBg = 'rgba(248, 81, 73, 0.08)';
    statusBadge = (
      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--status-red)', fontSize: '0.7rem', fontWeight: 600 }}>
        <span>✗ Failed</span>
        {onRetry && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onRetry(file); }}
            style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', textDecoration: 'underline', padding: 0, fontSize: '0.7rem' }}
          >
            Retry
          </button>
        )}
      </span>
    );
  }

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '4px 10px',
        borderRadius: 'var(--radius-sm)',
        background: pillBg,
        border: `1px solid ${pillBorder}`,
        fontSize: '0.76rem',
        color: 'var(--text-primary)',
        transition: 'all 0.15s ease-out',
        maxWidth: '320px'
      }}
      title={error_message || name}
    >
      <span style={{ fontSize: '0.85rem' }}>📄</span>

      <span
        style={{
          fontWeight: 600,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: '130px'
        }}
      >
        {name}
      </span>

      {displaySize && (
        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
          {displaySize}
        </span>
      )}

      {statusBadge}

      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(id || file);
          }}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            fontSize: '0.85rem',
            lineHeight: 1,
            padding: '2px',
            borderRadius: '2px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          title="Remove attachment"
        >
          ✕
        </button>
      )}
    </div>
  );
}
