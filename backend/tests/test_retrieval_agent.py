from app.agents import retrieval_agent as ra


def test_plan_splits_section_comparison():
    subs = ra.plan_subqueries("Compare Section 420 of the Indian Penal Code and Section 318 of the Bharatiya Nyaya Sanhita")
    assert len(subs) == 2 and "420" in subs[0] and "318" in subs[1]


def test_plan_splits_versus_and_leaves_simple_queries_alone():
    assert len(ra.plan_subqueries("bail under BNSS versus anticipatory bail")) == 2
    assert ra.plan_subqueries("What is punishment for cheating?") == ["What is punishment for cheating?"]


def test_plan_is_capped():
    q = " ".join(f"Section {n} of the Indian Penal Code" for n in (1, 2, 3, 4, 5, 6))
    assert len(ra.plan_subqueries(q)) == ra.MAX_SUBQUERIES


def test_retries_uncovered_subquery_once_then_stops_and_dedupes():
    calls = []
    def fetch(q):
        calls.append(q)
        return [{"act": "A", "section": "1", "text": "alpha"}] if "alpha" in q else []
    out = ra.run("alpha thing versus beta thing", fetch, lambda sq, ch: bool(ch) and "alpha" in sq, max_chunks=5)
    assert calls.count("beta thing") == 2          # one retry, then stop
    assert out["steps"].count("retrieve") == 2 and out["steps"][-1] == "merge"
    assert len(out["chunks"]) == 1


def test_flag_is_off_by_default():
    from app.config import settings
    assert settings.retrieval.agentic_retrieval_enabled is False
