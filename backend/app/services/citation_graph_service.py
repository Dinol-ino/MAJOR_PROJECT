import uuid
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

from app.db.engine import get_sync_session
from app.db.models import CitationEdge, Statute, StatuteSection

logger = logging.getLogger(__name__)


class CitationGraphService:
    """
    Spec 04 §4: Real dynamic legal citation graph engine.
    Constructs graph strictly from DB-backed citation edges, LLM output citations,
    and MCP cross-statute relationship mappings. Never returns hardcoded fake nodes.
    """

    def record_citations(
        self,
        conversation_id: str,
        message_id: str,
        citations: List[Dict[str, Any]]
    ) -> int:
        """
        Extracts citation tokens from assistant message and persists
        structured graph relationship edges to the citation_edges table.
        """
        if not citations:
            return 0

        edges_added = 0
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

                # Edge 1: Section -> Statute (Contains)
                session.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    src_type="statute",
                    src_key=statute_key,
                    dst_type="section",
                    dst_key=sec_key,
                    relation="contains",
                    origin="llm_citation",
                    conversation_id=conversation_id,
                    message_id=message_id,
                    confidence=1.0,
                    created_at=datetime.utcnow()
                ))
                edges_added += 1

                # Edge 2: Message -> Section (Cites)
                session.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    src_type=f"msg:{message_id}",
                    src_key=f"msg:{message_id}",
                    dst_type="section",
                    dst_key=sec_key,
                    relation="cites",
                    origin="llm_citation",
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
                            origin="llm_citation",
                            conversation_id=conversation_id,
                            message_id=message_id,
                            confidence=0.9,
                            created_at=datetime.utcnow()
                        ))
                        edges_added += 1

            session.commit()

        logger.debug(f"Recorded {edges_added} citation graph edges for session={conversation_id}")
        return edges_added

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
        - 'global': all verified statutory cross-references and MCP relations.
        """
        with get_sync_session() as session:
            query = session.query(CitationEdge)

            if scope == "conversation":
                if not conversation_id:
                    return {"nodes": [], "links": [], "empty_state": True, "scope": scope}
                query = query.filter_by(conversation_id=conversation_id)
            elif scope == "vault" and vault_id:
                # Query conversations belonging to this vault
                from app.db.models import Conversation
                conv_ids = [c.conversation_id for c in session.query(Conversation).filter_by(project_vault_id=vault_id).all()]
                if conv_ids:
                    query = query.filter(CitationEdge.conversation_id.in_(conv_ids))
                else:
                    return {"nodes": [], "links": [], "empty_state": True, "scope": scope}
            elif scope == "global":
                # Return mcp_relation + cross-statute edges
                query = query.filter(CitationEdge.origin.in_(["mcp_relation", "llm_citation"]))

            edges = query.order_by(CitationEdge.created_at.desc()).limit(150).all()

            if not edges:
                return {"nodes": [], "links": [], "empty_state": True, "scope": scope}

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            links_list: List[Dict[str, Any]] = []

            for edge in edges:
                src = edge.src_key
                dst = edge.dst_key

                # Skip internal message keys for cleaner graph visualization
                if src.startswith("msg:"):
                    continue

                # Parse or enhance source node
                if src not in nodes_dict:
                    nodes_dict[src] = self._build_node_object(src, edge.src_type, session)

                # Parse or enhance target node
                if dst not in nodes_dict:
                    nodes_dict[dst] = self._build_node_object(dst, edge.dst_type, session)

                links_list.append({
                    "id": edge.id,
                    "source": src,
                    "target": dst,
                    "relation": edge.relation,
                    "origin": edge.origin,
                    "confidence": edge.confidence
                })

            nodes_list = list(nodes_dict.values())

            # Filter if search_query present
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
                "total_links": len(links_list)
            }

    def _build_node_object(self, key: str, node_type: str, session) -> Dict[str, Any]:
        """Synthesizes rich visualization attributes for a node."""
        label = key
        desc = ""
        color = "#38bdf8"
        category = "Statute"

        if key.startswith("section:"):
            parts = key.split(":")
            act_slug = parts[1] if len(parts) > 1 else ""
            sec_num = parts[2] if len(parts) > 2 else ""
            label = f"Section {sec_num}"
            category = "Section"
            color = "#00d2b4"

            # Check DB for heading
            statute = session.query(Statute).filter_by(slug=act_slug).first()
            if statute:
                sec_row = session.query(StatuteSection).filter_by(statute_id=statute.id, number=sec_num).first()
                if sec_row:
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
                desc = f"Enacted: {statute.year or 'N/A'} · Source: {statute.source}"
            else:
                label = act_slug.replace("_", " ").title()
            color = "#38bdf8"

        elif key.startswith("precedent:"):
            label = key.replace("precedent:", "").replace("_", " ").title()
            category = "Precedent"
            color = "#a855f7"

        return {
            "id": key,
            "label": label,
            "type": node_type,
            "color": color,
            "category": category,
            "desc": desc
        }

    def expand_node(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """Lazy neighborhood expansion for a clicked node."""
        with get_sync_session() as session:
            edges = session.query(CitationEdge).filter(
                (CitationEdge.src_key == node_id) | (CitationEdge.dst_key == node_id)
            ).limit(20).all()

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            links_list: List[Dict[str, Any]] = []

            for edge in edges:
                for k, t in [(edge.src_key, edge.src_type), (edge.dst_key, edge.dst_type)]:
                    if not k.startswith("msg:") and k not in nodes_dict:
                        nodes_dict[k] = self._build_node_object(k, t, session)

                if not edge.src_key.startswith("msg:") and not edge.dst_key.startswith("msg:"):
                    links_list.append({
                        "id": edge.id,
                        "source": edge.src_key,
                        "target": edge.dst_key,
                        "relation": edge.relation,
                        "origin": edge.origin
                    })

            return {
                "nodes": list(nodes_dict.values()),
                "links": links_list
            }


citation_graph_service = CitationGraphService()
