import React, { useState } from 'react';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import FilePill from './FilePill';
import ContextMeter from './ContextMeter';
import { SendIcon, BookIcon, FolderIcon, SparklesIcon, ScaleIcon } from './Icons';

export default function CommandInput({
  onSendMessage,
  sessionId,
  onUploadSuccess,
  isGenerating,
  activeVaultId,
  usedTokens = 4200,
  maxTokens = 32768
}) {
  const [input, setInput] = useState('');
  const [reasoningEffort, setReasoningEffort] = useState('off'); // 'off' | 'low' | 'high'
  const [attachedFiles, setAttachedFiles] = useState([]);

  const cycleReasoningEffort = () => {
    setReasoningEffort((prev) => {
      if (prev === 'off') return 'low';
      if (prev === 'low') return 'high';
      return 'off';
    });
  };

  const isAnyFileIndexing = attachedFiles.some(
    (f) => f.status === 'uploading' || f.status === 'indexing'
  );

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isGenerating || isAnyFileIndexing) return;
    onSendMessage(input, reasoningEffort);
    setInput('');
  };

  const handleSpeechEnd = (transcript) => {
    setInput((prev) => (prev ? prev + ' ' + transcript : transcript));
  };

  const handlePillClick = (promptText) => {
    if (isGenerating || isAnyFileIndexing) return;
    onSendMessage(promptText, reasoningEffort);
  };

  const handleFileStatusUpdate = (fileInfo) => {
    setAttachedFiles((prev) => {
      const idx = prev.findIndex((f) => f.name === fileInfo.name);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...fileInfo };
        return next;
      }
      return [...prev, fileInfo];
    });
  };

  const handleRemoveFile = (fileOrId) => {
    setAttachedFiles((prev) =>
      prev.filter((f) => (f.id ? f.id !== fileOrId : f.name !== (fileOrId.name || fileOrId)))
    );
  };

  return (
    <div style={{ width: '100%', maxWidth: 'var(--max-content-width)', margin: '0 auto' }}>
      {/* Context Window Indicator Bar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px', paddingRight: '4px' }}>
        <ContextMeter
          usedTokens={usedTokens}
          maxTokens={maxTokens}
          breakdown={{
            history: Math.round(usedTokens * 0.55),
            documents: Math.round(usedTokens * 0.3),
            system: Math.round(usedTokens * 0.15)
          }}
        />
      </div>

      {/* Floating Command Box */}
      <form
        onSubmit={handleSend}
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-lg)',
          padding: '14px 18px',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          transition: 'border-color 0.15s ease-out',
          opacity: isGenerating ? 0.75 : 1
        }}
      >
        {/* Case File Attachment Pills */}
        {attachedFiles.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', paddingBottom: '4px' }}>
            {attachedFiles.map((file) => (
              <FilePill
                key={file.id || file.name}
                file={file}
                onRemove={handleRemoveFile}
                onRetry={() => {
                  handleFileStatusUpdate({ ...file, status: 'indexing', progress: 10 });
                }}
              />
            ))}
          </div>
        )}

        {/* Main Input Field */}
        <input
          type="text"
          value={input}
          disabled={isGenerating}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            isGenerating
              ? "Synthesizing legal analysis with citation grounding..."
              : isAnyFileIndexing
              ? "Indexing attached case documents..."
              : "Ask a legal question, research statutes, or cross-examine case evidence..."
          }
          style={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontSize: '0.98rem',
            boxSizing: 'border-box'
          }}
        />

        {/* Input Bar Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
          {/* Left tools: Upload PDF(s) + Reasoning Effort Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <UploadButton
              sessionId={sessionId}
              activeVaultId={activeVaultId}
              onUploadSuccess={(doc) => {
                handleFileStatusUpdate({
                  name: doc.filename || 'Uploaded Document',
                  status: 'ready',
                  progress: 100,
                  page_count: doc.pages || doc.page_count
                });
                if (onUploadSuccess) onUploadSuccess(doc);
              }}
            />

            <button
              type="button"
              onClick={cycleReasoningEffort}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                background:
                  reasoningEffort === 'high'
                    ? 'rgba(79, 140, 255, 0.15)'
                    : reasoningEffort === 'low'
                    ? 'rgba(0, 210, 180, 0.12)'
                    : 'var(--bg-raised)',
                border: `1px solid ${
                  reasoningEffort === 'high'
                    ? 'var(--accent)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-cyan)'
                    : 'var(--border-subtle)'
                }`,
                borderRadius: '16px',
                padding: '4px 10px',
                fontSize: '0.74rem',
                fontWeight: 600,
                color:
                  reasoningEffort === 'high'
                    ? 'var(--accent)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-cyan)'
                    : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              title={`Reasoning Effort: ${reasoningEffort.toUpperCase()} (Cycle OFF / LOW / HIGH Deep Thinking)`}
            >
              <SparklesIcon
                size={12}
                color={
                  reasoningEffort === 'high'
                    ? 'var(--accent)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-cyan)'
                    : 'currentColor'
                }
              />
              <span>
                {reasoningEffort === 'high'
                  ? 'Reasoning: HIGH (Deep)'
                  : reasoningEffort === 'low'
                  ? 'Reasoning: LOW'
                  : 'Reasoning: OFF'}
              </span>
            </button>
          </div>

          {/* Right tools: STT Voice Mic and Submit Arrow */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MicButton onSpeechEnd={handleSpeechEnd} />

            <button
              type="submit"
              disabled={!input.trim() || isGenerating || isAnyFileIndexing}
              style={{
                background:
                  input.trim() && !isGenerating && !isAnyFileIndexing
                    ? 'var(--accent)'
                    : 'var(--bg-raised)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '50%',
                width: '34px',
                height: '34px',
                color: input.trim() && !isGenerating && !isAnyFileIndexing ? '#ffffff' : 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: input.trim() && !isGenerating && !isAnyFileIndexing ? 'pointer' : 'not-allowed',
                boxShadow: input.trim() && !isGenerating ? 'var(--shadow-sm)' : 'none'
              }}
              title={isAnyFileIndexing ? 'Still indexing — please wait' : 'Submit query (Enter)'}
            >
              <SendIcon size={15} />
            </button>
          </div>
        </div>
      </form>

      {/* Action Quick Suggestion Pills */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          justifyContent: 'center',
          flexWrap: 'wrap',
          marginTop: '14px'
        }}
      >
        <button
          type="button"
          onClick={() => handlePillClick("Analyze IT Act Section 66 penalties and compliance requirements")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '16px',
            padding: '5px 12px',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <BookIcon size={13} color="var(--accent-cyan)" /> Analyze Section 66
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("What are the key provisions of Companies Act 2013 regarding director liability under Section 447?")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '16px',
            padding: '5px 12px',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <ScaleIcon size={13} color="var(--accent-blue)" /> Research Companies Act
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("Draft a legal notice for breach of non-disclosure contract under Indian Contract Act Section 73")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '16px',
            padding: '5px 12px',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <SparklesIcon size={13} color="var(--accent)" /> Draft Legal Notice
        </button>

        <button
          type="button"
          onClick={() => handlePillClick("Explain cheating and forgery offences under Bharatiya Nyaya Sanhita (BNS 2023) Section 318")}
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '16px',
            padding: '5px 12px',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <FolderIcon size={13} color="var(--status-green)" /> BNS 2023 Cheating
        </button>
      </div>
    </div>
  );
}
