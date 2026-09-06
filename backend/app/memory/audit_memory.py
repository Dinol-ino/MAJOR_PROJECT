import logging
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.db.engine import get_sync_session
from app.db.models import AuditEvent

logger = logging.getLogger(__name__)


class AuditMemoryManager:
    """
    Layer 6 (L6) Audit Memory:
    Immutable, append-only cryptographic execution audit ledger.
    Stored in PostgreSQL table `audit_events`.
    Guarantees that no update or delete operations exist in the API surface.
    """

    def append_event(
        self,
        action: str,
        layer: Optional[str] = None,
        injection_score: Optional[float] = None,
        retrieval_hits: Optional[int] = None,
        citations_used: Optional[int] = None,
        validation_pass_fail: Optional[str] = None,
        model_tier_used: Optional[str] = None,
        latency_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Appends an immutable audit event with cryptographic hash chaining.
        """
        ts = datetime.utcnow().isoformat() + "Z"

        with get_sync_session() as session:
            last_event = session.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
            prev_hash = last_event.hash if last_event else "0" * 64

            # Compute SHA-256 hash chaining using canonical ledger function
            from app.security.audit_ledger import CryptographicAuditLedger
            curr_hash = CryptographicAuditLedger.compute_event_hash(
                prev_hash=prev_hash,
                ts=ts,
                action=action,
                layer=layer,
                injection_score=injection_score,
                retrieval_hits=retrieval_hits,
                citations_used=citations_used,
                validation_pass_fail=validation_pass_fail,
                model_tier_used=model_tier_used,
                latency_ms=latency_ms
            )

            event = AuditEvent(
                ts=ts,
                action=action,
                layer=layer,
                injection_score=injection_score,
                retrieval_hits=retrieval_hits,
                citations_used=citations_used,
                validation_pass_fail=validation_pass_fail,
                model_tier_used=model_tier_used,
                latency_ms=latency_ms,
                hash=curr_hash,
                prev_hash=prev_hash
            )
            session.add(event)
            session.flush()
            return event.to_dict()

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Reads recent audit events for auditing."""
        with get_sync_session() as session:
            events = session.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
            return [e.to_dict() for e in reversed(events)]

    def verify_ledger_integrity(self, start_id: Optional[int] = None) -> Tuple[bool, int, str]:
        """Verifies the unbroken cryptographic SHA-256 hash chain of the audit log."""
        with get_sync_session() as session:
            query = session.query(AuditEvent)
            if start_id is not None:
                query = query.filter(AuditEvent.id >= start_id)
            events = query.order_by(AuditEvent.id.asc()).all()
            if not events:
                return True, 0, "Ledger is empty"

            from app.security.audit_ledger import CryptographicAuditLedger
            prev_hash = events[0].prev_hash if events else "0" * 64
            for idx, ev in enumerate(events):
                if ev.prev_hash != prev_hash:
                    return False, idx, f"Hash chain broken at event ID {ev.id}: prev_hash mismatch"

                expected_hash = CryptographicAuditLedger.compute_event_hash(
                    prev_hash=prev_hash,
                    ts=ev.ts,
                    action=ev.action,
                    layer=ev.layer,
                    injection_score=ev.injection_score,
                    retrieval_hits=ev.retrieval_hits,
                    citations_used=ev.citations_used,
                    validation_pass_fail=ev.validation_pass_fail,
                    model_tier_used=ev.model_tier_used,
                    latency_ms=ev.latency_ms
                )
                
                # Check current canonical hash or legacy hash format
                legacy_payload = f"{prev_hash}|{ev.ts}|{ev.action}|{ev.layer}|{ev.injection_score}|{ev.validation_pass_fail}"
                legacy_hash = hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()

                if ev.hash != expected_hash and ev.hash != legacy_hash:
                    return False, idx, f"Hash chain broken at event ID {ev.id}: content hash mismatch"

                prev_hash = ev.hash

            return True, len(events), "Audit ledger hash chain verified 100% intact"


audit_memory = AuditMemoryManager()
