import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field

from app.db.engine import get_sync_session
from app.db.models import ProjectVault, Conversation, DocumentMemory, DocumentPage
from app.services.ingest import ingest_service, compute_file_hash, get_vault_collection_name
from app.defense.audit_log import AuditLogger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vaults", tags=["vaults"])
audit_logger = AuditLogger()


class CreateVaultRequest(BaseModel):
    vault_name: str = Field(..., min_length=1, max_length=255, description="Name of the legal matter / project vault")
    description: Optional[str] = Field(None, description="Optional case or matter description")
    user_id: Optional[str] = Field("default_user", description="Owner user ID")


class UpdateVaultRequest(BaseModel):
    vault_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


@router.post("", status_code=201)
def create_vault(req: CreateVaultRequest):
    """Creates a new durable Project Vault (matter-based container)."""
    with get_sync_session() as session:
        vault = ProjectVault(
            id=str(uuid.uuid4()),
            user_id=req.user_id or "default_user",
            vault_name=req.vault_name.strip(),
            description=req.description.strip() if req.description else None,
        )
        session.add(vault)
        session.flush()
        res = vault.to_dict()

    audit_logger.log(action=f"vault_created:{res['id']}", layer="persistence")
    return res


@router.get("")
def list_vaults(user_id: str = "default_user"):
    """Lists all Project Vaults for the user with document and conversation counts."""
    with get_sync_session() as session:
        vaults = (
            session.query(ProjectVault)
            .filter(ProjectVault.user_id == user_id)
            .order_by(ProjectVault.updated_at.desc())
            .all()
        )
        data = [v.to_dict() for v in vaults]
    return {"vaults": data, "count": len(data)}


@router.get("/{vault_id}")
def get_vault_details(vault_id: str):
    """Retrieves vault details, associated conversations, and indexed documents."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")

        convs = [c.to_dict() for c in vault.conversations]
        docs = [d.to_dict() for d in vault.documents]
        base_dict = vault.to_dict()

    base_dict["conversations"] = convs
    base_dict["documents"] = docs
    return base_dict


@router.patch("/{vault_id}")
def update_vault(vault_id: str, req: UpdateVaultRequest):
    """Renames vault or updates description."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")

        if req.vault_name is not None:
            vault.vault_name = req.vault_name.strip()
        if req.description is not None:
            vault.description = req.description.strip()

        session.flush()
        res = vault.to_dict()

    audit_logger.log(action=f"vault_updated:{vault_id}", layer="persistence")
    return res


@router.delete("/{vault_id}")
def delete_vault(vault_id: str):
    """Cascades delete for vault, conversations, documents, and purges vector namespace."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")

        session.delete(vault)

    # Purge Chroma collection for this vault
    ingest_service.delete_vault_collection(vault_id)
    audit_logger.log(action=f"vault_deleted:{vault_id}", layer="persistence")
    return {"status": "deleted", "vault_id": vault_id}


@router.post("/{vault_id}/documents", status_code=202)
async def upload_vault_document(
    vault_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Uploads a case PDF to a specific Project Vault.
    Returns document_id immediately with pending state; background worker processes ingestion.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF legal documents are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    f_hash = compute_file_hash(content)

    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")

        # Check deduplication within vault
        existing = (
            session.query(DocumentMemory)
            .filter(
                DocumentMemory.project_vault_id == vault_id,
                DocumentMemory.file_hash == f_hash
            )
            .first()
        )
        if existing:
            return {
                "document_id": existing.doc_id,
                "status": existing.ingest_status,
                "duplicate": True,
                "filename": existing.filename,
                "message": "File already ingested into this vault.",
            }

        doc_id = f"doc_{vault_id[:8]}_{uuid.uuid4().hex[:8]}"
        doc_mem = DocumentMemory(
            doc_id=doc_id,
            session_id=vault_id,
            project_vault_id=vault_id,
            filename=file.filename,
            file_hash=f_hash,
            file_size_bytes=len(content),
            vector_ns=get_vault_collection_name(vault_id),
            ingest_status="pending",
            ingest_progress=0,
            metadata_json={"source": "vault_upload", "original_filename": file.filename},
        )
        session.add(doc_mem)
        session.flush()

    # Dispatch ingestion in background task worker
    background_tasks.add_task(
        ingest_service.ingest_document,
        doc_id=doc_id,
        vault_id=vault_id,
        filename=file.filename,
        content=content,
    )

    audit_logger.log(action=f"vault_doc_queued:{doc_id}", layer="ingest")
    return {
        "document_id": doc_id,
        "vault_id": vault_id,
        "filename": file.filename,
        "status": "pending",
        "progress": 0,
        "duplicate": False,
    }


@router.get("/{vault_id}/documents")
def list_vault_documents(vault_id: str):
    """Lists all documents in vault with real ingestion status & progress."""
    with get_sync_session() as session:
        vault = session.query(ProjectVault).filter(ProjectVault.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail="Project vault not found.")

        docs = [d.to_dict() for d in vault.documents]
    return {"vault_id": vault_id, "documents": docs}


@router.get("/{vault_id}/documents/{doc_id}/status")
def get_document_status(vault_id: str, doc_id: str):
    """Polls ingestion status and progress for file pills (Spec 01 §6.2)."""
    with get_sync_session() as session:
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
def delete_vault_document(vault_id: str, doc_id: str):
    """Deletes a document from the vault and purges its vectors from Chroma."""
    with get_sync_session() as session:
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

        session.delete(doc)

    ingest_service.delete_document_vectors(vault_id=vault_id, doc_id=doc_id)
    audit_logger.log(action=f"vault_doc_deleted:{doc_id}", layer="ingest")
    return {"status": "deleted", "doc_id": doc_id, "vault_id": vault_id}
