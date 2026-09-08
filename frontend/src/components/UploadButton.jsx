import React, { useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { UploadIcon, CheckIcon } from './Icons';

export default function UploadButton({ sessionId, onUploadSuccess, activeVaultId }) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // { filename, status, progress, error, pages }

  const pollStatus = async (vaultId, docId, filename) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const s = await apiClient.getVaultDocumentStatus(vaultId, docId);
        setUploadStatus({
          filename,
          status: s.status,
          progress: s.progress,
          error: s.error,
          pages: s.pages,
        });

        if (s.status === 'ready' || s.status === 'failed' || attempts > 60) {
          clearInterval(interval);
          setIsUploading(false);
          if (s.status === 'ready' && onUploadSuccess) {
            onUploadSuccess(s);
          }
        }
      } catch (err) {
        console.warn("Poll status error:", err);
        if (attempts > 10) {
          clearInterval(interval);
          setIsUploading(false);
        }
      }
    }, 1000);
  };

  const handleFileChange = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    const nonPdf = files.find((f) => !f.name.toLowerCase().endsWith('.pdf') && f.type !== 'application/pdf');
    if (nonPdf) {
      alert(`File '${nonPdf.name}' is not a PDF. Only PDF documents are supported for statutory analysis.`);
      return;
    }

    setIsUploading(true);
    setUploadStatus(null);

    try {
      if (activeVaultId) {
        // Vault-scoped persistent ingestion (Spec 01 §4)
        for (const file of files) {
          const res = await apiClient.uploadVaultDocument(activeVaultId, file);
          if (res.duplicate) {
            setUploadStatus({
              filename: file.name,
              status: 'ready',
              progress: 100,
              duplicate: true,
            });
            setIsUploading(false);
          } else {
            setUploadStatus({
              filename: file.name,
              status: 'pending',
              progress: 0,
            });
            pollStatus(activeVaultId, res.document_id, file.name);
          }
        }
      } else {
        // Session fallback
        if (files.length === 1) {
          const response = await apiClient.upload(files[0], sessionId);
          if (response.status === 'ok') {
            setUploadStatus({
              filename: files[0].name,
              status: 'ready',
              progress: 100,
              chunks: response.chunks_added,
            });
            setTimeout(() => setUploadStatus(null), 4000);
            if (onUploadSuccess) onUploadSuccess(response);
          } else {
            alert(`Failed to ingest file: ${response.reason}`);
          }
        } else {
          const response = await apiClient.uploadBatch(files, sessionId);
          if (response.status === 'ok') {
            setUploadStatus({
              filename: `${files.length} PDFs`,
              status: 'ready',
              progress: 100,
              chunks: response.total_chunks,
            });
            setTimeout(() => setUploadStatus(null), 4000);
            if (onUploadSuccess) onUploadSuccess(response);
          } else {
            alert(`Batch upload status: ${response.status}`);
          }
        }
        setIsUploading(false);
      }
    } catch (err) {
      console.error("Upload error:", err);
      setUploadStatus({
        filename: files[0]?.name || 'Upload',
        status: 'failed',
        error: err.message,
      });
      setIsUploading(false);
    } finally {
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
          background: uploadStatus?.status === 'ready'
            ? 'rgba(16, 185, 129, 0.12)'
            : uploadStatus?.status === 'failed'
            ? 'rgba(239, 68, 68, 0.12)'
            : uploadStatus
            ? 'rgba(0, 210, 180, 0.12)'
            : 'rgba(255, 255, 255, 0.05)',
          border: uploadStatus?.status === 'ready'
            ? '1px solid rgba(16, 185, 129, 0.3)'
            : uploadStatus?.status === 'failed'
            ? '1px solid rgba(239, 68, 68, 0.3)'
            : uploadStatus
            ? '1px solid rgba(0, 210, 180, 0.3)'
            : '1px solid var(--border-medium)',
          borderRadius: '20px',
          padding: '6px 14px',
          color: uploadStatus?.status === 'ready'
            ? 'var(--defense-pass)'
            : uploadStatus?.status === 'failed'
            ? 'var(--defense-block)'
            : uploadStatus
            ? 'var(--accent-cyan)'
            : 'var(--text-secondary)',
          fontSize: '0.8rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s ease',
        }}
      >
        {uploadStatus ? (
          uploadStatus.status === 'ready' ? (
            <>
              <CheckIcon size={14} color="var(--defense-pass)" />
              <span>{uploadStatus.filename}: Indexed ✓ {uploadStatus.pages ? `(${uploadStatus.pages}p)` : ''}</span>
            </>
          ) : uploadStatus.status === 'failed' ? (
            <>
              <span style={{ color: 'var(--defense-block)' }}>✗</span>
              <span>Failed ({uploadStatus.error ? uploadStatus.error.slice(0, 20) : 'Error'}) - Retry</span>
            </>
          ) : (
            <>
              <UploadIcon size={14} color="var(--accent-cyan)" className="pulse-text" />
              <span className="pulse-text">{uploadStatus.status.toUpperCase()} {uploadStatus.progress}%</span>
            </>
          )
        ) : (
          <>
            <UploadIcon size={14} color="var(--text-muted)" />
            <span>{activeVaultId ? 'Upload to Vault' : 'Upload PDF(s)'}</span>
          </>
        )}
      </button>
    </div>
  );
}
