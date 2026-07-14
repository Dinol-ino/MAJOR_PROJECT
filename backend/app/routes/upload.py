import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile

from app.config import settings
from app.defense.audit_log import AuditLogger
from app.ingestion.document_parser import SUPPORTED_EXTENSIONS, UnsupportedDocumentError
from app.ingestion.service import IngestionService
from app.platform.database import get_session_factory
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.schemas import UploadResponse

router = APIRouter(tags=["upload"])
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)


@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...), session_id: str = Form(...)):
    filename = file.filename or "uploaded_document"
    extension = os.path.splitext(filename)[1].lower()
    audit_logger.log(action=f"upload_document:{filename}", layer=None)

    if extension not in SUPPORTED_EXTENSIONS:
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=filename,
            reason="Supported document types are PDF, TXT, and DOCX.",
        )

    fd, temp_file_path = tempfile.mkstemp(suffix=extension)
    try:
        with os.fdopen(fd, "wb") as tmp:
            content = await file.read()
            tmp.write(content)

        SessionLocal = get_session_factory()
        with SessionLocal() as db_session:
            ingestion_service = IngestionService(db_session)
            page_index = ingestion_service.ingest_file(
                temp_file_path,
                filename=filename,
            )

        chunks_added = len(page_index.chunks)
        if settings.CHROMA_LEGACY_ENABLED:
            chunks_added = tier2_retriever.add_documents(
                session_id,
                filename,
                "\n\n".join(chunk.text for chunk in page_index.chunks),
            )

        return UploadResponse(
            status="ok",
            chunks_added=chunks_added,
            filename=filename,
            reason=None,
        )
    except (UnsupportedDocumentError, ImportError, ValueError) as exc:
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=filename,
            reason=str(exc),
        )
    except Exception as exc:
        audit_logger.log(
            action=f"upload_failed:{filename}:{type(exc).__name__}",
            layer=None,
        )
        return UploadResponse(
            status="rejected",
            chunks_added=0,
            filename=filename,
            reason="Document ingestion failed.",
        )
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)