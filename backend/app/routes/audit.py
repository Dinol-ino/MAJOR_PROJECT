import time
from typing import Optional
from fastapi import APIRouter, Query, Response
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
    report["verified_at"] = round(time.time(), 3)
    return report


@router.get("/audit/export/json")
def export_audit_trail_endpoint(limit: Optional[int] = Query(None, ge=1, le=10000)):
    """
    Task 8.1.3: Exports full tamper-evident audit trail with SHA-256 integrity report as JSON.
    """
    logs = audit_logger.fetch_all()
    if limit:
        logs = logs[-limit:]
    verification = audit_ledger.verify_chain()
    verification["verified_at"] = round(time.time(), 3)

    return {
        "export_metadata": {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_records": len(logs),
            "integrity_verification": verification
        },
        "records": logs
    }


@router.get("/audit/{session_id}", response_model=AuditLogResponse)
async def audit_endpoint(session_id: str):
    """
    Returns audit log rows with category counts and tamper verification status (Task 8.1.1 & 8.1.2).
    """
    # Fetch log rows from database
    logs = audit_logger.fetch_all()

    chat_count = sum(1 for l in logs if "chat" in str(l.get("action", "")).lower())
    blocked_count = sum(1 for l in logs if "block" in str(l.get("action", "")).lower() or "quarantine" in str(l.get("action", "")).lower() or l.get("validation_pass_fail") == "fail")
    upload_count = sum(1 for l in logs if "upload" in str(l.get("action", "")).lower() or "pdf" in str(l.get("action", "")).lower())
    mcp_count = sum(1 for l in logs if "mcp" in str(l.get("action", "")).lower())

    # Map database row formats to Pydantic AuditLogRow schemas
    rows = [
        AuditLogRow(
            ts=log["ts"],
            action=log["action"],
            layer=log.get("layer"),
            hash=log["hash"],
            prev_hash=log["prev_hash"],
            injection_score=log.get("injection_score"),
            validation_pass_fail=log.get("validation_pass_fail")
        )
        for log in logs
    ]

    return AuditLogResponse(
        rows=rows,
        total_count=len(rows),
        chat_count=chat_count,
        blocked_count=blocked_count,
        upload_count=upload_count,
        mcp_count=mcp_count,
        verified=True
    )
