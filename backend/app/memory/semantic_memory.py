import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.db.engine import get_sync_session
from app.db.models import SemanticMemory
from app.memory.policies import policies
from app.defense.layer1_input_guard import Layer1InputGuard

logger = logging.getLogger(__name__)


class SemanticMemoryValidationGate:
    """
    Validation Gate for Layer 3 Semantic Memory.
    Ensures LLMs cannot automatically decide arbitrary long-term memory without policy validation.
    Enforces format checking, category allowlist, deduplication, and injection checks.
    """

    def __init__(self):
        self.input_guard = Layer1InputGuard()

    def validate_proposal(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        consent_given: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates proposed memory entry against security & consistency invariants.
        Returns (is_valid, rejection_reason).
        """
        if not consent_given:
            return False, "User consent not provided for long-term memory persistence."

        if not category or category.lower() not in policies.ALLOWED_SEMANTIC_CATEGORIES:
            return False, f"Category '{category}' is not in allowed semantic categories: {policies.ALLOWED_SEMANTIC_CATEGORIES}"

        if not key or len(key.strip()) < 2 or len(key) > 128:
            return False, "Key must be between 2 and 128 characters."

        if not value or len(value.strip()) < 1 or len(value) > 2000:
            return False, "Value must be between 1 and 2000 characters."

        # Scan for adversarial injection patterns inside proposed memory
        is_clean, reason = self.input_guard.validate(value)
        if not is_clean:
            return False, f"Security rejection: proposed memory value flagged for injection risk ({reason})"

        # Doc 04 §4.4: Invariant enforcement — reject legal-fact-shaped writes at the validation gate
        import re
        combined_text = f"{key} {value}"
        legal_fact_patterns = [
            r"(?i)\bsection\s+\d+[a-z]*\b.*?\b(?:means|defines|punishes|provides|prescribes|imposes|states|penalizes)\b",
            r"(?i)\b(?:ipc|crpc|bns|bnss|bsa|it\s+act|companies\s+act)\b.*?\b(?:section|sec\.?)\s*\d+",
            r"(?i)\bpunishment\s+for\b.*?\b(?:is|shall\s+be|imprisonment)\b",
            r"(?i)\bunder\s+section\s+\d+[a-z]*\b.*?\b(?:imprisonment|fine|bailable|cognizable|punishable)\b",
            r"(?i)\bstatutory\s+definition\s+of\b",
            r"(?i)\bpenal\s+code\b.*?\bsection\b",
        ]
        for pat in legal_fact_patterns:
            if re.search(pat, combined_text):
                return False, (
                    "Statutory legal claims, definitions, and provisions cannot be stored in user semantic memory. "
                    "Legal facts must reside exclusively in the authoritative retrieval corpus."
                )

        return True, None


class SemanticMemoryManager:
    """
    Layer 3 (L3) Semantic Memory:
    Explicitly managed user facts, preferences, jurisdictions, and practice areas.
    Stored in PostgreSQL table `semantic_memory`.
    """

    def __init__(self):
        self.validator = SemanticMemoryValidationGate()

    def propose_and_save(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        consent_given: bool = True
    ) -> Dict[str, Any]:
        """
        Passes proposed memory entry through the validation gate before writing to PostgreSQL.
        """
        is_valid, reason = self.validator.validate_proposal(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            consent_given=consent_given
        )

        if not is_valid:
            logger.warning(f"Semantic memory proposal rejected for user '{user_id}': {reason}")
            raise ValueError(f"Memory validation failed: {reason}")

        norm_category = category.lower().strip()
        norm_key = key.strip()
        norm_value = value.strip()

        with get_sync_session() as session:
            existing = session.query(SemanticMemory).filter_by(
                user_id=user_id,
                category=norm_category,
                key=norm_key
            ).first()

            if existing:
                existing.value = norm_value
                existing.updated_at = datetime.utcnow()
                session.flush()
                return existing.to_dict()
            else:
                mem = SemanticMemory(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    category=norm_category,
                    key=norm_key,
                    value=norm_value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(mem)
                session.flush()
                return mem.to_dict()

    def get_user_memories(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves semantic memory entries filtered strictly by authenticated user_id."""
        with get_sync_session() as session:
            query = session.query(SemanticMemory).filter_by(user_id=user_id)
            if category:
                query = query.filter_by(category=category.lower().strip())
            mems = query.order_by(SemanticMemory.updated_at.desc()).all()
            return [m.to_dict() for m in mems]

    def delete_memory(
        self,
        memory_id: str,
        user_id: str
    ) -> bool:
        """Explicit user-initiated deletion of a specific semantic memory entry."""
        with get_sync_session() as session:
            mem = session.query(SemanticMemory).filter_by(id=memory_id).first()
            if not mem:
                return False
            if not policies.validate_user_access(mem.user_id, user_id):
                raise PermissionError(f"User '{user_id}' is not authorized to delete memory '{memory_id}'.")

            session.delete(mem)
            return True


semantic_memory = SemanticMemoryManager()
