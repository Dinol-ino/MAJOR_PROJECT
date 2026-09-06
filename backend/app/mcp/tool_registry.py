import logging
from typing import Dict, Any, List, Optional, Type, Callable
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Tool Input / Output Schemas
# ---------------------------------------------------------

class LocalStatuteSearchInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Legal query or statutory concept.")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of results to retrieve.")

class LocalStatuteSearchOutput(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)
    total_found: int = 0


class LocalProvisionLookupInput(BaseModel):
    act: str = Field(..., min_length=2, max_length=100, description="Act name e.g. Indian Penal Code")
    section: str = Field(..., min_length=1, max_length=50, description="Section e.g. Section 302")

class LocalProvisionLookupOutput(BaseModel):
    found: bool = False
    act: str
    section: str
    text: Optional[str] = None


class UserDocumentSearchInput(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    query: str = Field(..., min_length=2, max_length=500)
    top_k: Optional[int] = Field(default=3, ge=1, le=10)

class UserDocumentSearchOutput(BaseModel):
    session_id: str
    results: List[Dict[str, Any]] = Field(default_factory=list)


class LegalCorpusQueryInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    domain: Optional[str] = Field(default="criminal_law", description="Legal domain filter")

class LegalCorpusQueryOutput(BaseModel):
    citations: List[Dict[str, str]] = Field(default_factory=list)
    summary: str = ""


class LiveStatuteCheckerInput(BaseModel):
    act_name: str = Field(..., min_length=2, max_length=150)
    section: Optional[str] = None

class LiveStatuteCheckerOutput(BaseModel):
    act_name: str
    status: str = "In Force"
    latest_amendment_year: Optional[int] = 2023
    details: str = ""


class KanoonCaseSearchInput(BaseModel):
    citation: Optional[str] = None
    keywords: str = Field(..., min_length=3, max_length=300)
    max_cases: Optional[int] = Field(default=3, ge=1, le=5)

class KanoonCaseSearchOutput(BaseModel):
    cases: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "Indian Kanoon Allowlisted Mirror"


class IndiaCodeFetcherInput(BaseModel):
    act_id: str = Field(..., min_length=2, max_length=50)

class IndiaCodeFetcherOutput(BaseModel):
    act_id: str
    official_title: str
    gazette_ref: str
    enactment_date: str


class GenericMCPInput(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)

class GenericMCPOutput(BaseModel):
    data: Any = None
    status: str = "success"


# ---------------------------------------------------------
# Tool Definition & Registry
# ---------------------------------------------------------

class ToolDefinition:
    """Encapsulates a typed tool definition within the MCP Subsystem."""
    def __init__(
        self,
        name: str,
        category: str,
        description: str,
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        handler: Optional[Callable[..., Any]] = None,
        server_name: Optional[str] = None
    ):
        self.name = name
        self.category = category
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.handler = handler
        self.server_name = server_name

    def validate_input(self, payload: Dict[str, Any]) -> BaseModel:
        return self.input_schema(**payload)

    def validate_output(self, payload: Dict[str, Any]) -> BaseModel:
        return self.output_schema(**payload)


class ToolRegistry:
    """Central typed registry of all allowed MCP and internal tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        logger.debug(f"Registered MCP tool '{tool.name}' in category '{tool.category}'.")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        result = []
        for name, tool in self._tools.items():
            if category is None or tool.category == category:
                result.append({
                    "name": tool.name,
                    "category": tool.category,
                    "description": tool.description,
                    "server_name": tool.server_name,
                    "input_schema": tool.input_schema.model_json_schema(),
                    "output_schema": tool.output_schema.model_json_schema(),
                })
        return result

    def _register_default_tools(self) -> None:
        # LOCAL_RETRIEVAL
        self.register_tool(ToolDefinition(
            name="local_statute_search",
            category="LOCAL_RETRIEVAL",
            description="Searches local statutory corpus (IPC, CrPC, Evidence Act) via hybrid RAG.",
            input_schema=LocalStatuteSearchInput,
            output_schema=LocalStatuteSearchOutput,
            handler=self._mock_local_statute_search
        ))
        self.register_tool(ToolDefinition(
            name="local_provision_lookup",
            category="LOCAL_RETRIEVAL",
            description="Direct structural lookup for an exact Act and Section.",
            input_schema=LocalProvisionLookupInput,
            output_schema=LocalProvisionLookupOutput,
            handler=self._mock_provision_lookup
        ))

        # DOCUMENT_SEARCH
        self.register_tool(ToolDefinition(
            name="user_document_search",
            category="DOCUMENT_SEARCH",
            description="Searches user-uploaded PDF/text documents for the active session.",
            input_schema=UserDocumentSearchInput,
            output_schema=UserDocumentSearchOutput,
            handler=self._mock_user_doc_search
        ))

        # LEGAL_SEARCH
        self.register_tool(ToolDefinition(
            name="legal_corpus_query",
            category="LEGAL_SEARCH",
            description="Read-only query across validated legal statutes.",
            input_schema=LegalCorpusQueryInput,
            output_schema=LegalCorpusQueryOutput,
            handler=self._mock_legal_corpus_query
        ))

        # CURRENT_LAW (Requires ONLINE)
        self.register_tool(ToolDefinition(
            name="live_statute_checker",
            category="CURRENT_LAW",
            description="Live lookup of amendments and in-force status.",
            input_schema=LiveStatuteCheckerInput,
            output_schema=LiveStatuteCheckerOutput,
            handler=self._mock_live_statute_checker
        ))

        # CASE_LAW_SEARCH (Requires ONLINE)
        self.register_tool(ToolDefinition(
            name="kanoon_case_search",
            category="CASE_LAW_SEARCH",
            description="Searches Indian Kanoon / Supreme Court judgment mirrors.",
            input_schema=KanoonCaseSearchInput,
            output_schema=KanoonCaseSearchOutput,
            handler=self._mock_kanoon_search
        ))

        # GOVERNMENT_SOURCE (Requires ONLINE)
        self.register_tool(ToolDefinition(
            name="indiacode_fetcher",
            category="GOVERNMENT_SOURCE",
            description="Fetches official gazette publication details from IndiaCode portal.",
            input_schema=IndiaCodeFetcherInput,
            output_schema=IndiaCodeFetcherOutput,
            handler=self._mock_indiacode_fetcher
        ))


    # --- Built-in Safe Handlers ---
    def _mock_local_statute_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        from app.retrieval.tier1_law import Tier1LawRetrieval
        from app.config import settings
        t1 = Tier1LawRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
        results = t1.query(text=query, top_k=top_k)
        return {"results": results, "total_found": len(results)}

    def _mock_provision_lookup(self, act: str, section: str) -> Dict[str, Any]:
        from app.retrieval.fusion_router import fusion_router
        res = fusion_router.execute_pageindex_lookup(act, section)
        if res:
            first = res[0]
            return {"found": True, "act": first.get("act", act), "section": first.get("section", section), "text": first.get("text")}
        return {"found": False, "act": act, "section": section, "text": None}

    def _mock_user_doc_search(self, session_id: str, query: str, top_k: int = 3) -> Dict[str, Any]:
        from app.retrieval.tier2_user import Tier2UserRetrieval
        from app.config import settings
        t2 = Tier2UserRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
        results = t2.query(session_id=session_id, text=query, top_k=top_k)
        return {"session_id": session_id, "results": results}

    def _mock_legal_corpus_query(self, query: str, domain: str = "criminal_law") -> Dict[str, Any]:
        return {
            "citations": [{"act": "Indian Penal Code", "section": "Section 300"}],
            "summary": f"Retrieved provisions related to '{query}' in {domain}."
        }

    def _mock_live_statute_checker(self, act_name: str, section: Optional[str] = None) -> Dict[str, Any]:
        return {
            "act_name": act_name,
            "status": "In Force",
            "latest_amendment_year": 2023,
            "details": f"Verified live gazette status for {act_name}."
        }

    def _mock_kanoon_search(self, keywords: str, citation: Optional[str] = None, max_cases: int = 3) -> Dict[str, Any]:
        return {
            "cases": [
                {"title": "State of Maharashtra v. Mayer Hans George", "citation": "1965 AIR 722", "relevance": "High"}
            ],
            "source": "Indian Kanoon Allowlisted Mirror"
        }

    def _mock_indiacode_fetcher(self, act_id: str) -> Dict[str, Any]:
        return {
            "act_id": act_id,
            "official_title": f"Government Act Registry Ref #{act_id}",
            "gazette_ref": "Ext. No. 45/1860",
            "enactment_date": "1860-10-06"
        }


tool_registry = ToolRegistry()
