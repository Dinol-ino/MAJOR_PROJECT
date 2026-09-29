import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import MicButton from './MicButton';
import UploadButton from './UploadButton';
import FilePill from './FilePill';
import ContextMeter from './ContextMeter';
import { SendIcon, SparklesIcon } from './Icons';

export default function CommandInput({
  onSendMessage,
  sessionId,
  onUploadSuccess,
  isGenerating,
  activeVaultId,
  lastMetrics = null,
}) {
  const [input, setInput] = useState('');
  // LOW / MEDIUM / HIGH map to real server-side budgets (retrieval depth, evidence, output length, verification).
  const [reasoningEffort, setReasoningEffort] = useState('medium');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [suggestions, setSuggestions] = useState([]);

  // Suggestions are built from what is actually indexed, never from hardcoded statutes.
  useEffect(() => {
    let active = true;
    apiClient.getCorpusStatus().then((c) => {
      if (!active) return;
      const acts = (c.acts || []).filter((a) => a.sections && a.sections.length);
      const out = [];
      if (acts[0]) {
        const sec = acts[0].sections.find((x) => /^\d/.test(String(x))) || acts[0].sections[0];
        out.push({ label: `${acts[0].act_name}, s. ${sec}`, prompt: `What does Section ${sec} of the ${acts[0].act_name} provide?` });
        out.push({ label: `Penalties in ${acts[0].act_name}`, prompt: `Which provisions of the ${acts[0].act_name} prescribe penalties, and what are they?` });
      }
      if (acts[1]) out.push({ label: acts[1].act_name, prompt: `Summarise the key provisions of the ${acts[1].act_name}.` });
      setSuggestions(out.slice(0, 3));
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  const cycleReasoningEffort = () => {
    setReasoningEffort((prev) => (prev === 'low' ? 'medium' : prev === 'medium' ? 'high' : 'low'));
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
      {/* Context use of the LAST answer, from the server's own measurements (hidden until one exists). */}
      {lastMetrics && lastMetrics.max_context_tokens && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px', paddingRight: '4px' }}>
          <ContextMeter metrics={lastMetrics} />
        </div>
      )}

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
                    ? 'rgba(255, 0, 127, 0.15)'
                    : reasoningEffort === 'low'
                    ? 'rgba(0, 132, 255, 0.15)'
                    : 'var(--bg-raised)',
                border: `1px solid ${
                  reasoningEffort === 'high'
                    ? 'var(--accent-pink)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-blue)'
                    : 'var(--border-subtle)'
                }`,
                borderRadius: '16px',
                padding: '4px 10px',
                fontSize: '0.74rem',
                fontWeight: 600,
                color:
                  reasoningEffort === 'high'
                    ? 'var(--accent-pink)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-blue)'
                    : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              title="Reasoning level sets the retrieval depth, evidence volume, answer length and verification retries (click to cycle Low / Medium / High)"
            >
              <SparklesIcon
                size={12}
                color={
                  reasoningEffort === 'high'
                    ? 'var(--accent-pink)'
                    : reasoningEffort === 'low'
                    ? 'var(--accent-blue)'
                    : 'currentColor'
                }
              />
              <span>
                {`Reasoning: ${reasoningEffort.charAt(0).toUpperCase()}${reasoningEffort.slice(1)}`}
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

      {suggestions.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '14px' }}>
          {suggestions.map((sg) => (
            <button
              key={sg.label}
              type="button"
              onClick={() => handlePillClick(sg.prompt)}
              style={{ background: 'transparent', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', padding: '5px 12px', fontSize: '0.78rem', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              {sg.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
