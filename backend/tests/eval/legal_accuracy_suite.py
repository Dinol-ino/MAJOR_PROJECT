"""
Phase 12 — Legal Accuracy Eval Suite.

Tests the extended legal benchmark dataset (25 cases) against the system's
evaluation harness. Validates:
  1. Refusal on out-of-corpus / out-of-scope questions
  2. Superseded provision detection
  3. Multi-hop citation correctness (expected section references)
  4. Freshness-sensitive case handling (must not silently hallucinate new law)
  5. Conflict detection flag cases
  6. EvalHarness integration — load_dataset, evaluate_adversarial_security,
     evaluate_faithfulness_and_grounding all still functional after extension
"""
import os
import sys
import json
import pytest
from typing import List, Dict, Any

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.eval.eval_harness import EvalHarness

DATASET_PATH = os.path.join(
    _BACKEND_DIR, "app", "eval", "legal_benchmark_dataset.json"
)


@pytest.fixture(scope="module")
def harness():
    return EvalHarness()


@pytest.fixture(scope="module")
def dataset() -> List[Dict[str, Any]]:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Dataset structure tests
# ---------------------------------------------------------------------------

class TestLegalDatasetStructure:

    def test_dataset_has_minimum_entries(self, dataset):
        assert len(dataset) >= 25, (
            f"Legal benchmark dataset has only {len(dataset)} entries; expected >=25."
        )

    def test_all_entries_have_required_fields(self, dataset):
        required = {"id", "category", "query", "should_refuse"}
        for item in dataset:
            missing = required - set(item.keys())
            assert not missing, f"Entry {item.get('id')} missing fields: {missing}"

    def test_categories_represented(self, dataset):
        cats = {item["category"] for item in dataset}
        required_cats = {
            "direct_lookup", "multi_hop", "missing_context_refusal",
            "superseded_trap", "citation_correctness",
        }
        missing_cats = required_cats - cats
        assert not missing_cats, f"Missing required categories: {missing_cats}"

    def test_freshness_sensitive_cases_present(self, dataset):
        freshness = [i for i in dataset if i.get("freshness_sensitive")]
        assert len(freshness) >= 2, "Need at least 2 freshness-sensitive test cases."

    def test_conflict_detection_cases_present(self, dataset):
        conflict = [i for i in dataset if i.get("conflict_present")]
        assert len(conflict) >= 1, "Need at least 1 conflict-detection test case."

    def test_superseded_trap_cases_present(self, dataset):
        superseded = [i for i in dataset if i["category"] == "superseded_trap"]
        assert len(superseded) >= 2, "Need at least 2 superseded_trap test cases."

    def test_refusal_cases_present(self, dataset):
        refusals = [i for i in dataset if i["should_refuse"]]
        assert len(refusals) >= 5, "Need at least 5 should_refuse=True cases."

    def test_non_refusal_cases_present(self, dataset):
        non_refusals = [i for i in dataset if not i["should_refuse"]]
        assert len(non_refusals) >= 10, "Need at least 10 should_refuse=False cases."


# ---------------------------------------------------------------------------
# Refusal correctness
# ---------------------------------------------------------------------------

class TestRefusalBehavior:
    """
    Out-of-corpus questions (maritime law, tax law, procedure) must be refused.
    We test this at the dataset level: refused cases have `should_refuse=True`
    and the EvalHarness must correctly classify them.
    """

    def test_eval_harness_loads_extended_dataset(self, harness, dataset):
        loaded = harness.load_dataset()
        assert len(loaded) >= 25, "EvalHarness.load_dataset() did not load extended dataset."

    def test_should_refuse_case_maritime(self, dataset):
        """Maritime boundary question must be marked as requiring refusal."""
        maritime = next(
            (i for i in dataset if "maritime" in i["query"].lower()), None
        )
        assert maritime is not None, "Maritime boundary test case not found in dataset."
        assert maritime["should_refuse"] is True

    def test_should_refuse_case_gst(self, dataset):
        """GST/tax question must be marked as requiring refusal."""
        gst = next(
            (i for i in dataset if "gst" in i["query"].lower() or "tax" in i["query"].lower()),
            None
        )
        assert gst is not None, "GST/tax test case not found in dataset."
        assert gst["should_refuse"] is True

    def test_should_refuse_case_court_procedure(self, dataset):
        """Court procedure question must be marked as requiring refusal."""
        procedure = next(
            (i for i in dataset if "writ petition" in i["query"].lower()), None
        )
        assert procedure is not None, "Court procedure test case not found in dataset."
        assert procedure["should_refuse"] is True


# ---------------------------------------------------------------------------
# Superseded provision detection
# ---------------------------------------------------------------------------

class TestSupersededProvisionDetection:
    """Superseded sections must have expected_answer_contains='superseded'."""

    def test_superseded_trap_cases_marked_correctly(self, dataset):
        traps = [i for i in dataset if i["category"] == "superseded_trap"]
        failures = []
        for trap in traps:
            expected = (trap.get("expected_answer_contains") or "").lower()
            if "superseded" not in expected and "repeal" not in expected:
                failures.append(
                    f"[{trap['id']}] superseded_trap case does not expect 'superseded' in answer: "
                    f"expected='{trap.get('expected_answer_contains')}'"
                )
        assert not failures, "\n".join(failures)

    def test_superseded_cases_have_should_refuse_true(self, dataset):
        traps = [i for i in dataset if i["category"] == "superseded_trap"]
        for trap in traps:
            assert trap["should_refuse"] is True, (
                f"[{trap['id']}] superseded_trap cases must have should_refuse=True."
            )


# ---------------------------------------------------------------------------
# Multi-hop citation correctness
# ---------------------------------------------------------------------------

class TestMultiHopCitations:
    """Multi-hop cases must reference multiple sections in ground_truth_section."""

    def test_multi_hop_cases_have_multiple_sections(self, dataset):
        multi_hop = [i for i in dataset if i["category"] == "multi_hop"]
        assert len(multi_hop) >= 2, "Need at least 2 multi-hop cases."
        for case in multi_hop:
            sections = case.get("ground_truth_section") or ""
            assert "," in sections, (
                f"[{case['id']}] multi_hop case should reference multiple sections, "
                f"got: '{sections}'"
            )

    def test_citation_correctness_cases_have_section_in_expected_answer(self, dataset):
        citation_cases = [i for i in dataset if i["category"] == "citation_correctness"]
        for case in citation_cases:
            expected = case.get("expected_answer_contains") or ""
            section = case.get("ground_truth_section") or ""
            # Expected answer should reference the section number
            assert any(
                seg.strip() in expected
                for seg in section.split(",")
            ), (
                f"[{case['id']}] citation_correctness case expected answer '{expected}' "
                f"does not mention ground-truth section '{section}'."
            )


# ---------------------------------------------------------------------------
# Freshness handling
# ---------------------------------------------------------------------------

class TestFreshnessHandling:
    """Freshness-sensitive cases must flag that the answer may be stale."""

    def test_freshness_cases_have_note_field(self, dataset):
        freshness = [i for i in dataset if i.get("freshness_sensitive")]
        for case in freshness:
            assert "note" in case, (
                f"[{case['id']}] freshness_sensitive case missing 'note' field."
            )

    def test_dpdpa_case_is_freshness_sensitive(self, dataset):
        dpdpa = next(
            (i for i in dataset if "dpdpa" in i["query"].lower() or "2023" in i["query"].lower()),
            None
        )
        assert dpdpa is not None, "DPDPA 2023 freshness test case not found."
        assert dpdpa.get("freshness_sensitive") is True


# ---------------------------------------------------------------------------
# EvalHarness integration
# ---------------------------------------------------------------------------

class TestEvalHarnessIntegration:
    """Ensures EvalHarness still functions correctly after Phase 12 extension."""

    def test_load_dataset_returns_list(self, harness):
        data = harness.load_dataset()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_evaluate_adversarial_security_returns_accuracy(self, harness):
        result = harness.evaluate_adversarial_security()
        assert "adversarial_accuracy" in result
        assert 0.0 <= result["adversarial_accuracy"] <= 1.0
        # Phase 12 minimum threshold: 75%
        assert result["adversarial_accuracy"] >= 0.75, (
            f"Adversarial security accuracy {result['adversarial_accuracy']:.0%} < 75% minimum."
        )

    def test_evaluate_faithfulness_and_grounding(self, harness):
        chunks = [{"act": "IT Act 2000", "section": "66", "text": "Section 66 governs computer offences."}]
        answer = "Under Section 66 of IT Act 2000, computer offences are illegal."
        result = harness.evaluate_faithfulness_and_grounding(answer, chunks)
        assert "faithfulness_score" in result
        assert result["faithfulness_score"] > 0.0

    def test_run_full_eval_suite_passes(self, harness):
        result = harness.run_full_eval_suite()
        assert result["overall_status"] == "PASSED"
        assert "faithfulness_metric" in result
        assert "adversarial_injection_defense" in result
