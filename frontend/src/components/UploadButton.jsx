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
    <div>
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
        className="btn-icon"
        title={isUploading ? 'Uploading...' : 'Upload PDF document'}
        style={{
          opacity: isUploading ? 0.5 : 1,
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" x2="12" y1="3" y2="15"/>
        </svg>
      </button>
    </div>
  );
}
