import pytest
from app.services.response_parser import response_parser, ParsedCitation
from app.defense.layer2_trusted_context import Layer2TrustedContext


def test_response_parser_deep_thinking_extraction():
    # 1. Closed deep_thinking tags
    raw = (
        "<deep_thinking>\n"
        "User is asking about Section 66 of IT Act.\n"
        "Penalty is 3 years imprisonment or 5 lakh fine.\n"
        "</deep_thinking>\n"
        "Answer: Section 66 provides punishment for computer-related offences."
    )
    cleaned, trace = response_parser.extract_deep_thinking(raw)
    assert trace is not None
    assert "User is asking about Section 66" in trace
    assert "Answer: Section 66" in cleaned
    assert "<deep_thinking>" not in cleaned

    # 2. Unclosed deep_thinking tags (Tier-0 model tolerance)
    raw_unclosed = (
        "<deep_thinking>\n"
        "Analysis in progress without closing tag..."
    )
    cleaned_unclosed, trace_unclosed = response_parser.extract_deep_thinking(raw_unclosed)
    assert trace_unclosed is not None
    assert "Analysis in progress" in trace_unclosed

    # 3. No deep thinking tags
    raw_plain = "Direct answer without reasoning tags."
    cleaned_plain, trace_plain = response_parser.extract_deep_thinking(raw_plain)
    assert trace_plain is None
    assert cleaned_plain == raw_plain


def test_response_parser_citations_and_superscripts():
    evidence = [
        {
            "id": "c1",
            "act": "Information Technology Act, 2000",
            "section": "66",
            "text": "Punishment for computer related offences up to 3 years."
        },
        {
            "id": "c2",
            "act": "Indian Penal Code, 1860",
            "section": "420",
            "text": "Cheating and dishonestly inducing delivery of property."
        }
    ]

    text = (
        "Unauthorized computer access is punishable under Section 66 [^S:IT_Act_2000|s66|p4]. "
        "Cheating is defined under Section 420 [^S:IPC_1860|s420|p12]. "
        "Non-existent provision cited [^S:Fictional_Act|s999]."
    )

    rendered, citations = response_parser.parse_citations(text, evidence_chunks=evidence)

    # Verify superscripts replaced tokens
    assert "[^1]" in rendered
    assert "[^2]" in rendered
    assert "[^3]" in rendered
    assert "[^S:" not in rendered

    # Verify parsed citations
    assert len(citations) == 3
    assert citations[0].section == "66"
    assert citations[0].page == 4
    assert citations[0].resolved is True

    assert citations[1].section == "420"
    assert citations[1].page == 12
    assert citations[1].resolved is True

    assert citations[2].section == "999"
    assert citations[2].resolved is False


def test_response_parser_grounding_score_calculation():
    # 1. Fully resolved citations (100%)
    cits_resolved = [
        ParsedCitation(index=1, act="IT Act", act_slug="it", section="66", resolved=True),
        ParsedCitation(index=2, act="IT Act", act_slug="it", section="43", resolved=True),
    ]
    score_100 = response_parser.compute_grounding_score(cits_resolved, "Substantive legal answer.")
    assert score_100 == 100.0

    # 2. Partially resolved with penalty
    cits_partial = [
        ParsedCitation(index=1, act="IT Act", act_slug="it", section="66", resolved=True),
        ParsedCitation(index=2, act="Ghost Act", act_slug="ghost", section="99", resolved=False),
    ]
    # 1/2 = 50%, penalty -15% = 35%
    score_partial = response_parser.compute_grounding_score(cits_partial, "Answer with orphan citation.")
    assert score_partial == 35.0

    # 3. Domain gate refusal (100%)
    score_refusal = response_parser.compute_grounding_score(
        [],
        "This workspace is restricted to Indian legal analysis. I can help with statutes, case law, procedure, or your uploaded case files."
    )
    assert score_refusal == 100.0

    # 4. Insufficient grounding message (100%)
    score_insuff = response_parser.compute_grounding_score(
        [],
        "Insufficient grounding in available sources. Please add the relevant act."
    )
    assert score_insuff == 100.0


def test_layer2_v4_prompt_assembly():
    layer2 = Layer2TrustedContext(enable_pii_scan=False)

    evidence = [{"text": "Sample Act Section 1 text", "act": "Sample Act", "section": "1"}]

    # 1. Reasoning effort = "off"
    prompt_off = layer2.build_prompt("What is section 1?", evidence, reasoning_effort="off")
    assert "<system_role>" in prompt_off
    assert "Nyaya-Core v4" in prompt_off
    assert "Do not emit <deep_thinking> tags." in prompt_off

    # 2. Reasoning effort = "high"
    prompt_high = layer2.build_prompt("What is section 1?", evidence, reasoning_effort="high")
    assert "You MUST emit <deep_thinking> reasoning before answering." in prompt_high

    # 3. Domain gate in v4 prompt
    assert "restricted to Indian legal analysis" in prompt_off
    assert "honesty_protocol" in prompt_off


def test_grounding_score_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.memory.durable_memory import DurableMemoryManager

    client = TestClient(app)
    durable_memory = DurableMemoryManager()

    msg = durable_memory.add_message(
        conversation_id="test_conv_grounding",
        role="assistant",
        content="Testing grounding breakdown",
        citations=[{"act": "IT Act", "section": "66", "quote": "Penalty text", "resolved": True}],
        grounding_score=95.0
    )
    msg_id = msg["id"]

    resp = client.get(f"/api/messages/{msg_id}/grounding")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] == msg_id
    assert data["grounding_score"] == 95.0
    assert data["total_citations"] == 1
    assert data["resolved_citations"] == 1
    assert data["unresolved_citations"] == 0


def test_streaming_reasoning_delta_extraction():
    import asyncio
    from app.runtime.streaming import stream_token_generator

    async def _test():
        async def mock_token_stream():
            yield "Answ"
            yield "er start. <deep_thi"
            yield "nking>Analyzing section 66"
            yield " thoroughly</deep_thinking>"
            yield " Conclusion."

        events = []
        async for event in stream_token_generator(mock_token_stream(), session_id="test_sess"):
            events.append(event)

        full_output = "".join(events)
        assert "event: reasoning_delta" in full_output
        assert "Analyzing section 66" in full_output
        assert "Conclusion" in full_output

    asyncio.run(_test())

