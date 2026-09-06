from fastapi import APIRouter
from app.schemas import AuditLogResponse, AuditLogRow
from app.config import settings
from app.defense.audit_log import AuditLogger
from app.security.audit_ledger import audit_ledger

router = APIRouter(tags=["audit"])

# Instantiate the shared audit logger
audit_logger = AuditLogger()


@router.get("/audit/verify")
def verify_audit_ledger_endpoint():
    """
    Cryptographic verification endpoint for the append-only audit ledger (Phase 07).
    Walks the SHA-256 hash-chain and confirms zero tampering across all recorded events.
    """
    report = audit_ledger.verify_chain()
    return report


@router.get("/audit/{session_id}", response_model=AuditLogResponse)
async def audit_endpoint(session_id: str):
    # Fetch log rows from database
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
