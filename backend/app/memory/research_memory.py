import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.db.engine import get_sync_session
from app.db.models import ResearchSession, ResearchSource

logger = logging.getLogger(__name__)


class ResearchMemoryManager:
    """
    Layer 5 (L5) Research Memory:
    Maintains structured research findings, legal sources, citations, and provenance records.
    Stored in PostgreSQL tables `research_sessions` and `research_sources`.
    """

    def create_research_session(
        self,
        session_id: str,
        topic: str,
        status: str = "active"
    ) -> Dict[str, Any]:
        """Creates or resets a research session."""
        with get_sync_session() as session:
            rs = session.query(ResearchSession).filter_by(session_id=session_id).first()
            if rs:
                rs.topic = topic
                rs.status = status
            else:
                rs = ResearchSession(
                    session_id=session_id,
                    topic=topic,
                    status=status,
                    findings="",
                    sources=[],
                    citations=[],
                    created_at=datetime.utcnow()
                )
                session.add(rs)
            session.flush()
            return rs.to_dict()

    def add_source(
        self,
        session_id: str,
        source_url: str,
        title: Optional[str] = None,
        snippet: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends a discovered source with provenance to the research session."""
        source_id = str(uuid.uuid4())
        source = ResearchSource(
            source_id=source_id,
            session_id=session_id,
            source_url=source_url,
            title=title,
            snippet=snippet,
            retrieved_at=datetime.utcnow()
        )
        with get_sync_session() as session:
            session.add(source)
            session.flush()
            return source.to_dict()

    def update_findings(
        self,
        session_id: str,
        findings: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        status: str = "completed"
    ) -> Dict[str, Any]:
        """Updates synthesized findings and structured citations for the session."""
        with get_sync_session() as session:
            rs = session.query(ResearchSession).filter_by(session_id=session_id).first()
            if not rs:
                rs = ResearchSession(
                    session_id=session_id,
                    topic="Synthesized Research",
                    status=status,
                    findings=findings,
                    citations=citations or [],
                    created_at=datetime.utcnow()
                )
                session.add(rs)
            else:
                rs.findings = findings
                rs.status = status
                if citations is not None:
                    rs.citations = citations
            session.flush()
            return rs.to_dict()

    def get_research_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a research session including its synthesized findings and sources."""
        with get_sync_session() as session:
            rs = session.query(ResearchSession).filter_by(session_id=session_id).first()
            if not rs:
                return None
            res = rs.to_dict()
            sources = session.query(ResearchSource).filter_by(session_id=session_id).all()
            res["discovered_sources"] = [s.to_dict() for s in sources]
            return res


research_memory = ResearchMemoryManager()
