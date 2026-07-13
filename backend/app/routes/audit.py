from fastapi import APIRouter
from app.schemas import AuditLogResponse, AuditLogRow
from datetime import datetime

router = APIRouter(tags=["audit"])

@router.get("/audit/{session_id}", response_model=AuditLogResponse)
async def audit_endpoint(session_id: str):
    # Stub database fetch for Phase 0
    # In real app, fetches from SQLite hash-chained audit database
    
    mock_rows = [
        AuditLogRow(
            ts=datetime.utcnow().isoformat() + "Z",
            action="init",
            layer=None,
            hash="0000000000000000000000000000000000000000000000000000000000000000",
            prev_hash="0000000000000000000000000000000000000000000000000000000000000000"
        )
    ]
    return AuditLogResponse(rows=mock_rows)
