import React, { useState } from 'react';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import { SendIcon, BookIcon, FolderIcon, SparklesIcon, ScaleIcon } from './Icons';

export default function CommandInput({ onSendMessage, sessionId, onUploadSuccess, isGenerating }) {
  const [input, setInput] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    onSendMessage(input);
    setInput('');
  };

  const handleSpeechEnd = (transcript) => {
    setInput((prev) => (prev ? prev + ' ' + transcript : transcript));
  };

  const handlePillClick = (promptText) => {
    if (isGenerating) return;
    onSendMessage(promptText);
  };

  return (
    <div style={{ width: '100%', maxWidth: '760px', margin: '0 auto' }}>
      {/* Floating Command Box */}
      <form
        onSubmit={handleSend}
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-medium)',
          borderRadius: '16px',
          padding: '14px 18px',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          transition: 'border-color 0.2s ease',
          opacity: isGenerating ? 0.7 : 1,
        }}
        className="glow-pill"
      >
        {/* Main Input Textarea */}
        <input
          type="text"
          value={input}
          disabled={isGenerating}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isGenerating ? "Legal AI is generating response..." : "Ask a legal question, analyze statutes, or research case law..."}
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontSize: '1rem',
            boxSizing: 'border-box',
          }}
        />

        {/* Input Bar Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
          {/* Left tools: Upload PDF(s) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <UploadButton sessionId={sessionId} onUploadSuccess={onUploadSuccess} />
          </div>

          {/* Right tools: STT Voice Mic and Submit Arrow */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <MicButton onSpeechEnd={handleSpeechEnd} />

            <button
              type="submit"
              disabled={!input.trim() || isGenerating}
              style={{
                background: (input.trim() && !isGenerating) ? 'var(--accent-gradient)' : 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: '50%',
                width: '36px',
                height: '36px',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: (input.trim() && !isGenerating) ? 'pointer' : 'default',
                transition: 'all 0.2s ease',
                boxShadow: (input.trim() && !isGenerating) ? 'var(--shadow-sm)' : 'none',
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
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <BookIcon size={14} color="var(--accent-cyan)" /> Analyze Section 66
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("What are the key provisions of Companies Act 2013 regarding director liability and fraud under Section 447?")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <ScaleIcon size={14} color="var(--accent-blue)" /> Research Companies Act
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("Draft a legal notice for breach of non-disclosure contract under Indian Contract Act Section 73")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <SparklesIcon size={14} color="var(--accent-indigo)" /> Draft Legal Notice
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("Explain cheating and forgery offences under Bharatiya Nyaya Sanhita (BNS 2023) Section 318")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '20px',
            padding: '6px 14px',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <FolderIcon size={14} color="var(--defense-pass)" /> BNS 2023 Cheating
        </button>
      </div>
    </div>
  );
}
