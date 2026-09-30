import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends, Query
from pydantic import BaseModel, Field

from app.db.engine import get_sync_session
from app.db.models import utcnow
from app.db.models import ProjectVault, Conversation, DocumentMemory, DocumentPage
from app.services.ingest import ingest_service, compute_file_hash, get_vault_collection_name
from app.services.document_store import document_store, DocumentStoreError
from app.defense.audit_log import AuditLogger
from app.routes.auth import get_current_user
from app.security.ownership import current_user_id, owns

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vaults", tags=["vaults"])
audit_logger = AuditLogger()


def _verify_vault_access(vault: ProjectVault, current_user: Dict[str, Any], write: bool = False) -> None:
    # 404 (not 403) so another user's vault ids are not disclosed. Admins may read across
    # users but never modify or delete a practitioner's privileged matter files (write=True).
    if not owns(vault.user_id, current_user, write=write):
        raise HTTPException(status_code=404, detail="Project vault not found.")


class CreateVaultRequest(BaseModel):
    vault_name: str = Field(..., min_length=1, max_length=255, description="Name of the legal matter / project vault")
    description: Optional[str] = Field(None, max_length=4000, description="Optional case or matter description")


class UpdateVaultRequest(BaseModel):
    vault_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


@router.post("", status_code=201)
def create_vault(req: CreateVaultRequest, current_user: Dict = Depends(get_current_user)):
    """Creates a new durable Project Vault (matter-based container)."""
    effective_user_id = current_user_id(current_user)
    with get_sync_session() as session:
        vault = ProjectVault(
            id=str(uuid.uuid4()),
            user_id=effective_user_id,
            vault_name=req.vault_name.strip(),
            description=req.description.strip() if req.description else None,
        )
        session.add(vault)
        session.flush()
        res = vault.to_dict()

    audit_logger.log(action=f"vault_created:{res['id']}", layer="persistence")
    return res


@router.get("")
def list_vaults(current_user: Dict = Depends(get_current_user)):
    """Lists all active Project Vaults for the user with document and conversation counts."""
    effective_uid = current_user_id(current_user)
    with get_sync_session() as session:
        vaults = (
            session.query(ProjectVault)
            .filter(ProjectVault.user_id == effective_uid, ProjectVault.deleted_at.is_(None))
            .order_by(ProjectVault.updated_at.desc())
            .all()
        )
        data = [v.to_dict() for v in vaults]
    return {"vaults": data, "count": len(data)}


@router.get("/{vault_id}")
def get_vault_details(vault_id: str, current_user: Dict = Depends(get_current_user)):
    """Retrieves vault details, associated conversations, and indexed documents."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id, ProjectVault.deleted_at.is_(None)).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user)

        convs = [c.to_dict() for c in vault.conversations]
        docs = [d.to_dict() for d in vault.documents]
        base_dict = vault.to_dict()

    base_dict["conversations"] = convs
    base_dict["documents"] = docs
    return base_dict


@router.get("/{vault_id}/conversations")
def list_vault_conversations(
    vault_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: Dict = Depends(get_current_user),
):
    """Paginated list of conversations in a specific Project Vault."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id, ProjectVault.deleted_at.is_(None)).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user)

        query = session.query(Conversation).filter(
            Conversation.project_vault_id == vault_id,
            Conversation.user_id == vault.user_id,
        )
        total_count = query.count()
        offset = (page - 1) * limit
        convs = query.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit).all()

        data = []
        for c in convs:
            d = c.to_dict()
            d["message_count"] = len(c.messages)
            data.append(d)

        return {
            "vault_id": vault_id,
            "conversations": data,
            "total_count": total_count,
            "page": page,
            "limit": limit
        }


@router.patch("/{vault_id}")
def update_vault(vault_id: str, req: UpdateVaultRequest, current_user: Dict = Depends(get_current_user)):
    """Renames vault or updates description."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id, ProjectVault.deleted_at.is_(None)).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user, write=True)

        if req.vault_name is not None:
            vault.vault_name = req.vault_name.strip()
        if req.description is not None:
            vault.description = req.description.strip()

        session.flush()
        res = vault.to_dict()

    audit_logger.log(action=f"vault_updated:{vault_id}", layer="persistence")
    return res


@router.delete("/{vault_id}")
def delete_vault(vault_id: str, soft_delete: bool = True, current_user: Dict = Depends(get_current_user)):
    """Soft delete keeps every original and derived record (retention window, recoverable);
    only ``soft_delete=false`` - an explicit permanent delete - removes the stored files."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user, write=True)

        if soft_delete:
            vault.deleted_at = utcnow()
        else:
            session.delete(vault)

    if not soft_delete:
        ingest_service.delete_vault_collection(vault_id)
        document_store.delete_vault(vault_id)
    audit_logger.log(action=f"vault_deleted:{vault_id}", layer="persistence")
    return {"status": "deleted", "vault_id": vault_id, "soft_deleted": soft_delete}


async def _read_upload_bounded(file: UploadFile) -> bytes:
    """Reads an upload in 1 MiB steps and refuses it as soon as it exceeds MAX_FILE_SIZE_MB."""
    from app.config import settings
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


def _run_ingestion(doc_id: str, vault_id: str, filename: str) -> None:
    """Background worker. Reads the original from the canonical store, so it also works
    after a restart, and always records a terminal state."""
    try:
        ingest_service.ingest_document(doc_id=doc_id, vault_id=vault_id, filename=filename)
    except Exception as exc:
        logger.error("Background ingestion unhandled failure for doc %s: %s", doc_id, exc, exc_info=True)
        try:
            ingest_service.update_doc_state(doc_id=doc_id, status="failed", progress=0,
                                            error=f"Ingestion failed: {exc}")
        except Exception as db_err:
            logger.error("Failed to record ingest failure in DB for doc %s: %s", doc_id, db_err)


@router.post("/{vault_id}/documents", status_code=202)
async def upload_vault_document(
    vault_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """
    Uploads a case PDF to a Project Vault.

    The original is written to durable storage before anything else; ingestion (parse,
    chunk, embed, index) then runs in the background and can be repeated at will from
    that file. Returns the document id immediately in the "pending" state.
    """
    from app.config import settings

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF legal documents are supported.")

    content = await _read_upload_bounded(file)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file is not a valid PDF.")

    f_hash = compute_file_hash(content)
    requeue: Optional[Dict[str, Any]] = None
    stored_rel: Optional[str] = None

    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id, ProjectVault.deleted_at.is_(None)).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user, write=True)

        # Enforce per-vault file cap
        if len(vault.documents) >= settings.retrieval.vault_max_files:
            raise HTTPException(
                status_code=400,
                detail=f"Vault file quota reached: maximum {settings.retrieval.vault_max_files} files allowed per project vault."
            )

        existing = (
            session.query(DocumentMemory)
            .filter(DocumentMemory.project_vault_id == vault_id, DocumentMemory.file_hash == f_hash)
            .first()
        )
        if existing:
            if existing.ingest_status == "failed":
                # Same file again after a failure: keep the record, restore the original if it
                # is missing, and retry indexing rather than reporting a dead duplicate.
                if not document_store.exists(existing.storage_path):
                    existing.storage_path = document_store.save(vault_id, existing.doc_id, content)
                existing.ingest_status, existing.ingest_progress, existing.ingest_error = "pending", 0, None
                requeue = {"doc_id": existing.doc_id, "filename": existing.filename}
            else:
                return {
                    "document_id": existing.doc_id,
                    "status": existing.ingest_status,
                    "duplicate": True,
                    "filename": existing.filename,
                    "message": "File already in this vault.",
                }

        if requeue is None:
            doc_id = f"doc_{vault_id[:8]}_{uuid.uuid4().hex[:8]}"
            # The original hits the disk BEFORE its row is committed.
            stored_rel = document_store.save(vault_id, doc_id, content)
            try:
                session.add(DocumentMemory(
                    doc_id=doc_id,
                    session_id=vault_id,
                    project_vault_id=vault_id,
                    filename=file.filename,
                    file_hash=f_hash,
                    file_size_bytes=len(content),
                    vector_ns=get_vault_collection_name(vault_id),
                    ingest_status="pending",
                    ingest_progress=0,
                    storage_path=stored_rel,
                    doc_type="pdf",
                    metadata_json={"source": "vault_upload", "original_filename": file.filename,
                                   "uploaded_by": current_user_id(current_user)},
                ))
                session.flush()
            except Exception:
                document_store.delete_document(stored_rel)
                raise
            requeue = {"doc_id": doc_id, "filename": file.filename}

    background_tasks.add_task(_run_ingestion, requeue["doc_id"], vault_id, requeue["filename"])
    audit_logger.log(action=f"vault_doc_queued:{requeue['doc_id']}", layer="ingest")
    return {
        "document_id": requeue["doc_id"],
        "vault_id": vault_id,
        "filename": requeue["filename"],
        "status": "pending",
        "progress": 0,
        "duplicate": False,
    }


@router.get("/{vault_id}/documents")
def list_vault_documents(vault_id: str, current_user: Dict = Depends(get_current_user)):
    """Lists all documents in vault with real ingestion status & progress."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user)

        docs = [d.to_dict() for d in vault.documents]
    return {"vault_id": vault_id, "documents": docs}


@router.get("/{vault_id}/documents/{doc_id}/status")
def get_document_status(vault_id: str, doc_id: str, current_user: Dict = Depends(get_current_user)):
    """Polls ingestion status and progress for file pills (Spec 01 §6.2)."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user)
        doc = (
            session.query(DocumentMemory)
            .filter(
                DocumentMemory.doc_id == doc_id,
                DocumentMemory.project_vault_id == vault_id
            )
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        return {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "status": doc.ingest_status,
            "progress": doc.ingest_progress,
            "error": doc.ingest_error,
            "pages": doc.page_count,
            "chunks": doc.chunk_count,
        }


@router.delete("/{vault_id}/documents/{doc_id}")
def delete_vault_document(vault_id: str, doc_id: str, current_user: Dict = Depends(get_current_user)):
    """Deletes a document from the vault and purges its vectors from Chroma."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")
        _verify_vault_access(vault, current_user, write=True)

        doc = (
            session.query(DocumentMemory)
            .filter(
                DocumentMemory.doc_id == doc_id,
                DocumentMemory.project_vault_id == vault_id
            )
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        stored_path = doc.storage_path
        session.delete(doc)

    ingest_service.delete_document_vectors(vault_id=vault_id, doc_id=doc_id)
    # Explicit user deletion is the only path that removes the original file.
    document_store.delete_document(stored_path)
    audit_logger.log(action=f"vault_doc_deleted:{doc_id}", layer="ingest")
    return {"status": "deleted", "doc_id": doc_id, "vault_id": vault_id}


def _owned_document(session, vault_id: str, doc_id: str, current_user: Dict[str, Any], write: bool) -> DocumentMemory:
    vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id, ProjectVault.deleted_at.is_(None)).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Project vault not found.")
    _verify_vault_access(vault, current_user, write=write)
    doc = (
        session.query(DocumentMemory)
        .filter(DocumentMemory.doc_id == doc_id, DocumentMemory.project_vault_id == vault_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/{vault_id}/documents/{doc_id}/file")
def download_vault_document(vault_id: str, doc_id: str, current_user: Dict = Depends(get_current_user)):
    """Returns the original uploaded PDF, byte for byte."""
    from fastapi.responses import FileResponse
    with get_sync_session() as session:
        doc = _owned_document(session, vault_id, doc_id, current_user, write=False)
        stored_path, filename = doc.storage_path, doc.filename
    if not document_store.exists(stored_path):
        raise HTTPException(status_code=404, detail="The original file is not available for this document.")
    return FileResponse(document_store.path(stored_path), media_type="application/pdf", filename=filename)


@router.post("/{vault_id}/documents/{doc_id}/reindex", status_code=202)
def reindex_vault_document(vault_id: str, doc_id: str, background_tasks: BackgroundTasks,
                           current_user: Dict = Depends(get_current_user)):
    """Rebuilds pages, chunks and indexes from the stored original. The original is untouched."""
    with get_sync_session() as session:
        doc = _owned_document(session, vault_id, doc_id, current_user, write=True)
        if not document_store.exists(doc.storage_path):
            raise HTTPException(status_code=409, detail="The original file is not available; upload the document again.")
        filename = doc.filename
        doc.ingest_status, doc.ingest_progress, doc.ingest_error = "pending", 0, None
    background_tasks.add_task(_run_ingestion, doc_id, vault_id, filename)
    audit_logger.log(action=f"vault_doc_reindex:{doc_id}", layer="ingest")
    return {"document_id": doc_id, "status": "pending"}
