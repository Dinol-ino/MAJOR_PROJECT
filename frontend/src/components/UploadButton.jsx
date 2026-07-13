import React, { useRef, useState } from 'react';
import { apiClient } from '../api/client';

export default function UploadButton({ sessionId, onUploadSuccess }) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      alert('Only PDF files are supported.');
      return;
    }

    setIsUploading(true);
    try {
      const response = await apiClient.upload(file, sessionId);
      if (response.status === 'ok') {
        alert(`Successfully ingested PDF: ${file.name}. Chunks added: ${response.chunks_added}`);
        if (onUploadSuccess) onUploadSuccess(response);
      } else {
        alert(`Failed to ingest file: ${response.reason}`);
      }
    } catch (err) {
      console.error(err);
      alert('Error uploading document.');
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
          align_items: 'center',
          gap: '8px',
        }}
      >
        <span>📁</span>
        <span>{isUploading ? 'Ingesting PDF...' : 'Upload PDF'}</span>
      </button>
    </div>
  );
}
