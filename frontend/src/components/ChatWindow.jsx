import React, { useState } from 'react';
import CommandInput from './CommandInput';
import SourcesPanel from './SourcesPanel';
import MessageContent from './MessageContent';
import StagedLoadingIndicator from './StagedLoadingIndicator';
import {
  ShieldAlertIcon,
  AlertTriangleIcon,
  InfoIcon,
  UserIcon,
  BotIcon,
  Volume2Icon,
  SparklesIcon,
  CopyIcon,
  CheckIcon
} from './Icons';

export default function ChatWindow({
  messages,
  onSendMessage,
  sessionId,
  onUploadSuccess,
  isGenerating,
  generationStage = 'retrieving',
  onClearThread,
  activeVaultId,
  activeModel = null,
  onNavigate = null,
}) {
  const lastMetrics = [...messages].reverse().find((m) => m.role === 'assistant' && m.metrics)?.metrics || null;
  const [speakingIdx, setSpeakingIdx] = useState(null);
  const [copiedIdx, setCopiedIdx] = useState(null);

  const handleSpeak = (text, idx) => {
    if (!('speechSynthesis' in window)) {
      alert('Text-to-Speech is not supported in this browser.');
      return;
    }

    if (speakingIdx === idx) {
      window.speechSynthesis.cancel();
      setSpeakingIdx(null);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-IN';
    utterance.rate = 1.0;

    utterance.onend = () => setSpeakingIdx(null);
    utterance.onerror = () => setSpeakingIdx(null);

    setSpeakingIdx(idx);
    window.speechSynthesis.speak(utterance);
  };

  const handleCopyText = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--bg-app)' }}>
      {/* Messages / Canvas Container */}
      <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {messages.length === 0 ? (
          /* Empty / Zero-State Hero Canvas */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              textAlign: 'center',
              padding: '40px 20px',
              maxWidth: 'var(--max-content-width)',
              margin: '0 auto',
              width: '100%'
            }}
            className="view-container"
          >
            <h1 style={{ fontFamily: 'var(--font-serif)', fontWeight: 600, fontSize: '2.1rem', color: 'var(--text-primary)', marginBottom: '12px', lineHeight: 1.2 }}>
              Legal research, grounded in your sources
            </h1>
            <p style={{ fontFamily: 'var(--font-serif)', fontSize: '1.05rem', color: 'var(--text-secondary)', maxWidth: '560px', marginBottom: '28px', lineHeight: 1.6 }}>
              Ask about indexed statutes or your uploaded documents. Answers cite the passages they rely on;
              when the evidence is insufficient, you will be told rather than given a guess.
            </p>

            <CommandInput
              onSendMessage={onSendMessage}
              sessionId={sessionId}
              onUploadSuccess={onUploadSuccess}
              isGenerating={isGenerating}
              activeVaultId={activeVaultId}
            />
          </div>
        ) : (
          /* Active Conversation Stream — Constrained to 760px */
          <div style={{ maxWidth: 'var(--max-content-width)', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                data-testid={msg.role === 'user' ? 'user-message' : 'assistant-message'}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '92%',
                  background: msg.role === 'user' ? 'var(--bg-raised)' : 'var(--bg-card)',
                  border: `1px solid ${msg.role === 'user' ? 'var(--border-medium)' : 'var(--border-subtle)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: '16px 20px',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                {/* Message Header */}
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {msg.role === 'user' ? (
                      <>
                        <UserIcon size={14} color="var(--accent-pink)" />
                        <span style={{ fontWeight: 700, color: 'var(--accent-pink)' }}>YOU</span>
                      </>
                    ) : (
                      <>
                        <BotIcon size={15} color="var(--accent)" />
                        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                          {msg.model_used ? msg.model_used : (msg.failure_kind ? 'No model output' : 'Assistant')}
                        </span>

                      </>
                    )}
                  </div>

                  {/* Actions Toolbar */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      type="button"
                      onClick={() => handleCopyText(msg.content, idx)}
                      style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem' }}
                      title="Copy message"
                    >
                      {copiedIdx === idx ? <CheckIcon size={13} color="var(--status-green)" /> : <CopyIcon size={13} />}
                    </button>

                    {msg.role === 'assistant' && (
                      <button
                        type="button"
                        onClick={() => handleSpeak(msg.content, idx)}
                        style={{
                          background: speakingIdx === idx ? 'var(--accent-blue-subtle)' : 'none',
                          border: 'none',
                          color: speakingIdx === idx ? 'var(--accent)' : 'var(--text-muted)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.72rem',
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}
                        title={speakingIdx === idx ? 'Stop audio' : 'Listen to response'}
                      >
                        <Volume2Icon size={13} />
                        <span>{speakingIdx === idx ? 'Playing...' : 'TTS'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Message Text Content */}
                {msg.role === 'user' ? (
                  <p style={{ fontSize: '0.94rem', lineHeight: '1.6', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', margin: 0 }}>
                    {msg.content}
                  </p>
                ) : (
                  <MessageContent
                    content={msg.content}
                    reasoningTrace={msg.reasoning_trace}
                    citations={msg.citations_parsed || msg.citations || []}
                    groundingScore={msg.grounding_score}
                    modelUsed={msg.model_used}
                    runtimeUsed={msg.runtime_used}
                    onRegenerate={
                      idx === messages.length - 1 && !isGenerating
                        ? () => {
                            const lastUser = [...messages].reverse().find((m) => m.role === 'user');
                            if (lastUser) onSendMessage(lastUser.content);
                          }
                        : null
                    }
                  />
                )}

                {/* 1. Security Shield Block Warning */}
                {msg.blocked_by && (
                  <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(248, 81, 73, 0.08)', border: '1px solid var(--defense-block)', borderRadius: 'var(--radius-sm)', color: 'var(--defense-block)', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ShieldAlertIcon size={16} />
                      <span>Blocked by <strong>{msg.blocked_by.toUpperCase()} Guard</strong>: {msg.block_reason}</span>
                    </div>
                    {msg.correlation_id && (
                      <span style={{ fontSize: '0.68rem', opacity: 0.8, fontFamily: 'var(--font-mono, monospace)', marginLeft: '24px' }}>
                        Trace ID: {msg.correlation_id}
                      </span>
                    )}
                  </div>
                )}

                {/* 2. Model Unavailable / Transport Alert */}
                {!msg.blocked_by && msg.failure_kind === 'model_unavailable' && (
                  <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(217, 119, 6, 0.1)', border: '1px solid rgba(217, 119, 6, 0.4)', borderRadius: 'var(--radius-sm)', color: '#d97706', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <AlertTriangleIcon size={16} color="#d97706" />
                      <span>The local model did not answer. {activeModel ? `Active model: ${activeModel}.` : 'No local model is active.'}</span>
                    </div>
                    {onNavigate && (
                      <button type="button" onClick={() => onNavigate('hardware')} style={{ alignSelf: 'flex-start', marginLeft: '24px', background: 'transparent', border: '1px solid currentColor', color: 'inherit', borderRadius: 'var(--radius-sm)', padding: '3px 10px', cursor: 'pointer', fontSize: '0.76rem' }}>
                        Open Hardware &amp; Models
                      </button>
                    )}
                    {msg.correlation_id && (
                      <span style={{ fontSize: '0.68rem', opacity: 0.85, fontFamily: 'var(--font-mono, monospace)', marginLeft: '24px' }}>
                        Trace ID: {msg.correlation_id}
                      </span>
                    )}
                  </div>
                )}

                {/* 3. Insufficient Evidence Notice */}
                {!msg.blocked_by && msg.failure_kind === 'insufficient_evidence' && (
                  <div style={{ marginTop: '10px', padding: '8px 12px', background: 'rgba(56, 189, 248, 0.07)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-cyan)', fontSize: '0.78rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <InfoIcon size={15} color="var(--accent-cyan)" />
                      <span>Insufficient verified evidence was retrieved to answer this reliably.</span>
                    </div>
                    {msg.correlation_id && (
                      <span style={{ fontSize: '0.68rem', opacity: 0.75, fontFamily: 'var(--font-mono, monospace)' }}>
                        Trace: {msg.correlation_id.substring(0, 8)}
                      </span>
                    )}
                  </div>
                )}

                {/* Citation Sources Panel */}
                {!msg.blocked_by && msg.sources && msg.sources.length > 0 && (
                  <SourcesPanel sources={msg.sources} citations={msg.citations_parsed} />
                )}
              </div>
            ))}

            {/* Staged Loading & Shimmer Skeleton */}
            {isGenerating && (
              <div style={{ width: '100%' }}>
                <StagedLoadingIndicator stage={generationStage} />
              </div>
            )}

            {/* Bottom Floating Command Input */}
            <div style={{ marginTop: '14px', paddingTop: '6px' }}>
              <CommandInput
                onSendMessage={onSendMessage}
                sessionId={sessionId}
                onUploadSuccess={onUploadSuccess}
                isGenerating={isGenerating}
                activeVaultId={activeVaultId}
                lastMetrics={lastMetrics}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
