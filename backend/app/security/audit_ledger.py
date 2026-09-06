import hashlib
import logging
from typing import Dict, Any, List, Optional

from app.db.engine import get_sync_session
from app.db.models import AuditEvent

logger = logging.getLogger(__name__)


class CryptographicAuditLedger:
    """
    Cryptographic Audit Ledger Verifier (Phase 07).
    Validates append-only immutability and SHA-256 cryptographic hash-chaining
    across all stored audit events in PostgreSQL/SQLite.
    """

    @staticmethod
    def compute_event_hash(
        prev_hash: str,
        ts: str,
        action: str,
        layer: Optional[str] = None,
        injection_score: Optional[float] = None,
        retrieval_hits: Optional[int] = None,
        citations_used: Optional[int] = None,
        validation_pass_fail: Optional[str] = None,
        model_tier_used: Optional[str] = None,
        latency_ms: Optional[float] = None
    ) -> str:
        """Canonical SHA-256 hash chaining formula across all telemetry dimensions."""
        layer_str = str(layer) if layer else "null"
        inj_str = f"{injection_score:.4f}" if injection_score is not None else "null"
        hits_str = str(retrieval_hits) if retrieval_hits is not None else "null"
        cites_str = str(citations_used) if citations_used is not None else "null"
        val_str = str(validation_pass_fail) if validation_pass_fail else "null"
        tier_str = str(model_tier_used) if model_tier_used else "null"
        lat_str = f"{latency_ms:.2f}" if latency_ms is not None else "null"
        
        payload = f"{prev_hash}|{ts}|{action}|{layer_str}|{inj_str}|{hits_str}|{cites_str}|{val_str}|{tier_str}|{lat_str}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_chain(self, start_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Walks the audit event table and verifies:
        1. Linkage: event[i].prev_hash matches event[i-1].hash.
        2. Integrity: recomputed canonical hash matches stored event.hash.
        """
        with get_sync_session() as session:
            query = session.query(AuditEvent)
            if start_id is not None:
                query = query.filter(AuditEvent.id >= start_id)
            events: List[AuditEvent] = query.order_by(AuditEvent.id.asc()).all()

            if not events:
                return {
                    "valid": True,
                    "total_events": 0,
                    "broken_event_id": None,
                    "error_details": "Audit ledger slice is empty."
                }

            for idx, event in enumerate(events):
                if idx > 0:
                    prev_event = events[idx - 1]
                    if event.prev_hash != prev_event.hash:
                        error_msg = f"Hash chain broken at Event ID {event.id}: prev_hash does not match Event {prev_event.id}."
                        return {
                            "valid": False,
                            "total_events": len(events),
                            "broken_event_id": event.id,
                            "error_details": error_msg
                        }

                # Recompute canonical hash
                recomputed = self.compute_event_hash(
                    prev_hash=event.prev_hash,
                    ts=event.ts,
                    action=event.action,
                    layer=event.layer,
                    injection_score=event.injection_score,
                    retrieval_hits=event.retrieval_hits,
                    citations_used=event.citations_used,
                    validation_pass_fail=event.validation_pass_fail,
                    model_tier_used=event.model_tier_used,
                    latency_ms=event.latency_ms
                )

                if event.hash != recomputed:
                    # Also accept legacy simple hash format if present from initial migrations
                    legacy_payload = f"{event.prev_hash}|{event.ts}|{event.action}|{event.layer}|{event.injection_score}|{event.validation_pass_fail}"
                    legacy_hash = hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()
                    legacy_payload2 = f"{event.ts}|{event.action}|{event.layer or 'null'}|{f'{event.injection_score:.4f}' if event.injection_score is not None else 'null'}|{str(event.retrieval_hits) if event.retrieval_hits is not None else 'null'}|{str(event.citations_used) if event.citations_used is not None else 'null'}|{event.validation_pass_fail or 'null'}|{event.model_tier_used or 'null'}|{f'{event.latency_ms:.2f}' if event.latency_ms is not None else 'null'}|{event.prev_hash}"
                    legacy_hash2 = hashlib.sha256(legacy_payload2.encode("utf-8")).hexdigest()

                    if event.hash != legacy_hash and event.hash != legacy_hash2:
                        error_msg = f"Cryptographic tampering detected at Event ID {event.id}: stored hash does not match canonical or legacy signatures."
                        return {
                            "valid": False,
                            "total_events": len(events),
                            "broken_event_id": event.id,
                            "error_details": error_msg
                        }

            return {
                "valid": True,
                "total_events": len(events),
                "broken_event_id": None,
                "error_details": "Cryptographic audit chain verified. Zero tampering detected."
            }


audit_ledger = CryptographicAuditLedger()
