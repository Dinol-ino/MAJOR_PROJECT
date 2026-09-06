import logging
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.research.provenance import LegalEvidenceItem, ProvenanceRecord

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    STATUS_CONFLICT = "STATUS_CONFLICT"              # e.g., Local says In Force, Online says Repealed
    PUNISHMENT_CONFLICT = "PUNISHMENT_CONFLICT"      # e.g., Amendment changed prison term/fine
    AMENDMENT_OVERWRITE = "AMENDMENT_OVERWRITE"      # e.g., Provision replaced by BNS/BNSS 2023
    PRECEDENT_OVERRULED = "PRECEDENT_OVERRULED"      # e.g., Higher bench overruled prior ratio


class ConflictRecord(BaseModel):
    """
    Formal conflict record surfaced when online source contradicts local corpus (Phase 10).
    Surfaced explicitly in response so LLM can explain nuance rather than silently overriding.
    """
    act: str
    section: Optional[str] = None
    conflict_type: ConflictType
    description: str
    local_source_title: str
    local_trust_level: str
    local_version: str
    online_source_title: str
    online_trust_level: str
    online_version: str
    online_url: Optional[str] = None
    resolution_guidance: str


class LegalConflictDetector:
    """
    Detects substantive statutory and precedent conflicts between local corpus and online sources.
    """

    def detect_conflicts(
        self,
        local_items: List[LegalEvidenceItem],
        online_items: List[LegalEvidenceItem]
    ) -> List[ConflictRecord]:
        """
        Cross-matches local and online legal evidence for same Act/Section to identify contradictions.
        """
        conflicts: List[ConflictRecord] = []

        for online in online_items:
            on_prov = online.provenance
            on_act = (on_prov.act or "").lower().strip()
            on_sec = (on_prov.section or "").lower().strip()

            for local in local_items:
                loc_prov = local.provenance
                loc_act = (loc_prov.act or "").lower().strip()
                loc_sec = (loc_prov.section or "").lower().strip()

                # Match by Act and Section
                if on_act and loc_act and (on_act in loc_act or loc_act in on_act):
                    if on_sec and loc_sec and (on_sec in loc_sec or loc_sec in on_sec):
                        conflict = self._check_pair_conflict(local, online)
                        if conflict:
                            conflicts.append(conflict)

        return conflicts

    def _check_pair_conflict(
        self,
        local: LegalEvidenceItem,
        online: LegalEvidenceItem
    ) -> Optional[ConflictRecord]:
        loc_text = local.text.lower()
        on_text = online.text.lower()

        # Check for Repeal / Supersession
        if ("repealed" in on_text or "superseded" in on_text or "omitted" in on_text) and ("repealed" not in loc_text):
            return ConflictRecord(
                act=local.provenance.act,
                section=local.provenance.section,
                conflict_type=ConflictType.STATUS_CONFLICT,
                description=f"Online official source indicates {local.provenance.act} {local.provenance.section} has been repealed or superseded, whereas local corpus records it as active.",
                local_source_title=local.provenance.source_title,
                local_trust_level=local.provenance.trust_level,
                local_version=local.provenance.document_version,
                online_source_title=online.provenance.source_title,
                online_trust_level=online.provenance.trust_level,
                online_version=online.provenance.document_version,
                online_url=online.provenance.source_url,
                resolution_guidance="Present both provisions clearly, explaining that the online gazette reflects the latest legislative amendment."
            )

        # Check for Bharatiya Nyaya Sanhita (BNS) replacement of IPC
        if ("bharatiya nyaya sanhita" in on_text or "bns" in on_text) and "indian penal code" in local.provenance.act.lower():
            return ConflictRecord(
                act=local.provenance.act,
                section=local.provenance.section,
                conflict_type=ConflictType.AMENDMENT_OVERWRITE,
                description=f"IPC provision replaced by Bharatiya Nyaya Sanhita (BNS), 2023 with effect from July 1, 2024.",
                local_source_title=local.provenance.source_title,
                local_trust_level=local.provenance.trust_level,
                local_version=local.provenance.document_version,
                online_source_title=online.provenance.source_title,
                online_trust_level=online.provenance.trust_level,
                online_version=online.provenance.document_version,
                online_url=online.provenance.source_url,
                resolution_guidance="Highlight both the legacy IPC section and the corresponding newly enforced BNS section."
            )

        return None


conflict_detector = LegalConflictDetector()
