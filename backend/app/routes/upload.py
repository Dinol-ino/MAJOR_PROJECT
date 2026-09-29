import os
import tempfile
from typing import List
import hashlib
from typing import Dict
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.routes.auth import get_current_user
from app.security.ownership import conversation_accessible
from app.db.engine import get_sync_session
from app.schemas import UploadResponse
from app.config import settings
from app.defense.audit_log import AuditLogger
from app.memory.durable_memory import DurableMemoryManager
from app.security.pdf_sanitizer import pdf_sanitizer
from app.retrieval.tier2_user import Tier2UserRetrieval

from app.events import DocumentIngested, emit_document_ingested

router = APIRouter(tags=["upload"])
audit_logger = AuditLogger()
durable_memory = DurableMemoryManager()
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)

_MAX_BATCH_FILES = int(os.getenv("UPLOAD_MAX_BATCH_FILES", "10"))


def _name_fingerprint(filename: str) -> str:
    """Audit-safe reference to a filename (names of legal documents can themselves be confidential)."""
    return hashlib.sha256((filename or "").encode("utf-8")).hexdigest()[:12]


async def _read_bounded(file: UploadFile) -> bytes:
    """Reads an upload in chunks and rejects it as soon as it exceeds MAX_FILE_SIZE_MB (no unbounded buffering)."""
    limit = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    buf = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(status_code=413, detail=f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit.")
    return bytes(buf)


def _require_session_access(session_id: str, current_user: Dict) -> None:
    with get_sync_session() as db:
        if not conversation_accessible(db, session_id, current_user):
            raise HTTPException(status_code=404, detail="Conversation not found.")


@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...), session_id: str = Form(...), current_user: Dict = Depends(get_current_user)):
    _require_session_access(session_id, current_user)
    audit_logger.log(action=f"upload_pdf:{_name_fingerprint(file.filename)}", layer=None)
    
    if not file.filename.lower().endswith(".pdf"):
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=file.filename,
            reason="Uploaded file must be a PDF."
        )
        
    try:
        content = await _read_bounded(file)
        text, metadata = pdf_sanitizer.extract_clean_text(content)
        chunks_added = tier2_retriever.add_documents(session_id, file.filename, text)
        
        # Persist document metadata in PostgreSQL / SQLite DocumentMemory
        doc_id = f"doc_{session_id[:8]}_{file.filename}"
        durable_memory.save_document_memory(
            doc_id=doc_id,
            session_id=session_id,
            filename=file.filename,
            file_size_bytes=len(content),
            chunk_count=chunks_added,
            metadata_json={"source": "single_upload", "pages": metadata.get("total_pages")}
        )

        # Emit DocumentIngested event (Module 9 §9.2 Event 2)
        emit_document_ingested(DocumentIngested(
            doc_id=doc_id,
            session_id=session_id,
            filename=file.filename,
            file_size_bytes=len(content),
            chunk_count=chunks_added,
            pages_count=metadata.get("total_pages", 1)
        ))

        return UploadResponse(
            status="ok",
            chunks_added=chunks_added,
            filename=file.filename,
            reason=None
        )
    except HTTPException:
        raise
    except Exception as exc:
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=file.filename,
            reason=f"Document could not be processed safely ({type(exc).__name__})."
        )


@router.post("/upload/batch")
async def upload_batch_endpoint(files: List[UploadFile] = File(...), session_id: str = Form(...), current_user: Dict = Depends(get_current_user)):
    """
    Multi-file batch upload endpoint (bounded file count and per-file size).
    """
    _require_session_access(session_id, current_user)
    if len(files) > _MAX_BATCH_FILES:
        raise HTTPException(status_code=413, detail=f"At most {_MAX_BATCH_FILES} files per batch.")
    total_chunks = 0
    results = []

    for file in files:
        audit_logger.log(action=f"upload_batch_pdf:{_name_fingerprint(file.filename)}", layer=None)
        if not file.filename.lower().endswith(".pdf"):
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "chunks_added": 0,
                "reason": "Must be a PDF file."
            })
            continue

        try:
            content = await _read_bounded(file)
            text, metadata = pdf_sanitizer.extract_clean_text(content)
            chunks_added = tier2_retriever.add_documents(session_id, file.filename, text)
            total_chunks += chunks_added

            # Persist document metadata in PostgreSQL / SQLite DocumentMemory
            doc_id = f"doc_{session_id[:8]}_{file.filename}"
            durable_memory.save_document_memory(
                doc_id=doc_id,
                session_id=session_id,
                filename=file.filename,
                file_size_bytes=len(content),
                chunk_count=chunks_added,
                metadata_json={"source": "batch_upload", "pages": metadata.get("total_pages")}
            )

            # Emit DocumentIngested event (Module 9 §9.2 Event 2)
            emit_document_ingested(DocumentIngested(
                doc_id=doc_id,
                session_id=session_id,
                filename=file.filename,
                file_size_bytes=len(content),
                chunk_count=chunks_added,
                pages_count=metadata.get("total_pages", 1)
            ))

            results.append({
                "filename": file.filename,
                "status": "ok",
                "chunks_added": chunks_added,
                "reason": None
            })
        except HTTPException as exc:
            results.append({"filename": file.filename, "status": "rejected", "chunks_added": 0, "reason": exc.detail})
        except Exception as exc:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "chunks_added": 0,
                "reason": f"Document could not be processed safely ({type(exc).__name__})."
            })

    return {
        "status": "ok",
        "total_files": len(files),
        "total_chunks": total_chunks,
        "files_processed": results
    }


@router.get("/memory/documents/{session_id}")
async def get_session_documents(session_id: str):
    """
    Returns stored document metadata memory for a specific research/task session.
    """
    documents = durable_memory.get_session_documents(session_id=session_id)
    return {"session_id": session_id, "documents": documents}
