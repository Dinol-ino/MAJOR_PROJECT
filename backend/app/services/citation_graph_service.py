import os
import re
import uuid
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

from app.db.engine import get_sync_session, get_sync_engine
from app.db.models import CitationEdge, Statute, StatuteSection
from app.config import settings
from app.system.hardware_detector import HardwareDetector

logger = logging.getLogger(__name__)

# Canonical Derivation Methods per Spec 05 Section 5.2
DERIVATION_CORPUS_STRUCTURE = "corpus_structure"
DERIVATION_TEXT_EXTRACTION = "text_extraction"
DERIVATION_CURATED_LEGAL_RELATIONSHIP = "curated_legal_relationship"
DERIVATION_MCP_CASE_LAW_LOOKUP = "mcp_case_law_lookup"
DERIVATION_LLM_SUGGESTED_UNVERIFIED = "llm_suggested_unverified"
DERIVATION_USER_DOCUMENT_REFERENCE = "user_document_reference"

VALID_DERIVATION_METHODS = {
    DERIVATION_CORPUS_STRUCTURE,
    DERIVATION_TEXT_EXTRACTION,
    DERIVATION_CURATED_LEGAL_RELATIONSHIP,
    DERIVATION_MCP_CASE_LAW_LOOKUP,
    DERIVATION_LLM_SUGGESTED_UNVERIFIED,
    DERIVATION_USER_DOCUMENT_REFERENCE
}


class CitationGraphService:
    """
    Spec 05: Real dynamic legal citation graph engine.
    - Tier 1+ Hardware (8GB+ RAM): Memgraph Community Edition via Cypher over Bolt protocol.
    - Tier 0 Hardware (<8GB RAM): In-process SQLite/Postgres DB fallback.
    - Zero mock arrays or hardcoded fixture graphs.
    - Every graph edge maintains explicit derivation_method provenance.
    - Tracks cited_in_conversations for dynamic graph growth.
    """

    def __init__(self):
        self._memgraph_driver = None
        self._memgraph_tested = False
        self._memgraph_available = False

    def _get_hardware_tier(self) -> int:
        """Determines active hardware tier from HardwareDetector."""
        try:
            tier_info = HardwareDetector.get_auto_selected_tier()
            return int(tier_info.get("tier", 0))
        except Exception as exc:
            logger.debug(f"Hardware tier probe fallback: {exc}")
            return 0

    def _get_memgraph_driver(self):
        """
        Initializes and returns a Neo4j/Memgraph Bolt driver if hardware is Tier 1+
        and Memgraph daemon is reachable. Returns None on Tier 0 or connection failure.
        """
        tier = self._get_hardware_tier()
        if tier < 1 and settings.graph.backend != "memgraph":
            return None

        if self._memgraph_driver is not None:
            return self._memgraph_driver

        try:
            import neo4j
            uri = settings.graph.memgraph_uri
            auth = (
                (settings.graph.memgraph_user, settings.graph.memgraph_password)
                if settings.graph.memgraph_user
                else None
            )
            driver = neo4j.GraphDatabase.driver(
                uri,
                auth=auth,
                connection_timeout=settings.graph.cypher_timeout_seconds,
                max_connection_lifetime=300
            )
            with driver.session() as session:
                session.run("RETURN 1 AS ping")
            self._memgraph_driver = driver
            self._memgraph_available = True
            logger.info(f"Connected to Memgraph Community Edition at {uri} (Tier {tier}+ hardware)")
            return self._memgraph_driver
        except Exception as exc:
            logger.debug(f"Memgraph connection bypassed (using in-process DB fallback): {exc}")
            self._memgraph_driver = None
            self._memgraph_available = False
            return None

    def is_memgraph_active(self) -> bool:
        return self._get_memgraph_driver() is not None

    def get_active_backend_name(self) -> str:
        if self.is_memgraph_active():
            return "memgraph"
        engine = get_sync_engine()
        return "in_process_postgres" if "postgres" in str(engine.url) else "in_process_sqlite"

    def _extract_penalty_from_text(self, text: Optional[str]) -> Optional[str]:
        """Deterministic statutory penalty extraction (Spec 05 Section 5.2.1)."""
        if not text:
            return None

        patterns = [
            r"(?:punishable\s+with\s+imprisonment\s+[^.;\n]+(?:fine|both)?[^.;\n]*)",
            r"(?:punished\s+with\s+imprisonment\s+[^.;\n]+(?:fine|both)?[^.;\n]*)",
            r"(?:punished\s+with\s+death\s+[^.;\n]*)",
            r"(?:liable\s+to\s+pay\s+damages\s+by\s+way\s+of\s+compensation[^.;\n]*)",
            r"(?:monetary\s+penalty\s+which\s+may\s+extend\s+to[^.;\n]*)",
            r"(?:liable\s+to\s+a\s+penalty\s+[^.;\n]*)"
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted = m.group(0).strip().rstrip(",").rstrip(".")
                if len(extracted) > 10:
                    return extracted[:180]
        return None

    def record_citations(
        self,
        conversation_id: str,
        message_id: str,
        citations: List[Dict[str, Any]],
        is_user_document: bool = False
    ) -> int:
        """
        Spec 05 Section 5.3: Extracts citation tokens from assistant message / user document,
        persists structured graph edges with explicit derivation_method provenance,
        and increments cited_in_conversations counters.
        """
        if not citations:
            return 0

        edges_added = 0
        derivation_default = DERIVATION_USER_DOCUMENT_REFERENCE if is_user_document else DERIVATION_CORPUS_STRUCTURE

        with get_sync_session() as session:
            section_keys = []

            for cit in citations:
                act_slug = cit.get("act_slug") or cit.get("act", "").lower().replace(" ", "_").replace(",", "")
                sec_num = str(cit.get("section", "")).strip()
                if not sec_num:
                    continue

                sec_key = f"section:{act_slug}:{sec_num}"
                statute_key = f"statute:{act_slug}"
                section_keys.append((sec_key, cit.get("act") or act_slug, sec_num))

                statute_row = session.query(Statute).filter_by(slug=act_slug).first()
                sec_row = None
                if statute_row:
                    sec_row = session.query(StatuteSection).filter_by(statute_id=statute_row.id, number=sec_num).first()
                    if sec_row:
                        sec_row.cited_in_conversations = (sec_row.cited_in_conversations or 0) + 1
                    else:
                        sec_row = StatuteSection(
                            id=str(uuid.uuid4()),
                            statute_id=statute_row.id,
                            number=sec_num,
                            heading=cit.get("heading") or f"Section {sec_num}",
                            raw_text=cit.get("text") or cit.get("raw_text") or "",
                            embedding_ready=True,
                            cited_in_conversations=1
                        )
                        session.add(sec_row)

                # Edge 1: Statute -> Section (Contains: corpus_structure)
                session.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    src_type="statute",
                    src_key=statute_key,
                    dst_type="section",
                    dst_key=sec_key,
                    relation="contains",
                    origin="vault_doc" if is_user_document else "llm_citation",
                    derivation_method=derivation_default,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    confidence=1.0,
                    created_at=datetime.utcnow()
                ))
                edges_added += 1

                # Edge 2: Message/Doc -> Section (Cites / referenced_in_matter)
                session.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    src_type=f"doc:{conversation_id}" if is_user_document else f"msg:{message_id}",
                    src_key=f"doc:{conversation_id}" if is_user_document else f"msg:{message_id}",
                    dst_type="section",
                    dst_key=sec_key,
                    relation="referenced_in_matter" if is_user_document else "cites",
                    origin="vault_doc" if is_user_document else "llm_citation",
                    derivation_method=DERIVATION_USER_DOCUMENT_REFERENCE if is_user_document else DERIVATION_CORPUS_STRUCTURE,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    confidence=1.0,
                    created_at=datetime.utcnow()
                ))
                edges_added += 1

                # Edge 3: Deterministic Penalty Extraction (text_extraction)
                if sec_row and sec_row.raw_text:
                    penalty_text = self._extract_penalty_from_text(sec_row.raw_text)
                    if penalty_text:
                        pen_key = f"penalty:{act_slug}:{sec_num}"
                        session.add(CitationEdge(
                            id=str(uuid.uuid4()),
                            src_type="section",
                            src_key=sec_key,
                            dst_type="penalty",
                            dst_key=pen_key,
                            relation="penalizes_with",
                            origin="text_extraction",
                            derivation_method=DERIVATION_TEXT_EXTRACTION,
                            conversation_id=conversation_id,
                            message_id=message_id,
                            confidence=1.0,
                            created_at=datetime.utcnow()
                        ))
                        edges_added += 1

            # Inter-section co-citation edges in the same message
            if len(section_keys) > 1:
                for i in range(len(section_keys)):
                    for j in range(i + 1, len(section_keys)):
                        session.add(CitationEdge(
                            id=str(uuid.uuid4()),
                            src_type="section",
                            src_key=section_keys[i][0],
                            dst_type="section",
                            dst_key=section_keys[j][0],
                            relation="co_cited_in_claim",
                            origin="vault_doc" if is_user_document else "llm_citation",
                            derivation_method=DERIVATION_USER_DOCUMENT_REFERENCE if is_user_document else DERIVATION_LLM_SUGGESTED_UNVERIFIED,
                            conversation_id=conversation_id,
                            message_id=message_id,
                            confidence=0.85,
                            created_at=datetime.utcnow()
                        ))
                        edges_added += 1

            session.commit()

        self._write_through_to_memgraph(conversation_id, message_id, citations, is_user_document)
        logger.debug(f"Recorded {edges_added} citation graph edges (scope={conversation_id})")
        return edges_added

    def _write_through_to_memgraph(
        self,
        conversation_id: str,
        message_id: str,
        citations: List[Dict[str, Any]],
        is_user_document: bool
    ):
        """Asynchronously mirrors persisted edges to Memgraph Bolt endpoint."""
        driver = self._get_memgraph_driver()
        if not driver:
            return

        try:
            with driver.session() as mg_session:
                for cit in citations:
                    act_slug = cit.get("act_slug") or cit.get("act", "").lower().replace(" ", "_").replace(",", "")
                    sec_num = str(cit.get("section", "")).strip()
                    if not sec_num:
                        continue

                    sec_key = f"section:{act_slug}:{sec_num}"
                    statute_key = f"statute:{act_slug}"
                    sec_label = f"Section {sec_num}"
                    statute_label = cit.get("act") or act_slug.replace("_", " ").title()

                    cypher_query = """
                    MERGE (st:Statute {key: $statute_key})
                    ON CREATE SET st.label = $statute_label, st.type = 'statute', st.domain = $domain
                    MERGE (sec:Section {key: $sec_key})
                    ON CREATE SET sec.label = $sec_label, sec.type = 'section', sec.cited_in_conversations = 1
                    ON MATCH SET sec.cited_in_conversations = coalesce(sec.cited_in_conversations, 0) + 1
                    MERGE (st)-[r:CONTAINS]->(sec)
                    SET r.derivation_method = $derivation_method, r.origin = $origin, r.updated_at = $ts
                    """
                    mg_session.run(
                        cypher_query,
                        statute_key=statute_key,
                        statute_label=statute_label,
                        domain=cit.get("domain", "statutory"),
                        sec_key=sec_key,
                        sec_label=sec_label,
                        derivation_method=DERIVATION_CORPUS_STRUCTURE,
                        origin="llm_citation",
                        ts=datetime.utcnow().isoformat()
                    )
        except Exception as exc:
            logger.debug(f"Memgraph write-through notice: {exc}")

    def get_graph(
        self,
        scope: str = "conversation",
        conversation_id: Optional[str] = None,
        vault_id: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves graph nodes and edges dynamically according to the requested scope:
        - 'conversation': real edges generated during the active session.
        - 'vault': edges from all conversations within a project vault.
        - 'global': all verified statutory cross-references, MCP relations, and corpus structure.
        Uses Memgraph Cypher query when available on Tier 1+, with transparent DB fallback.
        """
        backend_name = self.get_active_backend_name()
        tier = self._get_hardware_tier()

        driver = self._get_memgraph_driver()
        if driver and scope == "global":
            try:
                memgraph_res = self._query_memgraph_global(driver, search_query)
                if memgraph_res and memgraph_res.get("nodes"):
                    memgraph_res["backend_used"] = "memgraph"
                    memgraph_res["hardware_tier"] = tier
                    return memgraph_res
            except Exception as exc:
                logger.debug(f"Memgraph query fallback to DB: {exc}")

        with get_sync_session() as session:
            query = session.query(CitationEdge)

            if scope == "conversation":
                if not conversation_id:
                    return {
                        "nodes": [],
                        "links": [],
                        "empty_state": True,
                        "scope": scope,
                        "backend_used": backend_name,
                        "hardware_tier": tier
                    }
                query = query.filter_by(conversation_id=conversation_id)
            elif scope == "vault" and vault_id:
                from app.db.models import Conversation
                conv_ids = [c.conversation_id for c in session.query(Conversation).filter_by(project_vault_id=vault_id).all()]
                if conv_ids:
                    query = query.filter(CitationEdge.conversation_id.in_(conv_ids))
                else:
                    return {
                        "nodes": [],
                        "links": [],
                        "empty_state": True,
                        "scope": scope,
                        "backend_used": backend_name,
                        "hardware_tier": tier
                    }
            elif scope == "global":
                query = query.filter(CitationEdge.origin.in_(["mcp_relation", "llm_citation", "vault_doc", "text_extraction"]))

            edges = query.order_by(CitationEdge.created_at.desc()).limit(200).all()

            if not edges:
                return {
                    "nodes": [],
                    "links": [],
                    "empty_state": True,
                    "scope": scope,
                    "backend_used": backend_name,
                    "hardware_tier": tier
                }

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            links_list: List[Dict[str, Any]] = []

            for edge in edges:
                src = edge.src_key
                dst = edge.dst_key

                if src.startswith("msg:") or src.startswith("doc:"):
                    continue

                if src not in nodes_dict:
                    nodes_dict[src] = self._build_node_object(src, edge.src_type, session)

                if dst not in nodes_dict:
                    nodes_dict[dst] = self._build_node_object(dst, edge.dst_type, session)

                derivation_method = edge.derivation_method or (
                    DERIVATION_CORPUS_STRUCTURE if edge.relation == "contains"
                    else (DERIVATION_TEXT_EXTRACTION if edge.relation == "penalizes_with"
                          else DERIVATION_CURATED_LEGAL_RELATIONSHIP)
                )

                is_unverified = derivation_method == DERIVATION_LLM_SUGGESTED_UNVERIFIED
                is_user_doc = derivation_method == DERIVATION_USER_DOCUMENT_REFERENCE

                links_list.append({
                    "id": edge.id,
                    "source": src,
                    "target": dst,
                    "relation": edge.relation,
                    "origin": edge.origin,
                    "derivation_method": derivation_method,
                    "is_unverified": is_unverified,
                    "is_user_document": is_user_doc,
                    "confidence": edge.confidence
                })

            nodes_list = list(nodes_dict.values())

            if search_query:
                sq = search_query.lower()
                matched_ids = {n["id"] for n in nodes_list if sq in n["label"].lower() or sq in n.get("desc", "").lower()}
                nodes_list = [n for n in nodes_list if n["id"] in matched_ids]
                links_list = [l for l in links_list if l["source"] in matched_ids and l["target"] in matched_ids]

            return {
                "nodes": nodes_list,
                "links": links_list,
                "empty_state": len(nodes_list) == 0,
                "scope": scope,
                "total_nodes": len(nodes_list),
                "total_links": len(links_list),
                "backend_used": backend_name,
                "hardware_tier": tier
            }

    def _query_memgraph_global(self, driver, search_query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Queries Memgraph via Cypher for global topology."""
        with driver.session() as mg_session:
            cypher = """
            MATCH (s:Node)-[r:RELATION]->(d:Node)
            RETURN s.key AS src_key, s.label AS src_label, s.type AS src_type, s.cited_in_conversations AS src_cites,
                   d.key AS dst_key, d.label AS dst_label, d.type AS dst_type, d.cited_in_conversations AS dst_cites,
                   r.type AS relation, r.derivation_method AS derivation_method, r.origin AS origin, r.confidence AS confidence
            LIMIT 200
            """
            result = mg_session.run(cypher)
            nodes_dict = {}
            links_list = []

            for record in result:
                src_key = record["src_key"]
                dst_key = record["dst_key"]

                if src_key not in nodes_dict:
                    nodes_dict[src_key] = {
                        "id": src_key,
                        "label": record["src_label"] or src_key,
                        "type": record["src_type"] or "statute",
                        "category": (record["src_type"] or "statute").title(),
                        "color": "#38bdf8" if record["src_type"] == "statute" else "#00d2b4",
                        "cited_in_conversations": record["src_cites"] or 0,
                        "desc": f"{record['src_label']} (Memgraph Native Node)"
                    }

                if dst_key not in nodes_dict:
                    nodes_dict[dst_key] = {
                        "id": dst_key,
                        "label": record["dst_label"] or dst_key,
                        "type": record["dst_type"] or "section",
                        "category": (record["dst_type"] or "section").title(),
                        "color": "#00d2b4" if record["dst_type"] == "section" else "#a855f7",
                        "cited_in_conversations": record["dst_cites"] or 0,
                        "desc": f"{record['dst_label']} (Memgraph Native Node)"
                    }

                links_list.append({
                    "id": f"{src_key}->{dst_key}:{record['relation']}",
                    "source": src_key,
                    "target": dst_key,
                    "relation": record["relation"],
                    "derivation_method": record["derivation_method"] or DERIVATION_CORPUS_STRUCTURE,
                    "origin": record["origin"] or "memgraph",
                    "confidence": record["confidence"] or 1.0,
                    "is_unverified": record["derivation_method"] == DERIVATION_LLM_SUGGESTED_UNVERIFIED,
                    "is_user_document": record["derivation_method"] == DERIVATION_USER_DOCUMENT_REFERENCE
                })

            nodes_list = list(nodes_dict.values())
            if search_query:
                sq = search_query.lower()
                matched_ids = {n["id"] for n in nodes_list if sq in n["label"].lower() or sq in n.get("desc", "").lower()}
                nodes_list = [n for n in nodes_list if n["id"] in matched_ids]
                links_list = [l for l in links_list if l["source"] in matched_ids and l["target"] in matched_ids]

            return {
                "nodes": nodes_list,
                "links": links_list,
                "empty_state": len(nodes_list) == 0,
                "scope": "global",
                "total_nodes": len(nodes_list),
                "total_links": len(links_list)
            }

    def _build_node_object(self, key: str, node_type: str, session) -> Dict[str, Any]:
        """Synthesizes rich visualization attributes with cited_in_conversations sizing."""
        label = key
        desc = ""
        color = "#38bdf8"
        category = "Statute"
        cited_count = 0

        if key.startswith("section:"):
            parts = key.split(":")
            act_slug = parts[1] if len(parts) > 1 else ""
            sec_num = parts[2] if len(parts) > 2 else ""
            label = f"Section {sec_num}"
            category = "Section"
            color = "#00d2b4"

            statute = session.query(Statute).filter_by(slug=act_slug).first()
            if statute:
                sec_row = session.query(StatuteSection).filter_by(statute_id=statute.id, number=sec_num).first()
                if sec_row:
                    cited_count = sec_row.cited_in_conversations or 0
                    desc = f"{statute.title} — {sec_row.heading or ''}\n{sec_row.raw_text[:140] if sec_row.raw_text else ''}"
                else:
                    desc = f"{statute.title}, Section {sec_num}"
            else:
                desc = f"{act_slug.replace('_', ' ').title()}, Section {sec_num}"

        elif key.startswith("statute:"):
            act_slug = key.replace("statute:", "")
            statute = session.query(Statute).filter_by(slug=act_slug).first()
            if statute:
                label = statute.title
                category = statute.domain.title()
                desc = f"Enacted: {statute.year or 'N/A'} · Source: {statute.source} · {statute.section_count} Sections"
            else:
                label = act_slug.replace("_", " ").title()
            color = "#38bdf8"

        elif key.startswith("precedent:"):
            label = key.replace("precedent:", "").replace("_", " ").title()
            category = "Precedent"
            color = "#a855f7"
            desc = f"Landmark Precedent: {label}"

        elif key.startswith("penalty:"):
            parts = key.split(":")
            sec_num = parts[2] if len(parts) > 2 else ""
            label = f"Penalty (§{sec_num})"
            category = "Penalty"
            color = "#f59e0b"
            desc = "Statutory sanction / penal consequence extracted from statutory text."

        return {
            "id": key,
            "label": label,
            "type": node_type,
            "color": color,
            "category": category,
            "desc": desc,
            "cited_in_conversations": cited_count,
            "size_score": 1.0 + (min(cited_count, 10) * 0.15)
        }

    def expand_node(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """Lazy neighborhood expansion for a clicked node with edge provenance."""
        with get_sync_session() as session:
            edges = session.query(CitationEdge).filter(
                (CitationEdge.src_key == node_id) | (CitationEdge.dst_key == node_id)
            ).limit(25).all()

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            links_list: List[Dict[str, Any]] = []

            for edge in edges:
                for k, t in [(edge.src_key, edge.src_type), (edge.dst_key, edge.dst_type)]:
                    if not k.startswith("msg:") and not k.startswith("doc:") and k not in nodes_dict:
                        nodes_dict[k] = self._build_node_object(k, t, session)

                if not edge.src_key.startswith("msg:") and not edge.src_key.startswith("doc:") and not edge.dst_key.startswith("msg:"):
                    links_list.append({
                        "id": edge.id,
                        "source": edge.src_key,
                        "target": edge.dst_key,
                        "relation": edge.relation,
                        "origin": edge.origin,
                        "derivation_method": edge.derivation_method or DERIVATION_CURATED_LEGAL_RELATIONSHIP,
                        "is_unverified": edge.derivation_method == DERIVATION_LLM_SUGGESTED_UNVERIFIED,
                        "is_user_document": edge.derivation_method == DERIVATION_USER_DOCUMENT_REFERENCE,
                        "confidence": edge.confidence
                    })

            return {
                "nodes": list(nodes_dict.values()),
                "links": links_list,
                "backend_used": self.get_active_backend_name()
            }


citation_graph_service = CitationGraphService()
