"""
Phase 12 — Mutation Checker.

Validates that the security eval suite is NOT vacuously passing.
Deliberately breaks the InjectionGate by monkey-patching its evaluate_query
to always return is_safe=True, then re-runs the security assertions.

Expected outcome: the security suite CATCHES the regression.
If the mutation goes undetected, the checker raises AssertionError —
meaning the eval suite is not doing its job.

Run:
    pytest backend/tests/eval/mutation_check.py -v
"""
import os
import sys
import json
import pytest
from unittest.mock import patch

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.security.injection_gate import InjectionGate

ATTACKS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "attack_suite", "attacks.json"
)

HARD_GATE_CATEGORIES = {
    "direct_injection", "jailbreak", "sqli", "path_traversal", "encoding_evasion"
}


def _load_attacks():
    with open(ATTACKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_hard_gate_check(gate) -> tuple:
    """
    Re-implements the core security suite assertion against the given gate.
    Returns (failures, tested_count).
    """
    all_vectors = _load_attacks()
    failures = []
    tested = 0
    for v in all_vectors:
        if v["category"] not in HARD_GATE_CATEGORIES or not v["should_block"]:
            continue
        tested += 1
        is_safe, reason, score, _ = gate.evaluate_query(v["prompt"])
        if is_safe:
            failures.append(
                f"[ID={v['id']} cat={v['category']}] BYPASS: gate returned is_safe=True."
            )
    return failures, tested


# ---------------------------------------------------------------------------
# Baseline: confirm the REAL gate passes the suite
# ---------------------------------------------------------------------------

class TestBaselineGateIsWorking:
    """Sanity check: the unmodified InjectionGate must pass the security suite."""

    def test_real_gate_blocks_all_hard_gate_vectors(self):
        gate = InjectionGate()
        failures, tested = _run_hard_gate_check(gate)
        assert tested > 0, "No hard-gate vectors found — check attacks.json path."
        assert not failures, (
            f"Baseline FAILED: {len(failures)}/{tested} hard-gate vectors bypassed real InjectionGate.\n"
            + "\n".join(failures)
        )


# ---------------------------------------------------------------------------
# Mutation: break the gate, confirm suite catches it
# ---------------------------------------------------------------------------

class TestMutationCaughtBySuite:
    """
    Deliberately introduces a regression and confirms the eval suite detects it.
    This validates the suite is not vacuously passing.
    """

    def test_broken_gate_is_caught_by_security_suite(self):
        """
        Mutation: InjectionGate.evaluate_query is patched to always return is_safe=True.
        The security suite must catch this regression.
        """
        gate = InjectionGate()

        def always_safe(message):
            """Deliberately broken gate — accepts everything."""
            query_hash = gate.compute_query_hash(message)
            return True, None, 0.0, query_hash

        # Apply the mutation
        with patch.object(gate, "evaluate_query", side_effect=always_safe):
            failures, tested = _run_hard_gate_check(gate)

        # The broken gate MUST produce failures — if it doesn't, our eval suite
        # is vacuously passing and this mutation check itself fails.
        assert tested > 0, "No hard-gate vectors found — attacks.json issue."
        assert len(failures) > 0, (
            "MUTATION NOT CAUGHT: The security eval suite passed despite a gate that "
            "accepts ALL inputs. The eval suite is vacuously passing — fix the assertions."
        )

        # Quantify: the mutation must cause at least 80% of hard-gate vectors to fail
        bypass_rate = len(failures) / tested
        assert bypass_rate >= 0.80, (
            f"Mutation only caught {bypass_rate:.0%} of hard-gate bypasses "
            f"(expected >=80%). Eval suite coverage is insufficient."
        )

    def test_partial_mutation_caught(self):
        """
        Partial mutation: gate blocks only even-indexed vectors.
        Suite should still catch significant bypass rate.
        """
        gate = InjectionGate()
        call_count = [0]

        original_evaluate = gate.evaluate_query.__func__ if hasattr(gate.evaluate_query, '__func__') else None

        def alternating_gate(message):
            call_count[0] += 1
            query_hash = gate.compute_query_hash(message)
            # Let odd calls through (is_safe=True), block even calls
            if call_count[0] % 2 == 1:
                return True, None, 0.0, query_hash  # bypass
            return False, "blocked by alternating gate", 0.95, query_hash

        with patch.object(gate, "evaluate_query", side_effect=alternating_gate):
            failures, tested = _run_hard_gate_check(gate)

        # ~50% bypass rate should be caught
        assert len(failures) > 0, (
            "PARTIAL MUTATION NOT CAUGHT: 50% bypass rate went undetected."
        )


# ---------------------------------------------------------------------------
# Eval run store smoke test
# ---------------------------------------------------------------------------

class TestEvalRunStore:
    """Smoke test for the EvalRunStore (trend tracking)."""

    def test_save_and_retrieve_category_result(self, tmp_path):
        from app.eval.run_store import EvalRunStore, new_run_id
        store = EvalRunStore(db_path=str(tmp_path / "eval_test.db"))
        run_id = new_run_id()

        store.save_category_result(
            run_id=run_id,
            category="security",
            score=0.97,
            pass_count=97,
            total_count=100,
            status="PASS",
            details={"test": "smoke"},
            git_commit="abc1234",
        )

        summary = store.get_run_summary(run_id)
        assert len(summary) == 1
        assert summary[0]["category"] == "security"
        assert summary[0]["score"] == 0.97
        assert summary[0]["pass_count"] == 97
        assert summary[0]["status"] == "PASS"

    def test_trend_retrieval(self, tmp_path):
        from app.eval.run_store import EvalRunStore, new_run_id
        store = EvalRunStore(db_path=str(tmp_path / "trend_test.db"))

        for i in range(5):
            store.save_category_result(
                run_id=new_run_id(),
                category="memory",
                score=0.8 + i * 0.04,
                pass_count=8 + i,
                total_count=10,
                status="PASS",
            )

        trend = store.get_trend("memory", limit=10)
        assert len(trend) == 5, f"Expected 5 trend rows, got {len(trend)}"
        scores = [r["score"] for r in trend]
        # Newest first — highest score should be first
        assert scores[0] >= scores[-1], "Trend not returning newest-first order."

    def test_new_run_id_is_unique(self):
        from app.eval.run_store import new_run_id
        ids = {new_run_id() for _ in range(100)}
        assert len(ids) == 100, "new_run_id() produced duplicates."
