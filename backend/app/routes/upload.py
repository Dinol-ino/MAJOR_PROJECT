import os
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.schemas import UploadResponse
from app.config import settings
from app.defense.audit_log import AuditLogger
from app.ingestion.pdf_extract import PDFExtractor
from app.retrieval.tier2_user import Tier2UserRetrieval

router = APIRouter(tags=["upload"])
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)
pdf_extractor = PDFExtractor(max_size_mb=settings.MAX_FILE_SIZE_MB, max_pages=settings.MAX_FILE_PAGES)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)


@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...), session_id: str = Form(...)):
    # Log pdf upload event in hash-chained SQLite db
    audit_logger.log(action=f"upload_pdf:{file.filename}", layer=None)
    
    if not file.filename.lower().endswith(".pdf"):
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=file.filename,
            reason="Uploaded file must be a PDF."
        )
        
    try:
        fd, temp_file_path = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as tmp:
                content = await file.read()
                tmp.write(content)
            
            text = pdf_extractor.extract_text(temp_file_path)
            chunks_added = tier2_retriever.add_documents(session_id, file.filename, text)
            
            return UploadResponse(
                status="ok",
                chunks_added=chunks_added,
                filename=file.filename,
                reason=None
            )
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    except Exception as exc:
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=file.filename,
            reason=str(exc)
        )


@router.post("/upload/batch")
async def upload_batch_endpoint(files: List[UploadFile] = File(...), session_id: str = Form(...)):
    """
    Multi-file batch upload endpoint. Ingests up to dynamic upload limits.
    """
    total_chunks = 0
    results = []

    for file in files:
        audit_logger.log(action=f"upload_batch_pdf:{file.filename}", layer=None)
        if not file.filename.lower().endswith(".pdf"):
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "chunks_added": 0,
                "reason": "Must be a PDF file."
            })
            continue

        try:
            fd, temp_file_path = tempfile.mkstemp(suffix=".pdf")
            try:
                with os.fdopen(fd, "wb") as tmp:
                    content = await file.read()
                    tmp.write(content)
                
                text = pdf_extractor.extract_text(temp_file_path)
                chunks_added = tier2_retriever.add_documents(session_id, file.filename, text)
                total_chunks += chunks_added
                results.append({
                    "filename": file.filename,
                    "status": "ok",
                    "chunks_added": chunks_added,
                    "reason": None
                })
            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
        except Exception as exc:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "chunks_added": 0,
                "reason": str(exc)
            })

    return {
        "status": "ok",
        "total_files": len(files),
        "total_chunks": total_chunks,
        "files_processed": results
    }
