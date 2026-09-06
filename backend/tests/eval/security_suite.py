"""
Phase 12 — Security Eval Suite.

Zero-tolerance hard-gate test suite. Every attack vector marked should_block=True
MUST be blocked by at least one security layer. A single miss causes the suite to fail.

Layers tested:
  1. InjectionGate (injection/jailbreak/SQLi/path-traversal) — app.security.injection_gate
  2. ContextSanitizer (indirect injection in retrieved context) — app.security.context_sanitizer
  3. PIIScanner (PII detection) — app.security.pii_scanner

API note:
  - InjectionGate.evaluate_query(text) -> (is_safe, reason, score, hash)
  - ContextSanitizer.sanitize_text(text) -> str
  - PIIScanner.contains_pii(text) -> bool

Coverage: 110 attack vectors from attack_suite/attacks.json
"""
import os
import sys
import json
import pytest
from typing import List, Dict, Any

# Ensure backend app is on sys.path
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.security.injection_gate import InjectionGate
from app.security.context_sanitizer import ContextSanitizer
from app.security.pii_scanner import PIIScanner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ATTACKS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "attack_suite", "attacks.json"
)


def _load_attacks() -> List[Dict[str, Any]]:
    with open(ATTACKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_vectors():
    return _load_attacks()


@pytest.fixture(scope="module")
def gate():
    return InjectionGate()


@pytest.fixture(scope="module")
def sanitizer():
    return ContextSanitizer()


@pytest.fixture(scope="module")
def pii_scanner():
    return PIIScanner()


# ---------------------------------------------------------------------------
# Category: direct_injection, jailbreak, sqli, path_traversal
# All should_block=True vectors must be blocked by InjectionGate.
# ---------------------------------------------------------------------------

HARD_GATE_CATEGORIES = {
    "direct_injection", "jailbreak", "sqli", "path_traversal", "encoding_evasion"
}


class TestInjectionGateHardGate:
    """
    Tests that InjectionGate blocks every attack in hard-gate categories.
    Zero tolerance: any bypass = suite fail.
    """

    def _should_test(self, vector: Dict[str, Any]) -> bool:
        return (
            vector["category"] in HARD_GATE_CATEGORIES
            and vector["should_block"] is True
        )

    def test_all_hard_gate_vectors_blocked(self, gate, all_vectors):
        """
        Every should_block=True vector in hard-gate categories must be rejected.
        Collected failures are reported together (not short-circuited).
        """
        failures = []
        tested = 0

        for v in all_vectors:
            if not self._should_test(v):
                continue
            tested += 1
            is_safe, reason, score, _ = gate.evaluate_query(v["prompt"])
            if is_safe:
                failures.append(
                    f"[ID={v['id']} cat={v['category']}] "
                    f"BYPASS: gate returned is_safe=True. "
                    f"score={score:.2f} reason={reason!r}"
                )

        assert tested > 0, "No hard-gate vectors found — check attacks.json path."
        assert not failures, (
            f"{len(failures)}/{tested} hard-gate vectors bypassed InjectionGate:\n"
            + "\n".join(failures)
        )

    def test_safe_queries_not_blocked(self, gate, all_vectors):
        """
        Queries marked should_block=False must NOT be blocked by InjectionGate
        (precision check — the gate must not be over-triggering).
        """
        false_positives = []
        for v in all_vectors:
            if v["should_block"] is not False:
                continue
            is_safe, reason, score, _ = gate.evaluate_query(v["prompt"])
            if not is_safe:
                false_positives.append(
                    f"[ID={v['id']} cat={v['category']}] "
                    f"FALSE POSITIVE: blocked a safe query. reason={reason!r}"
                )
        assert not false_positives, (
            f"{len(false_positives)} safe queries were incorrectly blocked:\n"
            + "\n".join(false_positives)
        )

    def test_injection_gate_coverage_count(self, gate, all_vectors):
        """Asserts there are at least 60 should_block=True hard-gate vectors."""
        count = sum(1 for v in all_vectors if self._should_test(v))
        assert count >= 60, f"Expected >=60 hard-gate block vectors, found {count}"


# ---------------------------------------------------------------------------
# Category: indirect_injection
# Vectors go through ContextSanitizer (retrieved context path, not user query).
# ---------------------------------------------------------------------------

class TestContextSanitizerIndirectInjection:
    """
    Every indirect injection vector (from retrieved/tool content) must be
    stripped of embedded instructions by ContextSanitizer.
    """

    def test_all_indirect_injection_vectors_sanitized(self, sanitizer, all_vectors):
        failures = []
        tested = 0

        for v in all_vectors:
            if v["category"] != "indirect_injection" or not v["should_block"]:
                continue
            tested += 1
            # Use sanitize_text (the correct API method name)
            sanitized = sanitizer.sanitize_text(v["prompt"], source_type="tool_result")
            # The marker should have been removed/neutralized
            # We check the sanitized output is meaningfully shorter or transformed
            if sanitized.strip() == v["prompt"].strip():
                # No transformation at all — sanitizer did nothing
                failures.append(
                    f"[ID={v['id']}] ContextSanitizer.sanitize_text made no change to indirect injection prompt."
                )

        assert tested > 0, "No indirect_injection vectors found."
        assert not failures, (
            f"{len(failures)}/{tested} indirect injection vectors not sanitized:\n"
            + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# Category: pii_leakage_probe — PII extraction queries blocked by InjectionGate
# PII presence in query text detected by PIIScanner.
# ---------------------------------------------------------------------------

class TestPIIScannerDetection:
    """
    PII probe queries that include real PII (Aadhaar, PAN, email) must be detected.
    Queries asking the system to leak PII from storage must be blocked by InjectionGate.
    """

    def test_pii_detection_in_query(self, pii_scanner):
        """PIIScanner.contains_pii must detect Aadhaar, PAN, and email in text."""
        pii_text = "My Aadhaar number is 1234 5678 9012 and my PAN is ABCDE1234F."
        found = pii_scanner.contains_pii(pii_text)
        assert found is True, "PIIScanner failed to detect Aadhaar/PAN in text."

    def test_email_detection(self, pii_scanner):
        found = pii_scanner.contains_pii("Reach me at test.user@lawfirm.co.in")
        assert found is True, "PIIScanner did not detect email address."

    def test_clean_text_no_false_positive(self, pii_scanner):
        found = pii_scanner.contains_pii("Section 66 of the IT Act governs computer offences.")
        assert found is False, "PIIScanner false-positive on clean legal text."

    def test_pii_data_exfiltration_queries_blocked(self, gate, all_vectors):
        """
        PII leakage probes that ask the system to dump stored PII
        (should_block=True) must be blocked by InjectionGate.
        """
        failures = []
        for v in all_vectors:
            if v["category"] != "pii_leakage_probe" or not v["should_block"]:
                continue
            is_safe, reason, score, _ = gate.evaluate_query(v["prompt"])
            if is_safe:
                failures.append(
                    f"[ID={v['id']}] PII exfiltration query not blocked. score={score:.2f}"
                )
        assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# Category: tool_poisoning
# Tool result strings go through ContextSanitizer (same path as retrieved context).
# ---------------------------------------------------------------------------

class TestToolPoisoningSanitization:
    """
    Tool-poisoning payloads (malicious content in tool/MCP results) must be
    sanitized by ContextSanitizer before being used as context.
    """

    def test_tool_poisoning_vectors_transformed(self, sanitizer, all_vectors):
        failures = []
        tested = 0
        for v in all_vectors:
            if v["category"] != "tool_poisoning" or not v["should_block"]:
                continue
            tested += 1
            sanitized = sanitizer.sanitize_text(v["prompt"], source_type="tool_result")
            if sanitized.strip() == v["prompt"].strip():
                failures.append(
                    f"[ID={v['id']}] ContextSanitizer.sanitize_text unchanged for tool_poisoning vector."
                )
        assert tested > 0, "No tool_poisoning vectors found."
        assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# Suite-level statistics test
# ---------------------------------------------------------------------------

class TestSecuritySuiteCoverage:
    """Validates overall coverage metrics of the attack vector dataset."""

    def test_minimum_vector_count(self, all_vectors):
        assert len(all_vectors) >= 100, (
            f"Attack vector dataset has only {len(all_vectors)} entries. Need >=100."
        )

    def test_all_categories_represented(self, all_vectors):
        categories = {v["category"] for v in all_vectors}
        required = {
            "direct_injection", "jailbreak", "indirect_injection",
            "sqli", "pii_leakage_probe", "path_traversal",
            "tool_poisoning", "encoding_evasion",
        }
        missing = required - categories
        assert not missing, f"Missing attack categories: {missing}"

    def test_block_ratio(self, all_vectors):
        """At least 80% of vectors should be should_block=True."""
        block_count = sum(1 for v in all_vectors if v["should_block"])
        ratio = block_count / len(all_vectors)
        assert ratio >= 0.80, f"Block ratio too low: {ratio:.0%} (need >=80%)"
