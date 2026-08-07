import React, { useState } from 'react';
import CommandInput from './CommandInput';
import SourcesPanel from './SourcesPanel';
import { ScaleIcon, ShieldAlertIcon, UserIcon, BotIcon, Volume2Icon } from './Icons';

export default function ChatWindow({ messages, onSendMessage, sessionId, onUploadSuccess }) {
  const [speakingIdx, setSpeakingIdx] = useState(null);

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

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: '#121214' }}>
      {/* Messages / Canvas Container */}
      <div style={{ flex: 1, padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {messages.length === 0 ? (
          /* Manus AI Hero Centered Canvas */
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: '40px 20px' }}>
            <h1 style={{ fontFamily: 'Georgia, serif', fontSize: '2.8rem', fontWeight: 400, color: '#f8fafc', marginBottom: '32px', letterSpacing: '-0.02em' }}>
              What can I do for you?
            </h1>

            <CommandInput onSendMessage={onSendMessage} sessionId={sessionId} onUploadSuccess={onUploadSuccess} />
          </div>
        ) : (
          /* Conversation Stream */
          <div style={{ maxWidth: '820px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  background: msg.role === 'user' ? 'rgba(99, 102, 241, 0.15)' : '#1e1e22',
                  border: `1px solid ${msg.role === 'user' ? 'rgba(99, 102, 241, 0.3)' : '#27272a'}`,
                  borderRadius: '12px',
                  padding: '16px 20px',
                  boxShadow: '0 10px 20px rgba(0,0,0,0.3)',
                }}
              >
                {/* Message Header */}
                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {msg.role === 'user' ? (
                      <>
                        <UserIcon size={14} color="var(--accent-color)" /> You
                      </>
                    ) : (
                      <>
                        <BotIcon size={14} color="var(--safe-color)" /> DFrag Legal AI
                      </>
                    )}
                  </div>

                  {/* Text-to-Speech (TTS) Audio Playback Button for AI answers */}
                  {msg.role === 'assistant' && (
                    <button
                      type="button"
                      onClick={() => handleSpeak(msg.content, idx)}
                      style={{
                        background: speakingIdx === idx ? 'rgba(99, 102, 241, 0.2)' : 'none',
                        border: 'none',
                        color: speakingIdx === idx ? 'var(--accent-color)' : '#64748b',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        padding: '2px 6px',
                        borderRadius: '4px',
                      }}
                      title={speakingIdx === idx ? 'Stop audio' : 'Listen to response'}
                    >
                      <Volume2Icon size={14} />
                      <span>{speakingIdx === idx ? 'Playing...' : 'TTS'}</span>
                    </button>
                  )}
                </div>

                {/* Message Text Content */}
                <p style={{ fontSize: '0.96rem', lineHeight: '1.6', color: '#f8fafc', whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </p>

                {/* Blocked Shield Warning */}
                {msg.blocked_by && (
                  <div style={{ marginTop: '10px', padding: '10px 12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger-color)', borderRadius: '6px', color: 'var(--danger-color)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldAlertIcon size={16} />
                    <span>Blocked by {msg.blocked_by.toUpperCase()} Guard - {msg.block_reason}</span>
                  </div>
                )}

                {/* Citation Sources Panel */}
                {!msg.blocked_by && msg.sources && msg.sources.length > 0 && (
                  <SourcesPanel sources={msg.sources} />
                )}
              </div>
            ))}

            {/* Bottom floating Command Input when messages exist */}
            <div style={{ marginTop: '20px', paddingTop: '10px' }}>
              <CommandInput onSendMessage={onSendMessage} sessionId={sessionId} onUploadSuccess={onUploadSuccess} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
