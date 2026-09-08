import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    JSON,
    Index,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), default="Legal Practitioner")
    role = Column(String(32), default="attorney")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectVault(Base):
    __tablename__ = "project_vaults"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True, default="default_user")
    vault_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    conversations = relationship("Conversation", back_populates="vault", cascade="all, delete-orphan")
    documents = relationship("DocumentMemory", back_populates="vault", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "vault_id": self.id,
            "user_id": self.user_id,
            "vault_name": self.vault_name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "conversation_count": len(self.conversations) if self.conversations else 0,
            "document_count": len(self.documents) if self.documents else 0,
        }


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String(64), primary_key=True, index=True)
    project_vault_id = Column(String(64), ForeignKey("project_vaults.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(64), nullable=False, index=True, default="default_user")
    title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vault = relationship("ProjectVault", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.conversation_id,
            "conversation_id": self.conversation_id,
            "project_vault_id": self.project_vault_id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String(64), primary_key=True, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    citations_json = Column(JSON, nullable=True)
    reasoning_trace = Column(Text, nullable=True)
    model_used = Column(String(64), nullable=True)
    runtime_used = Column(String(16), nullable=True)
    token_count = Column(Integer, nullable=True)
    blocked_by = Column(String(64), nullable=True)
    latency_ms = Column(Float, nullable=True)
    grounding_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.message_id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "citations": self.citations or self.citations_json,
            "citations_json": self.citations_json or self.citations,
            "citations_parsed": self.citations_json or self.citations,
            "reasoning_trace": self.reasoning_trace,
            "grounding_score": self.grounding_score,
            "model_used": self.model_used,
            "runtime_used": self.runtime_used,
            "token_count": self.token_count,
            "blocked_by": self.blocked_by,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


ChatMessage = Message


class SemanticMemory(Base):
    __tablename__ = "semantic_memory"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)  # 'preference', 'fact', 'entity'
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_semantic_user_cat_key", "user_id", "category", "key"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentMemory(Base):
    __tablename__ = "document_memory"

    doc_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=True, index=True)
    project_vault_id = Column(String(64), ForeignKey("project_vaults.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    file_size_bytes = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True, default=0)
    vector_ns = Column(String(128), nullable=True)
    ingest_status = Column(String(32), nullable=False, default="ready")
    ingest_error = Column(Text, nullable=True)
    ingest_progress = Column(Integer, nullable=False, default=100)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    vault = relationship("ProjectVault", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.doc_id,
            "doc_id": self.doc_id,
            "session_id": self.session_id,
            "project_vault_id": self.project_vault_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_size_bytes": self.file_size_bytes,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "vector_ns": self.vector_ns,
            "ingest_status": self.ingest_status,
            "ingest_error": self.ingest_error,
            "ingest_progress": self.ingest_progress,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(64), ForeignKey("document_memory.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    page_no = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("DocumentMemory", back_populates="pages")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "page_no": self.page_no,
            "raw_text": self.raw_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    session_id = Column(String(64), primary_key=True)
    topic = Column(Text, nullable=False)
    status = Column(String(32), default="active", nullable=False)  # 'active', 'completed', 'failed'
    findings = Column(Text, nullable=True)
    sources = Column(JSON, nullable=True)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "status": self.status,
            "findings": self.findings,
            "sources": self.sources,
            "citations": self.citations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResearchSource(Base):
    __tablename__ = "research_sources"

    source_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), ForeignKey("research_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "session_id": self.session_id,
            "source_url": self.source_url,
            "title": self.title,
            "snippet": self.snippet,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
        }


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False, index=True)
    layer = Column(String(64), nullable=True)
    injection_score = Column(Float, nullable=True)
    retrieval_hits = Column(Integer, nullable=True)
    citations_used = Column(Integer, nullable=True)
    validation_pass_fail = Column(String(32), nullable=True)
    model_tier_used = Column(String(64), nullable=True)
    latency_ms = Column(Float, nullable=True)
    hash = Column(String(64), nullable=False)
    prev_hash = Column(String(64), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "action": self.action,
            "layer": self.layer,
            "injection_score": self.injection_score,
            "retrieval_hits": self.retrieval_hits,
            "citations_used": self.citations_used,
            "validation_pass_fail": self.validation_pass_fail,
            "model_tier_used": self.model_tier_used,
            "latency_ms": self.latency_ms,
            "hash": self.hash,
            "prev_hash": self.prev_hash,
        }


class MCPToolCall(Base):
    __tablename__ = "mcp_tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=True, index=True)
    tool_name = Column(String(64), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    network_mode = Column(String(32), nullable=False)
    input_payload = Column(JSON, nullable=True)
    output_preview = Column(Text, nullable=True)
    is_allowed = Column(Integer, default=1, nullable=False)
    policy_reason = Column(String(256), nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "category": self.category,
            "network_mode": self.network_mode,
            "input_payload": self.input_payload,
            "output_preview": self.output_preview,
            "is_allowed": bool(self.is_allowed),
            "policy_reason": self.policy_reason,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RequestMetricsRecord(Base):
    __tablename__ = "request_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    endpoint = Column(String(128), nullable=False, default="/chat")
    total_duration_ms = Column(Float, nullable=False, default=0.0)
    ttft_ms = Column(Float, nullable=True)
    retrieval_ms = Column(Float, nullable=True)
    mcp_ms = Column(Float, nullable=True)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    model_tier = Column(String(32), nullable=True)
    security_blocked = Column(Integer, default=0, nullable=False)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "endpoint": self.endpoint,
            "total_duration_ms": self.total_duration_ms,
            "ttft_ms": self.ttft_ms,
            "retrieval_ms": self.retrieval_ms,
            "mcp_ms": self.mcp_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "model_tier": self.model_tier,
            "security_blocked": bool(self.security_blocked),
            "metrics": self.metrics_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvalRunRecord(Base):
    """
    Phase 12 — Eval Run Store.
    Persists evaluation results per category per run for trend tracking.
    One row per (run_id, category) pair.
    """
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    git_commit = Column(String(64), nullable=True)
    category = Column(String(64), nullable=False)          # security | memory | mcp | legal | retrieval | performance
    score = Column(Float, nullable=False, default=0.0)     # 0.0-1.0
    pass_count = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="PASS")  # PASS | FAIL | SKIP
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_eval_runs_run_id_category", "run_id", "category"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "git_commit": self.git_commit,
            "category": self.category,
            "score": self.score,
            "pass_count": self.pass_count,
            "total_count": self.total_count,
            "status": self.status,
            "details": self.details_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SystemSetting(Base):
    """
    Spec 02 — Encrypted Settings & Key Vault Store.
    Persists system settings and Fernet-encrypted API credentials.
    """
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True, index=True)
    encrypted_value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Statute(Base):
    """
    Spec 04 — Dynamic Statute Catalog.
    Represents an Indian statutory enactment synced from MCP servers, local corpus, or vault documents.
    """
    __tablename__ = "statutes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(128), nullable=False, unique=True, index=True)
    title = Column(String(512), nullable=False)
    year = Column(Integer, nullable=True)
    domain = Column(String(64), nullable=False)  # criminal, cyber, corporate, tax, civil, constitutional, procedural, commercial
    source = Column(String(64), nullable=False)  # mcp:ansvar, mcp:themis, mcp:nyaya, mcp:taxbykk, vault_doc, seed_india_code
    section_count = Column(Integer, nullable=False, default=0)
    currency_checked_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sections = relationship("StatuteSection", back_populates="statute", cascade="all, delete-orphan", order_by="StatuteSection.number")

    def to_dict(self, include_sections: bool = False) -> Dict[str, Any]:
        indexed_count = len(self.sections) if self.sections else 0
        nominal_count = self.section_count or indexed_count
        coverage_display = (
            f"{indexed_count} of {nominal_count} sections indexed"
            if nominal_count > 0 and indexed_count != nominal_count
            else f"{nominal_count} sections indexed"
        )

        data = {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "name": self.title,
            "year": self.year,
            "domain": self.domain,
            "category": self.domain.title(),
            "source": self.source,
            "section_count": nominal_count,
            "nominal_sections_count": nominal_count,
            "indexed_sections_count": indexed_count,
            "coverage_display": coverage_display,
            "currency_checked_at": self.currency_checked_at.isoformat() if self.currency_checked_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sections and self.sections:
            data["sections"] = [s.to_dict() for s in self.sections]
        return data


class StatuteSection(Base):
    """
    Spec 04 — Individual Statute Section with raw text and penalty information.
    """
    __tablename__ = "statute_sections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    statute_id = Column(String(36), ForeignKey("statutes.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(String(16), nullable=False)   # "66", "66B", "302", "420"
    heading = Column(String(512), nullable=True)
    raw_text = Column(Text, nullable=True)
    page_ref = Column(Integer, nullable=True)
    embedding_ready = Column(Boolean, default=False)
    cited_in_conversations = Column(Integer, default=0, nullable=False)

    statute = relationship("Statute", back_populates="sections")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statute_id": self.statute_id,
            "number": self.number,
            "section": self.number,
            "heading": self.heading,
            "title": self.heading or f"Section {self.number}",
            "text": self.raw_text,
            "raw_text": self.raw_text,
            "page_ref": self.page_ref,
            "embedding_ready": self.embedding_ready,
            "cited_in_conversations": self.cited_in_conversations or 0,
        }


class CitationEdge(Base):
    """
    Spec 04 & 05 — Persistent Citation Relationship Edge.
    Connects statutes, sections, precedents, and user documents based on LLM citations,
    deterministic text extraction, and MCP relationships with explicit derivation_method provenance.
    """
    __tablename__ = "citation_edges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    src_type = Column(String(32), nullable=False)   # section, precedent, vault_doc, case, statute
    src_key = Column(String(128), nullable=False, index=True)
    dst_type = Column(String(32), nullable=False)   # section, precedent, vault_doc, case, statute, penalty
    dst_key = Column(String(128), nullable=False, index=True)
    relation = Column(String(64), nullable=False)   # cites, interprets, cross_applies, referred_in, supersedes, contains, penalizes_with, judicially_construed_in
    origin = Column(String(32), nullable=False)     # llm_citation, mcp_relation, vault_doc, user_pin
    derivation_method = Column(String(64), nullable=False, default="curated_legal_relationship")
    # Allowed derivation methods:
    # - corpus_structure
    # - text_extraction
    # - curated_legal_relationship
    # - mcp_case_law_lookup
    # - llm_suggested_unverified
    # - user_document_reference
    conversation_id = Column(String(64), nullable=True, index=True)
    message_id = Column(String(64), nullable=True, index=True)
    confidence = Column(Float, nullable=True, default=1.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "src_type": self.src_type,
            "src_key": self.src_key,
            "dst_type": self.dst_type,
            "dst_key": self.dst_key,
            "relation": self.relation,
            "origin": self.origin,
            "derivation_method": self.derivation_method or "curated_legal_relationship",
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


