import React, { useState } from 'react';
import CommandInput from './CommandInput';
import SourcesPanel from './SourcesPanel';
import ConfidenceIndicator from './ConfidenceIndicator';
import MessageContent from './MessageContent';
import StagedLoadingIndicator from './StagedLoadingIndicator';
import {
  ShieldAlertIcon,
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
  activeVaultId
}) {
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(79, 140, 255, 0.12)',
                  border: '1px solid rgba(79, 140, 255, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <SparklesIcon size={22} color="var(--accent)" />
              </div>
            </div>

            <h1 style={{ fontSize: '2.1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px', letterSpacing: '-0.02em' }}>
              Legal AI Research Copilot
            </h1>

            <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', maxWidth: '540px', marginBottom: '28px', lineHeight: '1.5' }}>
              Ask questions on Indian statutes, examine case evidence with citation grounding, and verify procedural requirements with multi-tier defense.
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
                        <UserIcon size={14} color="var(--accent)" />
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>YOU</span>
                      </>
                    ) : (
                      <>
                        <BotIcon size={15} color="var(--accent-cyan)" />
                        <span style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>NYAYA-CORE v4</span>
                        <ConfidenceIndicator
                          confidenceScore={msg.confidence_score}
                          sourcesCount={msg.sources ? msg.sources.length : 0}
                          isGrounded={!msg.blocked_by}
                        />
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
                          background: speakingIdx === idx ? 'rgba(79, 140, 255, 0.15)' : 'none',
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
                    groundingScore={msg.grounding_score ?? msg.confidence_score}
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

                {/* Blocked Shield Warning */}
                {msg.blocked_by && (
                  <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(248, 81, 73, 0.08)', border: '1px solid var(--defense-block)', borderRadius: 'var(--radius-sm)', color: 'var(--defense-block)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldAlertIcon size={16} />
                    <span>Blocked by <strong>{msg.blocked_by.toUpperCase()} Guard</strong>: {msg.block_reason}</span>
                  </div>
                )}

                {/* Citation Sources Panel */}
                {!msg.blocked_by && msg.sources && msg.sources.length > 0 && (
                  <SourcesPanel sources={msg.sources} />
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
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
