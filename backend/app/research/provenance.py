import hashlib
import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """
    Formal Legal Provenance Schema (Phase 10).
    Every retrieved chunk or external legal document MUST have this schema fully populated.
    Incomplete provenance results in evidence being discarded.
    """
    source_id: str = Field(description="Unique identifier for the legal source entity")
    source_type: str = Field(description="Type: statutory_code | gazette_notification | supreme_court_judgment | high_court_order | law_commission_report")
    source_title: str = Field(description="Formal legal title of the enactment or judgment")
    source_url: Optional[str] = Field(default=None, description="Official online URL if retrieved from allowlisted portal")
    jurisdiction: str = Field(default="India / Union", description="Legal jurisdiction governing this source")
    act: str = Field(description="Short title of the statutory Act (e.g. Indian Penal Code, 1860)")
    section: Optional[str] = Field(default=None, description="Specific provision or section reference (e.g. Section 302)")
    document_version: str = Field(default="Official Publication", description="Version / amendment enactment level")
    publication_date: Optional[str] = Field(default=None, description="Date of official gazette notification or judgment delivery")
    retrieval_timestamp: float = Field(default_factory=time.time, description="Unix timestamp of retrieval")
    content_hash: str = Field(description="SHA-256 cryptographic digest of the source text")
    trust_level: str = Field(description="OFFICIAL_GAZETTE | AUTHORITATIVE_PORTAL | JUDICIAL_MIRROR | LOCAL_VERIFIED_CORPUS")
    retrieval_method: str = Field(description="local_hybrid_bm25_vector | mcp_tool_gateway | allowlisted_online_fetch")


class LegalEvidenceItem(BaseModel):
    """Container pairing extracted text with its mandatory cryptographic provenance."""
    text: str
    provenance: ProvenanceRecord
    relevance_score: float = 1.0
    is_superseded: bool = False
    superseded_by: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def compute_content_hash(text: str) -> str:
    """Computes SHA-256 hash of extracted text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def validate_provenance_completeness(record: ProvenanceRecord) -> bool:
    """
    Validation Invariant: Verifies that all mandatory provenance fields are non-empty.
    Returns True if complete, raises ValueError if missing any required field.
    """
    required_fields = [
        "source_id",
        "source_type",
        "source_title",
        "jurisdiction",
        "act",
        "document_version",
        "content_hash",
        "trust_level",
        "retrieval_method",
    ]
    for field_name in required_fields:
        val = getattr(record, field_name, None)
        if not val or not str(val).strip():
            raise ValueError(f"Incomplete provenance: missing required field '{field_name}' in record {record.source_id}")
    return True


def create_provenance_from_chunk(
    chunk: Dict[str, Any],
    source_type: str = "statutory_code",
    trust_level: str = "LOCAL_VERIFIED_CORPUS",
    retrieval_method: str = "local_hybrid_bm25_vector"
) -> ProvenanceRecord:
    """Helper creating a complete ProvenanceRecord from an indexed corpus chunk."""
    text = chunk.get("text", "")
    meta = chunk.get("metadata", {}) or {}
    act_name = chunk.get("act") or meta.get("act") or "Indian Statutory Law"
    sec_name = chunk.get("section") or meta.get("section") or None
    source_id = chunk.get("id") or f"{act_name}_{sec_name or 'general'}_{hashlib.md5(text.encode()).hexdigest()[:8]}"

    rec = ProvenanceRecord(
        source_id=source_id,
        source_type=source_type,
        source_title=act_name,
        source_url=meta.get("source_url"),
        jurisdiction=meta.get("jurisdiction", "India / Union"),
        act=act_name,
        section=sec_name,
        document_version=meta.get("version", "Bare Act 2026"),
        publication_date=meta.get("publication_date"),
        retrieval_timestamp=time.time(),
        content_hash=compute_content_hash(text),
        trust_level=trust_level,
        retrieval_method=retrieval_method,
    )
    validate_provenance_completeness(rec)
    return rec
