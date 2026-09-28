import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.statute_sync import statute_sync_service
from app.services.citation_graph_service import citation_graph_service
from app.mcp.server_manager import mcp_server_manager

client = TestClient(app)


def test_statute_sync_indexes_only_the_local_corpus():
    """
    The library reflects exactly the files in the corpus directory: no built-in acts,
    and every act carries its manifest provenance (unverified unless a date was recorded).
    """
    import os
    from app.ingestion.statutory_corpus import acts_dir

    corpus_files = [f for f in os.listdir(acts_dir()) if f.endswith(".txt")]
    result = statute_sync_service.sync_all_statutes()
    assert result["statutes_synced"] == len(corpus_files)

    data = client.get("/statutes/catalog").json()
    assert data["total_acts"] == len(corpus_files)
    for item in data["catalog"]:
        assert item["source"] == "local_corpus"
        assert item["legal_status"] in ("in_force", "amended", "repealed", "unverified")
        assert item["indexed_sections_count"] == item["nominal_sections_count"]


def test_statutes_catalog_search_and_domain_filter():
    data = client.get("/statutes/catalog").json()
    assert data["catalog"], "corpus fixture must provide at least one act"
    first = data["catalog"][0]

    by_domain = client.get(f"/statutes?domain={first['domain']}").json()
    assert all(s["domain"] == first["domain"] for s in by_domain["catalog"])
    assert first["slug"] in [s["slug"] for s in by_domain["catalog"]]

    assert client.get("/statutes?q=zz-no-such-act-zz").json()["catalog"] == []


def test_statute_detail_and_section_endpoint():
    # Statute detail
    resp = client.get("/statutes/it_act_2000")
    assert resp.status_code == 200
    statute = resp.json()
    assert "sections" in statute
    assert len(statute["sections"]) > 0

    # Section detail
    resp_sec = client.get("/statutes/it_act_2000/sections/66")
    assert resp_sec.status_code == 200
    sec_data = resp_sec.json()
    assert sec_data["number"] == "66"
    assert "computer related offences" in sec_data["heading"].lower()
    assert sec_data["act_slug"] == "it_act_2000"


def test_citation_graph_empty_state_and_real_edges():
    """
    Spec 04 §4.4: Verify fresh conversation starts with empty state (zero fake nodes),
    and grows exclusively from real recorded citations.
    """
    # 1. Empty conversation produces empty state without fake seed statutes
    resp_empty = client.get("/statutes/graph?conversation_id=fresh_conv_12345&scope=conversation")
    assert resp_empty.status_code == 200
    empty_data = resp_empty.json()
    assert empty_data["empty_state"] is True
    assert len(empty_data["nodes"]) == 0
    assert len(empty_data["links"]) == 0

    # 2. Record real LLM citations
    sample_citations = [
        {"act": "Information Technology Act, 2000", "act_slug": "it_act_2000", "section": "66"},
        {"act": "Information Technology Act, 2000", "act_slug": "it_act_2000", "section": "43"}
    ]
    edges_added = citation_graph_service.record_citations(
        conversation_id="active_conv_999",
        message_id="msg_test_01",
        citations=sample_citations
    )
    assert edges_added >= 2

    # 3. Query conversation scope graph
    resp_active = client.get("/statutes/graph?conversation_id=active_conv_999&scope=conversation")
    assert resp_active.status_code == 200
    graph_data = resp_active.json()
    assert graph_data["empty_state"] is False
    assert len(graph_data["nodes"]) >= 2
    node_labels = [n["label"] for n in graph_data["nodes"]]
    assert any("Section 66" in l for l in node_labels)

    # Verify relation labels come from real relations (no hardcoded mock labels)
    link_relations = [l["relation"] for l in graph_data["links"]]
    assert "contains" in link_relations or "co_cited_in_claim" in link_relations


def test_mcp_server_manager_lifecycle_and_discovery():
    """
    Spec 04 §2.1 & §2.2: Verify 4 canonical Indian legal MCP servers are registered,
    report honest health status, and support auto-discovery.
    """
    # 1. MCP status endpoint
    resp = client.get("/mcp/status")
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["enabled"] is True
    active_srvs = {s["name"]: s for s in status_data["active_servers"]}
    assert "ansvar-systems-india-law-mcp" in active_srvs
    assert "themis-mcp" in active_srvs
    assert "nyaya-mcp" in active_srvs
    assert "taxbykk-mcp" in active_srvs

    # 2. Auto-discovery endpoint
    resp_disc = client.post("/mcp/discover")
    assert resp_disc.status_code == 200
    disc_data = resp_disc.json()
    assert disc_data["total_discovered"] >= 8

    # 3. Reconnect endpoint
    resp_recon = client.post("/mcp/servers/themis-mcp/reconnect")
    assert resp_recon.status_code == 200
    recon_data = resp_recon.json()
    assert recon_data["server"]["name"] == "themis-mcp"
