import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.db.models import Base, AuditEvent
from app.db.engine import get_sync_engine, get_sync_session

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Cryptographic SHA-256 hash-chained audit logging engine.
    Persists tamper-evident telemetry to PostgreSQL/SQLite via SQLAlchemy ORM (AuditEvent model).
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        if db_path and not (db_path.startswith("postgres://") or db_path.startswith("postgresql://")):
            url = f"sqlite:///{db_path}" if not db_path.startswith("sqlite://") else db_path
            self._engine = create_engine(url, connect_args={"check_same_thread": False}, echo=False)
            Base.metadata.create_all(bind=self._engine)
            with self._engine.connect() as conn:
                try:
                    conn.execute(Base.metadata.tables["audit_events"].select().limit(0))
                except Exception:
                    pass
            self._session_factory = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)
        else:
            self._engine = None
            self._session_factory = None
            try:
                engine = get_sync_engine()
                Base.metadata.create_all(bind=engine)
            except Exception as e:
                logger.warning(f"Could not initialize audit schema on startup: {e}")

    @contextmanager
    def _get_session(self):
        if self._session_factory:
            session: Session = self._session_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            with get_sync_session() as session:
                yield session

    def get_latest_hash(self) -> str:
        with self._get_session() as session:
            latest = session.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
            if latest:
                return latest.hash
            return "0000000000000000000000000000000000000000000000000000000000000000"

    def log(
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
        Logs an action, computes cryptographic hash chaining across telemetry metrics, and inserts it.
        """
        ts = datetime.utcnow().isoformat() + "Z"
        prev_hash = self.get_latest_hash()
        from app.security.audit_ledger import CryptographicAuditLedger
        current_hash = CryptographicAuditLedger.compute_event_hash(
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
            hash=current_hash,
            prev_hash=prev_hash
        )

        with self._get_session() as session:
            session.add(event)
            session.flush()

        return {
            "ts": ts,
            "action": action,
            "layer": layer,
            "hash": current_hash,
            "prev_hash": prev_hash
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            events = session.query(AuditEvent).order_by(AuditEvent.id.asc()).all()
            return [e.to_dict() for e in events]

    def verify_chain(self) -> bool:
        """
        Verifies the cryptographic integrity of the entire audit log chain.
        """
        from app.security.audit_ledger import CryptographicAuditLedger
        rows = self.fetch_all()
        expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        for row in rows:
            if row["prev_hash"] != expected_prev_hash:
                return False

            computed_hash = CryptographicAuditLedger.compute_event_hash(
                prev_hash=row["prev_hash"],
                ts=row["ts"],
                action=row["action"],
                layer=row.get("layer"),
                injection_score=row.get("injection_score"),
                retrieval_hits=row.get("retrieval_hits"),
                citations_used=row.get("citations_used"),
                validation_pass_fail=row.get("validation_pass_fail"),
                model_tier_used=row.get("model_tier_used"),
                latency_ms=row.get("latency_ms")
            )

            if row["hash"] != computed_hash:
                return False

            expected_prev_hash = row["hash"]

        return True
