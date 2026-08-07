import React, { useState } from 'react';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import { SendIcon, SparklesIcon, FolderIcon, BookIcon } from './Icons';

export default function CommandInput({ onSendMessage, sessionId, onUploadSuccess }) {
  const [input, setInput] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSendMessage(input);
    setInput('');
  };

  const handleSpeechEnd = (transcript) => {
    setInput((prev) => (prev ? prev + ' ' + transcript : transcript));
  };

  const handlePillClick = (promptText) => {
    onSendMessage(promptText);
  };

  return (
    <div style={{ width: '100%', maxWidth: '780px', margin: '0 auto' }}>
      {/* Floating Command Box */}
      <form
        onSubmit={handleSend}
        style={{
          background: '#1e1e22',
          border: '1px solid #27272a',
          borderRadius: '16px',
          padding: '12px 16px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          transition: 'border-color 0.2s ease',
        }}
        className="command-box"
      >
        {/* Main Input Textarea/Input */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Assign a legal task or type / for options"
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#f8fafc',
            fontSize: '1.02rem',
            boxSizing: 'border-box',
          }}
        />

        {/* Input Bar Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
          {/* Left tools: Attachment (+) and Manus Desktop pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <UploadButton sessionId={sessionId} onUploadSuccess={onUploadSuccess} />

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid #27272a',
                borderRadius: '12px',
                padding: '4px 10px',
                fontSize: '0.78rem',
                color: '#94a3b8',
              }}
            >
              <SparklesIcon size={14} color="var(--accent-color)" />
              <span>Legal Copilot Desktop</span>
            </div>
          </div>

          {/* Right tools: STT Voice Mic and Submit Arrow */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <MicButton onSpeechEnd={handleSpeechEnd} />

            <button
              type="submit"
              disabled={!input.trim()}
              style={{
                background: input.trim() ? 'var(--accent-color)' : 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: '50%',
                width: '36px',
                height: '36px',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: input.trim() ? 'pointer' : 'default',
                transition: 'all 0.2s ease',
              }}
            >
              <SendIcon size={16} />
            </button>
          </div>
        </div>
      </form>

      {/* Action Quick Pills below search bar */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          justifyContent: 'center',
          flexWrap: 'wrap',
          marginTop: '16px',
        }}
      >
        <button
          type="button"
          onClick={() => handlePillClick("Analyze IT Act Section 66 penalties and compliance requirements")}
          style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.8rem',
            color: '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
        >
          <BookIcon size={14} /> Analyze Section 66
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("What are the key provisions of Companies Act 2013 regarding director liability?")}
          style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.8rem',
            color: '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
        >
          <FolderIcon size={14} /> Research Companies Act
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("Draft a legal notice for breach of non-disclosure contract")}
          style={{
            background: '#18181b',
            border: '1px solid #27272a',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.8rem',
            color: '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}
        >
          <SparklesIcon size={14} /> Draft Legal Notice
        </button>
      </div>
    </div>
  );
}
