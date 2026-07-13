from fastapi import APIRouter
from app.schemas import AuditLogResponse, AuditLogRow
from app.config import settings
from app.defense.audit_log import AuditLogger

router = APIRouter(tags=["audit"])

# Instantiate the shared audit logger
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)

@router.get("/audit/{session_id}", response_model=AuditLogResponse)
async def audit_endpoint(session_id: str):
    # Fetch log rows from SQLite database
    logs = audit_logger.fetch_all()
    
    # Map database row formats to Pydantic AuditLogRow schemas
    rows = [
        AuditLogRow(
            ts=log["ts"],
            action=log["action"],
            layer=log["layer"],
            hash=log["hash"],
            prev_hash=log["prev_hash"]
        )
        for log in logs
    ]
    
    return AuditLogResponse(rows=rows)
