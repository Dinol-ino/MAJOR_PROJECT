import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SparklesIcon, ChevronDownIcon, CheckShieldIcon } from './Icons';

export default function MessageContent({
  content = '',
  reasoningTrace = null,
  citations = [],
  groundingScore = null,
  modelUsed = null,
  runtimeUsed = null,
  onRegenerate = null,
  isStreaming = false,
}) {
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const [activeCitation, setActiveCitation] = useState(null);
  const [copied, setCopied] = useState(false);
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);

  // Copy to clipboard
  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Web Speech TTS
  const handleTTS = () => {
    if (!window.speechSynthesis) return;

    if (isPlayingTTS) {
      window.speechSynthesis.cancel();
      setIsPlayingTTS(false);
      return;
    }

    // Clean markdown symbols for natural speech
    const cleanText = content
      .replace(/\[\^\d+\]/g, '')
      .replace(/#{1,6}\s+/g, '')
      .replace(/[*_`]/g, '')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.onend = () => setIsPlayingTTS(false);
    utterance.onerror = () => setIsPlayingTTS(false);

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setIsPlayingTTS(true);
  };

  // Grounding chip badge color & label
  const score = groundingScore !== null && groundingScore !== undefined ? Number(groundingScore) : null;
  let groundingBadge = null;

  if (score !== null && !isNaN(score)) {
    let color = 'var(--defense-pass, #10b981)';
    let bg = 'rgba(16, 185, 129, 0.12)';
    let border = 'rgba(16, 185, 129, 0.3)';
    let label = `Grounded: ${Math.round(score)}%`;
    let title = 'Grounded in authoritative statutory provisions';

    if (score < 60) {
      color = '#ef4444';
      bg = 'rgba(239, 68, 68, 0.12)';
      border = 'rgba(239, 68, 68, 0.3)';
      label = `Weakly Grounded: ${Math.round(score)}%`;
      title = 'Multiple claims lack source evidence';
    } else if (score < 80) {
      color = '#f59e0b';
      bg = 'rgba(245, 158, 11, 0.12)';
      border = 'rgba(245, 158, 11, 0.3)';
      label = `Grounded: ${Math.round(score)}%`;
      title = 'Low grounding — verify sources';
    }

    groundingBadge = (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: '12px',
          padding: '2px 8px',
          fontSize: '0.72rem',
          fontWeight: 700,
          color: color,
        }}
        title={title}
      >
        <CheckShieldIcon size={12} color={color} />
        {label}
      </span>
    );
  }

  // Custom link renderer to make [^1] superscript badges clickable
  const renderLink = ({ href, children, ...props }) => {
    const text = String(children);
    const supMatch = text.match(/^\^?(\d+)$/);
    if (supMatch) {
      const citIndex = parseInt(supMatch[1], 10);
      const matchedCit = citations.find((c) => c.index === citIndex);

      return (
        <sup
          style={{
            display: 'inline-block',
            cursor: matchedCit ? 'pointer' : 'default',
            color: 'var(--accent-cyan, #06b6d4)',
            fontWeight: 700,
            padding: '0 2px',
            fontSize: '0.75rem',
            userSelect: 'none',
          }}
          onClick={(e) => {
            e.stopPropagation();
            if (matchedCit) {
              setActiveCitation(activeCitation?.index === citIndex ? null : matchedCit);
            }
          }}
          title={
            matchedCit
              ? `${matchedCit.act} § ${matchedCit.section}${matchedCit.page ? ` (p. ${matchedCit.page})` : ''}`
              : `Citation [${citIndex}]`
          }
        >
          [{citIndex}]
        </sup>
      );
    }

    return (
      <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)' }} {...props}>
        {children}
      </a>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
      {/* Deep Thinking / Analytical Reasoning Trace Accordion */}
      {reasoningTrace && (
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          <button
            type="button"
            onClick={() => setReasoningExpanded(!reasoningExpanded)}
            style={{
              width: '100%',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #94a3b8)',
              fontSize: '0.76rem',
              fontWeight: 600,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <SparklesIcon size={13} color="var(--accent-indigo, #818cf8)" />
              <span>Analytical Reasoning Trace</span>
            </div>
            <ChevronDownIcon
              size={14}
              style={{
                transform: reasoningExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease',
              }}
            />
          </button>

          {reasoningExpanded && (
            <div
              style={{
                padding: '10px 14px',
                borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                background: 'rgba(0, 0, 0, 0.2)',
                fontSize: '0.78rem',
                fontFamily: 'monospace',
                color: 'var(--text-secondary, #cbd5e1)',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                maxHeight: '260px',
                overflowY: 'auto',
              }}
            >
              {reasoningTrace}
            </div>
          )}
        </div>
      )}

      {/* Main Markdown Assistant Response */}
      <div
        className="legal-markdown-body"
        style={{
          color: 'var(--text-primary, #f8fafc)',
          fontSize: '0.92rem',
          lineHeight: 1.68,
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: renderLink,
            table: ({ node, ...props }) => (
              <div style={{ overflowX: 'auto', margin: '14px 0' }}>
                <table
                  style={{
                    borderCollapse: 'collapse',
                    width: '100%',
                    fontSize: '0.84rem',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                  {...props}
                />
              </div>
            ),
            th: ({ node, ...props }) => (
              <th
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  padding: '8px 12px',
                  textAlign: 'left',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.15)',
                  fontWeight: 600,
                }}
                {...props}
              />
            ),
            td: ({ node, ...props }) => (
              <td
                style={{
                  padding: '8px 12px',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                }}
                {...props}
              />
            ),
            h2: ({ node, ...props }) => (
              <h2
                style={{
                  fontSize: '1.08rem',
                  fontWeight: 700,
                  margin: '18px 0 8px',
                  color: 'var(--text-primary, #fff)',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                  paddingBottom: '4px',
                }}
                {...props}
              />
            ),
            h3: ({ node, ...props }) => (
              <h3
                style={{
                  fontSize: '0.96rem',
                  fontWeight: 600,
                  margin: '14px 0 6px',
                  color: 'var(--accent-cyan, #06b6d4)',
                }}
                {...props}
              />
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>

      {/* Side-Peek Popup for Clicked Citation */}
      {activeCitation && (
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid var(--accent-cyan, #06b6d4)',
            borderRadius: '10px',
            padding: '12px 14px',
            fontSize: '0.8rem',
            color: 'var(--text-primary, #fff)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-cyan, #06b6d4)' }}>
              [{activeCitation.index}] {activeCitation.act} — Section {activeCitation.section}
              {activeCitation.page && ` (Page ${activeCitation.page})`}
            </div>
            <button
              type="button"
              onClick={() => setActiveCitation(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              ✕
            </button>
          </div>

          {activeCitation.quote && (
            <div
              style={{
                fontSize: '0.75rem',
                color: 'var(--text-secondary, #94a3b8)',
                fontStyle: 'italic',
                borderLeft: '2px solid var(--accent-cyan, #06b6d4)',
                paddingLeft: '8px',
                marginTop: '2px',
              }}
            >
              "{activeCitation.quote}..."
            </div>
          )}
        </div>
      )}

      {/* Meta Action Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: '4px',
          paddingTop: '8px',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
          fontSize: '0.74rem',
          color: 'var(--text-secondary, #94a3b8)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {modelUsed && (
            <span>
              via <strong>{modelUsed}</strong> · {runtimeUsed || 'local'}
            </span>
          )}
          {groundingBadge}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={handleCopy}
            style={{
              background: 'transparent',
              border: 'none',
              color: copied ? 'var(--defense-pass, #10b981)' : 'inherit',
              cursor: 'pointer',
              fontSize: '0.74rem',
              padding: '2px 6px',
            }}
            title="Copy answer markdown"
          >
            {copied ? '✓ Copied' : '⧉ Copy'}
          </button>

          <button
            type="button"
            onClick={handleTTS}
            style={{
              background: 'transparent',
              border: 'none',
              color: isPlayingTTS ? 'var(--accent-cyan, #06b6d4)' : 'inherit',
              cursor: 'pointer',
              fontSize: '0.74rem',
              padding: '2px 6px',
            }}
            title="Read answer aloud (Text-to-Speech)"
          >
            {isPlayingTTS ? '■ Stop' : '🔊 TTS'}
          </button>

          {onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: '0.74rem',
                padding: '2px 6px',
              }}
              title="Regenerate response"
            >
              ↻ Regenerate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
