import React, { useState } from 'react';
import CommandInput from './CommandInput';
import SourcesPanel from './SourcesPanel';
import ConfidenceIndicator from './ConfidenceIndicator';
import {
  ShieldAlertIcon,
  UserIcon,
  BotIcon,
  Volume2Icon,
  SparklesIcon,
  CheckShieldIcon,
  CopyIcon,
  CheckIcon
} from './Icons';

export default function ChatWindow({
  messages,
  onSendMessage,
  sessionId,
  onUploadSuccess,
  isGenerating,
  onClearThread
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
          /* Consensus Hero Centered Search Canvas */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              textAlign: 'center',
              padding: '40px 20px',
            }}
            className="view-container"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{ width: 44, height: 44, borderRadius: 12, background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: 'var(--glow-cyan)' }}>
                <SparklesIcon size={24} color="white" />
              </div>
            </div>

            <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '2.4rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px', letterSpacing: '-0.02em' }}>
              Legal AI Research Copilot
            </h1>

            <p style={{ fontSize: '0.96rem', color: 'var(--text-secondary)', maxWidth: '580px', marginBottom: '32px', lineHeight: '1.5' }}>
              Ask questions on Indian statutes, analyze contracts with citation grounding, and verify legal compliance with 3-layer security defense.
            </p>

            <CommandInput
              onSendMessage={onSendMessage}
              sessionId={sessionId}
              onUploadSuccess={onUploadSuccess}
              isGenerating={isGenerating}
            />
          </div>
        ) : (
          /* Active Conversation Stream */
          <div style={{ maxWidth: '820px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '88%',
                  background: msg.role === 'user' ? 'rgba(56, 189, 248, 0.12)' : 'var(--bg-card)',
                  border: `1px solid ${msg.role === 'user' ? 'rgba(56, 189, 248, 0.25)' : 'var(--border-subtle)'}`,
                  borderRadius: '14px',
                  padding: '18px 22px',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                {/* Message Header */}
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {msg.role === 'user' ? (
                      <>
                        <UserIcon size={14} color="var(--accent-blue)" />
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>YOU</span>
                      </>
                    ) : (
                      <>
                        <BotIcon size={15} color="var(--accent-cyan)" />
                        <span style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>DFRAG LEGAL AI</span>
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
                      {copiedIdx === idx ? <CheckIcon size={13} color="var(--defense-pass)" /> : <CopyIcon size={13} />}
                    </button>

                    {msg.role === 'assistant' && (
                      <button
                        type="button"
                        onClick={() => handleSpeak(msg.content, idx)}
                        style={{
                          background: speakingIdx === idx ? 'rgba(0, 210, 180, 0.15)' : 'none',
                          border: 'none',
                          color: speakingIdx === idx ? 'var(--accent-cyan)' : 'var(--text-muted)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.72rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
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
                <p style={{ fontSize: '0.95rem', lineHeight: '1.65', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </p>

                {/* Blocked Shield Warning */}
                {msg.blocked_by && (
                  <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--defense-block)', borderRadius: '8px', color: 'var(--defense-block)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
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

            {isGenerating && (
              <div
                style={{
                  alignSelf: 'flex-start',
                  maxWidth: '88%',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '12px',
                  padding: '14px 20px',
                  boxShadow: 'var(--shadow-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: 'var(--text-secondary)',
                  fontSize: '0.88rem',
                }}
              >
                <BotIcon size={16} color="var(--accent-cyan)" />
                <span className="pulse-text">DFrag Legal AI is searching statutory memory & generating response...</span>
              </div>
            )}

            {/* Bottom Floating Command Input */}
            <div style={{ marginTop: '16px', paddingTop: '8px' }}>
              <CommandInput
                onSendMessage={onSendMessage}
                sessionId={sessionId}
                onUploadSuccess={onUploadSuccess}
                isGenerating={isGenerating}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
