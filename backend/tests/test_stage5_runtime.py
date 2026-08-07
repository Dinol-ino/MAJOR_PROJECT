import pytest
from app.system.hardware_detector import HardwareDetector
from app.system.model_registry import ModelRegistry
from app.runtime.runtime_manager import RuntimeManager
from app.runtime.context_builder import ContextBuilder
from app.runtime.token_budget_manager import TokenBudgetManager
from app.runtime.citation_builder import CitationBuilder
from app.runtime.hallucination_detector import HallucinationDetector
from app.runtime.confidence_scorer import ConfidenceScorer

def test_hardware_detector():
    hw = HardwareDetector.detect(force_refresh=True)
    assert hw.cpu_cores >= 1
    assert hw.ram_total_gb > 0.0
    assert hw.storage_free_gb >= 0.0
    assert hw.platform_name in ["windows", "linux", "darwin"]

def test_model_registry():
    reg = ModelRegistry()
    all_models = reg.all_models()
    assert len(all_models) >= 2

    hw = HardwareDetector.detect()
    recs = reg.recommended_for(hw)
    assert len(recs) >= 1

def test_runtime_manager_switch():
    assert RuntimeManager.switch("mock") is True
    runtime = RuntimeManager.get()
    assert runtime is not None

def test_context_builder_and_budget():
    builder = ContextBuilder()
    chunks = [{"act": "IPC", "section": "302", "text": "Punishment for murder", "trust_score": 0.9}]
    pkg = builder.build(query="What is murder punishment?", retrieved_chunks=chunks)
    assert "[SYSTEM INSTRUCTION]" in pkg.full_prompt
    assert "Punishment for murder" in pkg.full_prompt

    budget = TokenBudgetManager(context_limit=4096)
    fitted, truncated = budget.fit_chunks(pkg.token_count, chunks)
    assert len(fitted) == 1
    assert truncated == 0

def test_citations_and_scoring():
    chunks = [{"act": "IPC", "section": "302", "text": "Punishment for murder text.", "trust_score": 0.95}]
    citation_builder = CitationBuilder()
    citations = citation_builder.build(chunks)
    assert len(citations) == 1
    assert citations[0].act == "IPC"
    assert citations[0].section == "302"

    detector = HallucinationDetector()
    report = detector.detect("Under Section 302 IPC, murder is punishable.", chunks)
    assert report.is_flagged is False

    scorer = ConfidenceScorer()
    score = scorer.score("Under Section 302 IPC, murder is punishable.", chunks, report)
    assert 0.0 <= score <= 1.0
