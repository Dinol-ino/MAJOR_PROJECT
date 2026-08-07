import React, { useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { UploadIcon } from './Icons';

export default function UploadButton({ sessionId, onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    const nonPdf = files.find((f) => !f.name.toLowerCase().endsWith('.pdf') && f.type !== 'application/pdf');
    if (nonPdf) {
      alert(`File '${nonPdf.name}' is not a PDF. Only PDF files are supported.`);
      return;
    }

    setIsUploading(true);
    try {
      if (files.length === 1) {
        const response = await apiClient.upload(files[0], sessionId);
        if (response.status === 'ok') {
          alert(`Successfully ingested PDF: ${files[0].name}. Chunks added: ${response.chunks_added}`);
          if (onUploadSuccess) onUploadSuccess(response);
        } else {
          alert(`Failed to ingest file: ${response.reason}`);
        }
      } else {
        const response = await apiClient.uploadBatch(files, sessionId);
        if (response.status === 'ok') {
          alert(`Successfully ingested ${response.total_files} PDF files! Total chunks added: ${response.total_chunks}`);
          if (onUploadSuccess) onUploadSuccess(response);
        } else {
          alert(`Batch upload status: ${response.status}`);
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      alert('Error uploading document(s).');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="upload-container">
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
        className="upload-button"
        style={{
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid var(--panel-border)',
          borderRadius: '8px',
          padding: '10px 16px',
          color: 'var(--text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
        }}
      >
        <UploadIcon size={16} color="var(--accent-color)" />
        <span>{isUploading ? 'Ingesting PDFs...' : 'Upload PDF(s)'}</span>
      </button>
    </div>
  );
}
