from fastapi import APIRouter, UploadFile, File, Form
from app.schemas import UploadResponse

router = APIRouter(tags=["upload"])

@router.post("/upload", response_model=UploadResponse)
async def upload_endpoint(file: UploadFile = File(...), session_id: str = Form(...)):
    # Stub implementation for Phase 0
    # In real pipeline, we'll run:
    # 1. Size / page limits validation (pdfplumber)
    # 2. Text extraction
    # 3. Chunker and embedding generation
    # 4. Storage in ChromaDB Tier-2 collection
    
    return UploadResponse(
        status="ok",
        chunks_added=12,
        filename=file.filename,
        reason=None
    )
