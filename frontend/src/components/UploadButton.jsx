import React, { useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { UploadIcon, CheckIcon } from './Icons';

export default function UploadButton({ sessionId, onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState(null);

  const handleFileChange = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    const nonPdf = files.find((f) => !f.name.toLowerCase().endsWith('.pdf') && f.type !== 'application/pdf');
    if (nonPdf) {
      alert(`File '${nonPdf.name}' is not a PDF. Only PDF documents are supported for statutory analysis.`);
      return;
    }

    setIsUploading(true);
    setUploadSuccessMsg(null);

    try {
      if (files.length === 1) {
        const response = await apiClient.upload(files[0], sessionId);
        if (response.status === 'ok') {
          setUploadSuccessMsg(`+${response.chunks_added} chunks`);
          setTimeout(() => setUploadSuccessMsg(null), 3000);
          if (onUploadSuccess) onUploadSuccess(response);
        } else {
          alert(`Failed to ingest file: ${response.reason}`);
        }
      } else {
        const response = await apiClient.uploadBatch(files, sessionId);
        if (response.status === 'ok') {
          setUploadSuccessMsg(`${response.total_files} PDFs (+${response.total_chunks} chunks)`);
          setTimeout(() => setUploadSuccessMsg(null), 3500);
          if (onUploadSuccess) onUploadSuccess(response);
        } else {
          alert(`Batch upload status: ${response.status}`);
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      alert(`Error uploading document(s): ${err.message}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf"
        multiple
        style={{ display: 'none' }}
      />
      <button
        type="button"
        disabled={isUploading}
        onClick={() => fileInputRef.current?.click()}
        style={{
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid var(--border-medium)',
          borderRadius: '20px',
          padding: '6px 14px',
          color: uploadSuccessMsg ? 'var(--defense-pass)' : 'var(--text-secondary)',
          fontSize: '0.8rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s ease',
        }}
      >
        {uploadSuccessMsg ? (
          <>
            <CheckIcon size={14} color="var(--defense-pass)" />
            <span>{uploadSuccessMsg}</span>
          </>
        ) : (
          <>
            <UploadIcon size={14} color={isUploading ? 'var(--accent-cyan)' : 'var(--text-muted)'} className={isUploading ? 'pulse-text' : ''} />
            <span>{isUploading ? 'Ingesting PDFs...' : 'Upload PDF(s)'}</span>
          </>
        )}
      </button>
    </div>
  );
}
