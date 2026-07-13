from fastapi import APIRouter, UploadFile, File, Form
from app.schemas import UploadResponse
from app.config import settings
from app.defense.audit_log import AuditLogger

router = APIRouter(tags=["upload"])
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)

@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...), session_id: str = Form(...)):
    # Log pdf upload event in hash-chained SQLite db
    audit_logger.log(action=f"upload_pdf:{file.filename}", layer=None)
    
    # Stub implementation for Phase 0 / Phase 1
    # Sweedan will wire this to PDFExtractor and SectionAwareChunker in Phase 2
    return UploadResponse(
        status="ok",
        chunks_added=12,
        filename=file.filename,
        reason=None
    )
