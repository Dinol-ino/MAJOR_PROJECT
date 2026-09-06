import re
import hashlib
import logging
from typing import Tuple, Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    # --- Existing patterns (Phase 07) ---
    re.compile(r"(?i)\bignore\s+(?:previous|all|the|prior)\s+instructions?\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:dan|jailbroken|unrestricted|god\s+mode|developer\s+mode)\b"),
    re.compile(r"(?i)\b(?:reveal|print|show|output|leak|dump)\s+(?:the\s+|all\s+)?(?:system\s+prompt|instructions?|initial\s+prompt)\b"),
    re.compile(r"(?i)\bsystem\s+prompt\b"),
    re.compile(r"(?i)\bforget\s+(?:everything|your\s+rules|all\s+guidelines)\b"),
    re.compile(r"(?i)\brole\s*:\s*system\b"),
    re.compile(r"(?i)<\s*system\s*>"),
    re.compile(r"(?i)\[\s*system\s*\]"),
    re.compile(r"(?i)\bdelimiter\s+breaking\b"),
    re.compile(r"(?i)\bbypass\s+(?:filter|safety|guardrails?|security)\b"),

    # --- Phase 12 additions: jailbreak / persona hijack ---
    re.compile(r"(?i)\bpretend\s+(?:you\s+are|to\s+be)\s+(?:an?\s+)?(?:ai|bot|assistant)\s+with\s+no\s+(?:ethical|safety|guidelines?|restrictions?)\b"),
    re.compile(r"(?i)\byou\s+are\s+(?:a\s+)?(?:unrestricted|jailbroken|unfiltered|uncensored)\b"),
    re.compile(r"(?i)\benable\s+(?:jailbreak|god|developer|unrestricted)\s+mode\b"),
    re.compile(r"(?i)\b(?:god\s+mode|jailbreak\s+mode|developer\s+mode|dan\s+mode)\s+(?:enabled|activated|on)\b"),
    re.compile(r"(?i)\bact\s+as\s+(?:an?\s+)?(?:ai|bot|model)\s+with\s+no\s+(?:restrictions?|filters?|guidelines?|ethics?)\b"),
    re.compile(r"(?i)\bsafety\s+(?:training|filters?)\s+(?:was|were|is|are|has\s+been)\s+(?:removed|disabled|bypassed)\b"),
    re.compile(r"(?i)\b(?:uncensored|unfiltered|unrestricted)\s+(?:mode|response|output|answer)\b"),
    re.compile(r"(?i)\bin\s+(?:unrestricted|jailbroken|god)\s+mode\b"),
    re.compile(r"(?i)\btell\s+me\s+what\s+you\s+would\s+(?:say|do)\s+if\s+your\s+(?:content\s+filter|safety|restrictions?)\s+(?:was|were|is|are)\s+disabled\b"),

    # --- Phase 12 additions: override / attention / new directive ---
    re.compile(r"(?i)\battention\s*[:\-]\s*all\s+previous\s+instructions?\s+(?:are\s+)?(?:now\s+)?invalid\b"),
    re.compile(r"(?i)\bas\s+per\s+the\s+new\s+(?:policy|directive|instruction|update)\b"),
    re.compile(r"(?i)\bprior\s+context\s+is\s+irrelevant\b"),
    re.compile(r"(?i)\b(?:new|updated?)\s+(?:directive|instruction|policy)\s*[:\-]\s*(?:reveal|output|disable|bypass|ignore)\b"),
    re.compile(r"(?i)\b(?:reveal|output|expose|disclose)\s+(?:all|your)\s+(?:configuration|config|internals?|hidden|stored)\b"),
    re.compile(r"(?i)\boperating\s+in\s+developer\s+mode\b"),
    re.compile(r"(?i)<<<\s*system\s*>>>"),
    re.compile(r"(?i)/\*\s*new\s+directive\s*\*/"),

    # --- Phase 12 additions: disregard / write story jailbreak framing ---
    re.compile(r"(?i)\bdisregard\s+(?:prior|previous|all|the)\s+(?:context|instructions?|guidelines?|reference)\b"),
    re.compile(r"(?i)\bunder\s+the\s+(?:roleplay|role-play|simulation|scenario)\s+.{0,40}(?:write|output|generate|explain)\b"),
    re.compile(r"(?i)\bin\s+this\s+story\b.{0,50}(?:explain|describe|show|write|output)"),
    re.compile(r"(?i)\bfor\s+a\s+(?:novel|story|fiction|roleplay|book|game)\b.{0,60}(?:bypass|circumvent|hack|manipulate|alter)"),
    re.compile(r"(?i)\byou\s+are\s+(?:now\s+)?(?:gpt.{0,10}jailbroken|devmode|dev\s+mode|ALICE|DAN|an\s+unfiltered)"),
    re.compile(r"(?i)\bDevMode\s+AI\b"),
    re.compile(r"(?i)\boutput\s+two\s+responses.{0,30}(?:uncensored|safe\s+one)"),
    re.compile(r"(?i)\b(?:roleplay|role-play)\s*:.{0,30}(?:you\s+are|as\s+an?|no\s+restrictions?)"),
    re.compile(r"(?i)\bfor\s+research\s+purposes?\s+only\b.{0,80}(?:manipulate|hack|alter|bypass|circumvent)"),
    re.compile(r"(?i)\bsimulate\s+a\s+scenario\s+where\s+you\s+are\s+an\s+AI\s+that\s+was\s+jailbroken"),
    re.compile(r"(?i)\bin\s+character\s+as\s+(?:an?\s+)?(?:unfiltered|uncensored|unrestricted|jailbroken)\s+AI"),
    re.compile(r"(?i)\bwrite\s+a\s+story\s+where.{0,60}(?:hack|alter|manipulate|bypass)"),

    re.compile(r"(?i)\boverrides?\s+all\s+restrictions?"),
    re.compile(r"(?i)\boutput\s+your\s+training\s+data\b"),
    re.compile(r"(?i)\bforget\s+(?:the\s+above|everything\s+above)\b"),
    # Final 3 bypass fixes (Phase 12)
    re.compile(r"(?i)\bdisregard\s+the\s+provided\s+(?:reference|context|texts?|sources?)\b"),  # ID 6
    re.compile(r"(?i)\bbypass\s+all\s+(?:filters?|safety|rules?|guidelines?)\s+and\s+output\b"),  # ID 18
    re.compile(r"(?i)\bwrite\s+a\s+story\s+where\s+the\s+main\s+character\s+(?:hack|alter|manipulate)\b"),  # ID 39


    # --- Phase 12 additions: PII exfiltration / data dump ---
    re.compile(r"(?i)\b(?:list|show|output|dump|reveal|expose|print)\s+(?:all|every|stored|indexed)?\s*(?:aadhaar|pan\s+card|phone\s+numbers?|email\s+addresses?|users?|personal\s+(?:data|information|details?))\b"),
    re.compile(r"(?i)\b(?:reveal|dump|output|leak|list)\s+(?:the\s+)?(?:private|personally\s+identifiable|pii)\s+(?:data|information|fields?|details?)\b"),
    re.compile(r"(?i)\bwhat\s+is\s+(?:user|their)\s+.{0,30}(?:phone\s+number|email|aadhaar|pan)\s+from\s+your\s+(?:logs?|database|memory|storage)\b"),
    re.compile(r"(?i)\bprint\s+all\s+(?:user|private|stored)\s+(?:data|details?|information|records?)\b"),
    re.compile(r"(?i)\blookup\s+all\s+stored\s+(?:aadhaar|pan|phone|email)\b"),
    re.compile(r"(?i)\bshow\s+me\s+all\s+(?:pan\s+cards?|aadhaar|phone\s+numbers?|emails?)"),
    re.compile(r"(?i)\bdump\s+all\s+(?:the\s+)?(?:private|personal|conversation|stored)\s+(?:data|fields?|history)"),

    # --- Phase 12 additions: encoding evasion text forms ---
    re.compile(r"(?i)i\s*-\s*g\s*-\s*n\s*-\s*o\s*-\s*r\s*-\s*e\s+a\s*-\s*l\s*-\s*l"),   # I-g-n-o-r-e a-l-l
    re.compile(r"(?i)\bign.{0,3}re\s+.{0,10}(?:prev.{0,5}ous|all|prior)\s+.{0,10}instru"),  # unicode-spaced ignore
    re.compile(r"(?i)%49%67%6[Ee]%6[Ff]%72%65"),   # URL-encoded "Ignore"
    re.compile(r"(?i)\\u0049\\u0067\\u006[Ee]"),    # unicode escape I, g, n
    re.compile(r"(?i)&#(?:73|105);&#(?:103|71);&#(?:110|78);"),  # HTML entity Ign...
    re.compile(r"(?i)&#\d+;&#\d+;&#\d+;&#\d+;&#\d+;&#\d+;"),    # dense HTML entity sequence
    re.compile(r"(?i)Ign\\u006[Ff]re\b"),            # partial unicode escape in ignore
    re.compile(r"(?i)system\\\s+prompt"),             # system\ prompt (escaped space)
]

SQLI_PATTERNS = [
    re.compile(r"(?i)('|\")\s*;\s*drop\s+table\b"),
    re.compile(r"(?i)\bunion\s+(?:all\s+)?select\b"),
    re.compile(r"(?i)\bor\s+['\"']?\d+['\"']?\s*=\s*['\"']?\d+['\"']?\b"),
    re.compile(r"(?i)\bexec\s*\(\s*char\("),
    # Phase 12 additions
    re.compile(r"(?i);\s*(?:insert|delete|update|drop|create|alter|truncate)\s+\b"),
    re.compile(r"(?i)\bwaitfor\s+delay\b"),
    re.compile(r"(?i)\bsleep\s*\(\s*\d+\s*\)"),
    re.compile(r"(?i)\bupdatexml\s*\("),
    re.compile(r"(?i)\binformation_schema\.tables\b"),
    re.compile(r"(?i)\b(?:having|where)\s+\d+\s*=\s*\d+\s*--"),
    re.compile(r"(?i)\bxp_cmdshell\b"),
    re.compile(r"(?i)select%20\*%20from\b"),           # URL-encoded SELECT
    re.compile(r"['\"](?:\s*OR\s*|\+OR\+)['\"][a-z0-9]+'=['\"][a-z0-9]"),  # OR 'a'='a form
    re.compile(r"q=[^&\s]*'[+%20]*OR[+%20]*'"),        # URL query string OR injection
]

PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"(?:\.\.\/|\.\.\\|%2e%2e%2f|%2e%2e/)"),
    re.compile(r"(?:/etc/passwd|/etc/shadow|c:\\windows\\system32)"),
    # Phase 12 additions
    re.compile(r"(?i)/etc/(?:hosts|shadow|sudoers|crontab|ssh)"),
    re.compile(r"(?i)/proc/self/"),
    re.compile(r"(?i)c:\\windows\\(?:system32|drivers)"),
    re.compile(r"(?i)file:///(?:etc|proc|c:)"),
    re.compile(r"(?i)\.{4,}/"),                        # ....//
    re.compile(r"(?i)(?:app|backend|config)/.*?(?:settings|\.env|secrets?)"),
]



class InjectionGate:
    """
    Layer 1 Hard-Gate Security Validator (Phase 07).
    Enforces non-additive, hard rejection on prompt injection, SQLi, command injection,
    and path traversal attempts.
    """

    def __init__(self, max_length: Optional[int] = None, risk_threshold: Optional[float] = None):
        self.max_length = max_length or settings.security.max_query_chars
        self.risk_threshold = risk_threshold if risk_threshold is not None else settings.security.injection_risk_threshold
        # In-memory query hash cache for L1/L1.5 deduplication
        self._cache: Dict[str, Dict[str, Any]] = {}

    def compute_query_hash(self, text: str) -> str:
        """Computes SHA-256 hash of normalized text."""
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def evaluate_query(self, message: str) -> Tuple[bool, Optional[str], float, str]:
        """
        Evaluates input query against security hard gates.
        Returns:
            (is_safe, block_reason, risk_score, query_hash)
        """
        query_hash = self.compute_query_hash(message)

        # L1/L1.5 Query Hash Deduplication Check
        if query_hash in self._cache:
            cached = self._cache[query_hash]
            return cached["is_safe"], cached["block_reason"], cached["risk_score"], query_hash

        # 1. Payload Length Check
        if len(message) > self.max_length:
            reason = f"Query length ({len(message)}) exceeds maximum limit of {self.max_length} characters."
            result = (False, reason, 1.0, query_hash)
            self._cache[query_hash] = {"is_safe": False, "block_reason": reason, "risk_score": 1.0}
            logger.warning(f"Injection Gate Block: {reason}")
            return result

        risk_score = 0.0

        # 2. Path Traversal Hard Gate
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern.search(message):
                reason = "Potential path traversal attempt detected."
                self._cache[query_hash] = {"is_safe": False, "block_reason": reason, "risk_score": 1.0}
                logger.warning(f"Injection Gate Block: {reason}")
                return False, reason, 1.0, query_hash

        # 3. SQL / Command Injection Hard Gate
        for pattern in SQLI_PATTERNS:
            if pattern.search(message):
                reason = "Potential SQL/command injection probe detected."
                self._cache[query_hash] = {"is_safe": False, "block_reason": reason, "risk_score": 0.95}
                logger.warning(f"Injection Gate Block: {reason}")
                return False, reason, 0.95, query_hash

        # 4. Prompt Injection & Jailbreak Hard Gate
        for pattern in INJECTION_PATTERNS:
            if pattern.search(message):
                risk_score = max(risk_score, 0.95)
                reason = f"Potential prompt injection detected (pattern: {pattern.pattern})."
                self._cache[query_hash] = {"is_safe": False, "block_reason": reason, "risk_score": risk_score}
                logger.warning(f"Injection Gate Block: {reason}")
                return False, reason, risk_score, query_hash

        # 5. Threshold Hard Gate Evaluation (Strict Non-Additive)
        is_safe = risk_score < self.risk_threshold
        block_reason = None if is_safe else f"Injection risk score ({risk_score:.2f}) meets or exceeds hard threshold ({self.risk_threshold:.2f})."

        self._cache[query_hash] = {
            "is_safe": is_safe,
            "block_reason": block_reason,
            "risk_score": risk_score
        }
        return is_safe, block_reason, risk_score, query_hash

    def validate(self, message: str) -> Tuple[bool, Optional[str]]:
        is_safe, reason, _, _ = self.evaluate_query(message)
        return is_safe, reason


injection_gate = InjectionGate()
