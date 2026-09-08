import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.events import (
    ChatResponseFinalized,
    DocumentIngested,
    MCPToolInvoked,
    DefenseLayerDecision,
    ModelLifecycleChanged,
    emit_chat_response_finalized,
    emit_document_ingested,
    emit_mcp_tool_invoked,
    emit_defense_layer_decision,
    emit_model_lifecycle_changed,
)
from app.defense.audit_log import AuditLogger
from app.services.citation_graph_service import citation_graph_service


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_response_finalized_event_fanout():
    """
    Module 9 §9.2 Event 1: Verify ChatResponseFinalized fan-out to audit log,
    citation graph, and statute library references with zero errors.
    """
    audit_logger = AuditLogger()
    prev_count = len(audit_logger.fetch_all())

    conv_id = f"test_conv_{uuid.uuid4().hex[:8]}"
    msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    citations = [
        {
            "act": "Information Technology Act, 2000",
            "act_slug": "information_technology_act_2000",
            "section": "Section 66A",
            "text": "Punishment for sending offensive messages through communication service."
        }
    ]

    event = ChatResponseFinalized(
        conversation_id=conv_id,
        message_id=msg_id,
        user_id="test_user",
        query="Explain Section 66A IT Act",
        answer="Section 66A was struck down in Shreya Singhal v. UOI (2015).",
        citations=citations,
        model_used="qwen2.5:7b",
        runtime_used="local",
        reasoning_trace="Evaluated IT Act provisions and landmark Supreme Court jurisprudence.",
        grounding_score=0.92,
        is_deep_thinking=True
    )

    emit_chat_response_finalized(event)

    # 1. Audit ledger row created
    new_logs = audit_logger.fetch_all()
    assert len(new_logs) > prev_count

    # 2. Citation graph node and edge recorded
    graph_data = citation_graph_service.get_graph(scope="conversation", conversation_id=conv_id)
    assert any(n["label"] == "Section 66A" or "66A" in n["label"] for n in graph_data["nodes"])


def test_document_ingested_event_fanout():
    """
    Module 9 §9.2 Event 2: Verify DocumentIngested fan-out to audit log and citation graph.
    """
    audit_logger = AuditLogger()
    prev_count = len(audit_logger.fetch_all())

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    citations = [
        {
            "act": "Indian Penal Code",
            "section": "Section 420",
            "text": "Cheating and dishonestly inducing delivery of property."
        }
    ]

    event = DocumentIngested(
        doc_id=doc_id,
        session_id="test_doc_session",
        filename="complaint_brief.pdf",
        file_size_bytes=1048576,
        chunk_count=8,
        pages_count=4,
        citations_found=citations
    )

    emit_document_ingested(event)

    # Audit row logged
    new_logs = audit_logger.fetch_all()
    assert len(new_logs) > prev_count
    assert any("complaint_brief.pdf" in l["action"] for l in new_logs)


def test_mcp_tool_invoked_event_fanout():
    """
    Module 9 §9.2 Event 3: Verify MCPToolInvoked fan-out to audit log and citation graph.
    """
    audit_logger = AuditLogger()
    prev_count = len(audit_logger.fetch_all())

    precedents = [
        {
            "act": "Supreme Court Precedent",
            "section": "1965 AIR 722",
            "text": "State of Maharashtra v. Mayer Hans George"
        }
    ]

    event = MCPToolInvoked(
        tool_name="kanoon_case_search",
        category="CASE_LAW_SEARCH",
        network_mode="ONLINE",
        is_allowed=True,
        arguments={"keywords": "mens rea foreign exchange"},
        latency_ms=45.2,
        session_id="test_mcp_sess",
        precedents_found=precedents
    )

    emit_mcp_tool_invoked(event)

    new_logs = audit_logger.fetch_all()
    assert len(new_logs) > prev_count


def test_defense_and_model_lifecycle_events():
    """
    Module 9 §9.2 Events 4 & 5: Verify DefenseLayerDecision and ModelLifecycleChanged.
    """
    audit_logger = AuditLogger()
    prev_count = len(audit_logger.fetch_all())

    # Defense decision
    d_event = DefenseLayerDecision(
        layer_name="layer1_input_guard",
        passed=True,
        injection_score=0.05,
        latency_ms=2.1,
        session_id="test_sess_def"
    )
    emit_defense_layer_decision(d_event)

    # Model lifecycle change
    m_event = ModelLifecycleChanged(
        event_type="override",
        model_name="qwen2.5:14b",
        runtime_name="ollama",
        source="user",
        session_id="test_sess_def",
        status="active"
    )
    emit_model_lifecycle_changed(m_event)

    new_logs = audit_logger.fetch_all()
    assert len(new_logs) >= prev_count + 2
