import re
import time
import uuid
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

from app.config import settings
from app.orchestrator.limits import (
    ExecutionBudget,
    LimitExceeded,
    StepLimitExceeded,
    ToolCallLimitExceeded,
    TokenLimitExceeded,
    TimeLimitExceeded,
    DocLimitExceeded,
    NetworkLimitExceeded,
    RetryBudgetExceeded,
)
from app.orchestrator.circuit_breaker import circuit_breaker
from app.orchestrator.cancellation import cancellation_manager

# Integrated Defense & Retrieval Components
from app.defense.layer1_input_guard import Layer1InputGuard
from app.defense.layer2_trusted_context import Layer2TrustedContext
from app.defense.layer3_output_guard import Layer3OutputGuard
from app.defense.audit_log import AuditLogger
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.mcp.gateway import mcp_gateway, MCPResponse
from app.runtime.runtime_manager import RuntimeManager
from app.runtime.token_budget_manager import TokenBudgetManager
from app.runtime.citation_builder import CitationBuilder
from app.runtime.response_formatter import ResponseFormatter
from app.memory.durable_memory import DurableMemoryManager

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    INITIALIZED = "INITIALIZED"
    CLASSIFY = "CLASSIFY"
    SECURITY_CHECK = "SECURITY_CHECK"
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    TOOL_CALL = "TOOL_CALL"
    EVIDENCE_VALIDATION = "EVIDENCE_VALIDATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SYNTHESIS = "SYNTHESIS"
    LEGAL_VERIFICATION = "LEGAL_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Explicit, code-controlled finite state transition graph
ALLOWED_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.INITIALIZED: {AgentState.CLASSIFY, AgentState.SECURITY_CHECK, AgentState.RETRIEVE, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.CLASSIFY: {AgentState.SECURITY_CHECK, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.SECURITY_CHECK: {AgentState.PLAN, AgentState.RETRIEVE, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.PLAN: {AgentState.RETRIEVE, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.RETRIEVE: {AgentState.TOOL_CALL, AgentState.EVIDENCE_VALIDATION, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.TOOL_CALL: {AgentState.EVIDENCE_VALIDATION, AgentState.RETRIEVE, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.EVIDENCE_VALIDATION: {AgentState.TOOL_CALL, AgentState.SYNTHESIS, AgentState.INSUFFICIENT_EVIDENCE, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.INSUFFICIENT_EVIDENCE: set(),
    AgentState.SYNTHESIS: {AgentState.LEGAL_VERIFICATION, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.LEGAL_VERIFICATION: {AgentState.COMPLETED, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.COMPLETED: set(),
    AgentState.FAILED: set(),
    AgentState.CANCELLED: set(),
}


class StateStepTrace(BaseModel):
    step_number: int
    state: str
    duration_ms: float
    outcome: str  # "success" | "failure" | "blocked" | "skipped" | "tripped"
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class OrchestrationResult(BaseModel):
    request_id: str
    session_id: str
    final_state: AgentState
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_by: Optional[str] = None
    block_reason: Optional[str] = None
    failure_kind: Optional[str] = None
    correlation_id: Optional[str] = None
    reasoning_trace: Optional[str] = None
    steps_trace: List[StateStepTrace] = Field(default_factory=list)
    budget_snapshot: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    model_used: Optional[str] = None
    runtime_used: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    # Citation-contract outcome. grounding_score is None only when no answer was produced
    # (blocked / model unavailable); it is never None merely because parsing found nothing.
    grounding_score: Optional[float] = None
    citations_parsed: Optional[List[Dict[str, Any]]] = None
    citation_contract_violated: bool = False


class ResearchStateMachine:
    """
    Bounded Agentic Research Orchestrator (Phase 09).
    Wraps research workflows into a deterministic, code-controlled state machine with hard ceilings,
    per-step circuit breakers, user/timeout cancellation, and L6 cryptographic audit logging.
    """

    def __init__(self):
        self.input_guard = Layer1InputGuard()
        self.trusted_context = Layer2TrustedContext()
        self.output_guard = Layer3OutputGuard()
        self.audit_logger = AuditLogger()
        self.durable_memory = DurableMemoryManager()
        self.tier1_retriever = Tier1LawRetrieval(settings.CHROMA_PERSIST_DIR)
        self.tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)
        self.token_budget_manager = TokenBudgetManager()
        self.citation_builder = CitationBuilder()
        self.response_formatter = ResponseFormatter()

    async def execute(
        self,
        query: str,
        session_id: str,
        user_id: str = "default_user",
        model: Optional[str] = None,
        shield_on: bool = True,
        vault_id: Optional[str] = None,
        reasoning_effort: Optional[str] = "off",
        request_id: Optional[str] = None,
        custom_budget: Optional[ExecutionBudget] = None,
    ) -> OrchestrationResult:
        """
        Executes a bounded research request through the formal state machine.
        Supports matter-scoped Project Vault retrieval and Deep Thinking CoT reasoning.
        """
        start_time = time.time()
        req_id = request_id or str(uuid.uuid4())
        profile = settings.reasoning.for_effort(reasoning_effort)
        cfg = settings.orchestrator
        # Reasoning level sets real budgets, always capped by the orchestrator hard ceilings.
        budget = custom_budget or ExecutionBudget(
            max_tool_calls=min(int(profile["max_tool_calls"]), cfg.max_tool_calls),
            retry_budget=min(int(profile["retry_budget"]), cfg.retry_budget),
            max_retrieved_docs=min(int(profile["max_evidence_chunks"]) * 3, cfg.max_retrieved_docs),
        )
        cancellation_manager.register(req_id)

        # Context accumulator across states
        ctx: Dict[str, Any] = {
            "query": query,
            "session_id": session_id,
            "user_id": user_id,
            "model": model or settings.DEFAULT_MODEL,
            "shield_on": shield_on,
            "vault_id": vault_id,
            "reasoning_effort": profile["level"],
            "profile": profile,
            "metrics": {"reasoning_level": profile["level"]},
            "reasoning_trace": None,
            "request_id": req_id,
            "intent": "general_legal",
            "security_passed": False,
            "injection_score": 0.0,
            "retrieved_chunks": [],
            "tool_results": [],
            "validated_evidence": [],
            "prompt": "",
            "raw_answer": "",
            "clean_answer": "",
            "sources": [],
            "blocked_by": None,
            "block_reason": None,
        }

        current_state = AgentState.INITIALIZED
        traces: List[StateStepTrace] = []

        if cancellation_manager.is_cancelled(req_id):
            current_state = AgentState.CANCELLED
            ctx["blocked_by"] = "cancellation"
            ctx["block_reason"] = cancellation_manager.get_cancellation_reason(req_id) or "User cancelled"
            ctx["clean_answer"] = f"Research session cancelled: {ctx['block_reason']}"
            return self._build_result(ctx, current_state, traces, budget, start_time)

        try:
            # Fast-Path for Simple Statutory Lookups (Fault 01 §10-State FSM)
            # Trivial queries like "Section 302 IPC" bypass planning, tools, and multi-pass verification.
            if profile["level"] == "low" and self._is_simple_statutory_lookup(query):
                current_state = self._transition(current_state, AgentState.SECURITY_CHECK, req_id)
                sec_trace = await self._run_security_check(ctx, budget)
                traces.append(sec_trace)
                if not ctx.get("security_passed", False):
                    current_state = self._transition(current_state, AgentState.FAILED, req_id)
                    return self._build_result(ctx, current_state, traces, budget, start_time)

                current_state = self._transition(current_state, AgentState.RETRIEVE, req_id)
                retrieve_trace = await self._run_retrieve(ctx, budget)
                traces.append(retrieve_trace)

                current_state = self._transition(current_state, AgentState.EVIDENCE_VALIDATION, req_id)
                val_trace = await self._run_evidence_validation(ctx, budget)
                traces.append(val_trace)

                if ctx.get("insufficient_evidence", False):
                    current_state = self._transition(current_state, AgentState.INSUFFICIENT_EVIDENCE, req_id)
                    ctx["clean_answer"] = self._format_insufficient_evidence_refusal(ctx)
                    return self._build_result(ctx, current_state, traces, budget, start_time)

                current_state = self._transition(current_state, AgentState.SYNTHESIS, req_id)
                synth_trace = await self._run_synthesis(ctx, budget)
                traces.append(synth_trace)

                # Layer 3 runs on the fast path too.
                #
                # This previously went straight to COMPLETED, which skipped the output
                # guard, citation parsing, grounding and hallucination detection - and the
                # response still reported blocked_by=null and failure_kind=null, so a
                # fast answer was indistinguishable from a verified one. Selecting the
                # "low" reasoning level therefore disabled the Layer 3 boundary silently.
                #
                # The fast path legitimately skips planning, tool calls and the retry
                # loop. It must not skip the output guard: every answer leaving this
                # system is checked against the evidence it claims to rest on.
                current_state = self._transition(current_state, AgentState.LEGAL_VERIFICATION, req_id)
                verify_trace = await self._run_legal_verification(ctx, budget)
                traces.append(verify_trace)

                current_state = self._transition(
                    current_state,
                    AgentState.COMPLETED if ctx.get("verification_passed", False) else AgentState.FAILED,
                    req_id,
                )
                return self._build_result(ctx, current_state, traces, budget, start_time)

            # 1. State: INITIALIZED -> CLASSIFY
            current_state = self._transition(current_state, AgentState.CLASSIFY, req_id)
            step_trace = await self._run_classify(ctx, budget)
            traces.append(step_trace)

            if ctx.get("is_out_of_scope", False):
                current_state = self._transition(current_state, AgentState.COMPLETED, req_id)
                return self._build_result(ctx, current_state, traces, budget, start_time)

            # 2. State: CLASSIFY -> SECURITY_CHECK
            current_state = self._transition(current_state, AgentState.SECURITY_CHECK, req_id)
            step_trace = await self._run_security_check(ctx, budget)
            traces.append(step_trace)
            if not ctx.get("security_passed", False):
                current_state = self._transition(current_state, AgentState.FAILED, req_id)
                return self._build_result(ctx, current_state, traces, budget, start_time)

            # 3. State: SECURITY_CHECK -> PLAN
            current_state = self._transition(current_state, AgentState.PLAN, req_id)
            step_trace = await self._run_plan(ctx, budget)
            traces.append(step_trace)

            # 4. State: PLAN -> RETRIEVE
            current_state = self._transition(current_state, AgentState.RETRIEVE, req_id)
            step_trace = await self._run_retrieve(ctx, budget)
            traces.append(step_trace)

            # 5. State: RETRIEVE -> OPTIONAL TOOL_CALL (if tools required & budget permits & circuit breaker closed)
            if ctx.get("requires_tool_call", False) and budget.tool_calls_made < budget.max_tool_calls:
                current_state = self._transition(current_state, AgentState.TOOL_CALL, req_id)
                step_trace = await self._run_tool_call(ctx, budget)
                traces.append(step_trace)

            # 6. State: TOOL_CALL / RETRIEVE -> EVIDENCE_VALIDATION
            current_state = self._transition(current_state, AgentState.EVIDENCE_VALIDATION, req_id)
            step_trace = await self._run_evidence_validation(ctx, budget)
            traces.append(step_trace)

            if ctx.get("insufficient_evidence", False):
                current_state = self._transition(current_state, AgentState.INSUFFICIENT_EVIDENCE, req_id)
                ctx["clean_answer"] = self._format_insufficient_evidence_refusal(ctx)
                return self._build_result(ctx, current_state, traces, budget, start_time)

            # 7. State: EVIDENCE_VALIDATION -> SYNTHESIS
            current_state = self._transition(current_state, AgentState.SYNTHESIS, req_id)
            step_trace = await self._run_synthesis(ctx, budget)
            traces.append(step_trace)

            # 8. State: SYNTHESIS -> LEGAL_VERIFICATION (Layer 3 Guardrails)
            current_state = self._transition(current_state, AgentState.LEGAL_VERIFICATION, req_id)
            step_trace = await self._run_legal_verification(ctx, budget)
            traces.append(step_trace)

            # Check verification outcome
            if ctx.get("verification_passed", False):
                current_state = self._transition(current_state, AgentState.COMPLETED, req_id)
            else:
                # If failed and retry budget exists, attempt synthesis once more
                if budget.retries_attempted < budget.retry_budget and ctx.get("failure_kind") != "model_unavailable":
                    budget.record_retry()
                    current_state = self._transition(current_state, AgentState.SYNTHESIS, req_id)
                    retry_trace = await self._run_synthesis(ctx, budget, retry_note=ctx.get("block_reason"))
                    traces.append(retry_trace)
                    
                    current_state = self._transition(current_state, AgentState.LEGAL_VERIFICATION, req_id)
                    reverify_trace = await self._run_legal_verification(ctx, budget)
                    traces.append(reverify_trace)

                    if ctx.get("verification_passed", False):
                        current_state = self._transition(current_state, AgentState.COMPLETED, req_id)
                    else:
                        current_state = self._transition(current_state, AgentState.FAILED, req_id)
                else:
                    current_state = self._transition(current_state, AgentState.FAILED, req_id)

        except LimitExceeded as exc:
            logger.warning(f"Orchestration ceiling breached for request '{req_id}': {exc.message}")
            current_state = AgentState.FAILED
            ctx["blocked_by"] = "orchestrator_limit"
            ctx["block_reason"] = exc.message
            ctx["clean_answer"] = f"Request terminated: {exc.message}"
            traces.append(StateStepTrace(
                step_number=budget.steps_taken,
                state="LIMIT_EXCEEDED",
                duration_ms=0.0,
                outcome="blocked",
                details={"limit_type": exc.limit_type, "message": exc.message}
            ))

        except Exception as unhandled_exc:
            logger.error(f"Unhandled error in state machine for request '{req_id}': {unhandled_exc}", exc_info=True)
            current_state = AgentState.FAILED
            ctx["blocked_by"] = "runtime_error"
            ctx["block_reason"] = str(unhandled_exc)
            ctx["clean_answer"] = f"An internal error occurred during research execution: {unhandled_exc}"

        finally:
            # Check if cancelled mid-flight
            if cancellation_manager.is_cancelled(req_id):
                current_state = AgentState.CANCELLED
                ctx["blocked_by"] = "cancellation"
                ctx["block_reason"] = cancellation_manager.get_cancellation_reason(req_id) or "User cancelled"
                ctx["clean_answer"] = f"Research session cancelled: {ctx['block_reason']}"

            cancellation_manager.unregister(req_id)

        return self._build_result(ctx, current_state, traces, budget, start_time)

    def _transition(self, current: AgentState, target: AgentState, request_id: str) -> AgentState:
        """Validates and applies a state transition against the defined transition graph."""
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError(f"Illegal state transition attempted from '{current.value}' to '{target.value}' in request '{request_id}'")
        logger.debug(f"StateMachine [{request_id[:8]}]: {current.value} -> {target.value}")
        return target

    def _session_has_uploads(self, session_id: Optional[str]) -> bool:
        """Returns True if the session has user-uploaded documents in the tier2 index."""
        if not session_id:
            return False
        try:
            count = self.tier2_retriever.collection.count()
            if count == 0:
                return False
            results = self.tier2_retriever.collection.get(
                where={"session_id": session_id},
                limit=1,
            )
            return bool(results and results.get("ids"))
        except Exception:
            return False

    def _is_simple_statutory_lookup(self, query: str) -> bool:
        """
        Fast-path heuristic for simple statutory lookups (Fault 01 §10-State FSM).
        Matches queries targeting a specific section of a codified act without deep analytical complexity.
        """
        import re
        q = query.strip().lower()
        has_section = bool(re.search(r"\b(?:section|sec\.?|s\.)\s*\d+[a-z]?\b", q))
        has_act = any(act in q for act in ["ipc", "crpc", "bns", "bnss", "bsa", "evidence act", "companies act", "constitution", "it act", "contract act", "act", "code"])
        is_complex = any(k in q for k in ["compare", "synthesize", "deep research", "cross examine", "multihop", "draft legal notice"])
        return has_section and has_act and not is_complex

    # --- Step Implementations ---

    async def _run_classify(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        q = ctx["query"].lower().strip()

        # Doc 04 §4.1: Legal-only scope enforcement (FSM CLASSIFY state)
        legal_keywords = [
            "section", "sec.", "act", "code", "sanhita", "adhiniyam", "ipc", "crpc", "cpc",
            "bns", "bnss", "bsa", "dpdpa", "constitution", "preamble", "article", "statute",
            "court", "tribunal", "judge", "advocate", "lawyer", "bench", "judgment", "ruling",
            "appeal", "petition", "writ", "plaint", "suit", "affidavit", "fir", "police",
            "magistrate", "bail", "anticipatory", "custody", "remand", "arrest", "summons",
            "warrant", "cognizable", "bailable", "charge sheet", "trial", "acquittal", "conviction",
            "law", "legal", "statutory", "jurisdiction", "crime", "criminal", "civil", "penalty",
            "punishment", "imprisonment", "fine", "offence", "offense", "fraud", "cheating",
            "theft", "murder", "defamation", "extortion", "contract", "agreement", "breach",
            "indemnity", "arbitration", "damages", "injunction", "property", "deed", "tenant",
            "lease", "landlord", "corporate", "company", "director", "shares", "tax", "gst",
            "customs", "excise", "trademark", "patent", "copyright", "ipr", "consumer",
            "deficiency", "labour", "employment", "gratuity", "provident fund", "cyber",
            "hacking", "privacy", "data protection", "evidence", "witness", "clause", "notice",
            "compliance", "liability", "quash", "stay", "interim"
        ]

        has_legal_terms = any(kw in q for kw in legal_keywords)
        
        # Check for obvious non-legal prompts
        import re
        non_legal_patterns = [
            r"(?i)\b(?:recipe|bake|cook|cake|pizza|burger|pasta|dish|curry)\b",
            r"(?i)\b(?:poem|song|lyrics|joke|riddle|bedtime\s+story)\b",
            r"(?i)\b(?:python|javascript|c\+\+|java|html|css|react|sql)\s+(?:code|script|program|function|algorithm|game|app)\b",
            r"(?i)\b(?:cricket|football|soccer|tennis|basketball|world\s+cup|match|score|ipl)\b",
            r"(?i)\b(?:weather|forecast|temperature|climate\s+in)\b",
            r"(?i)\bwho\s+is\s+(?:the\s+best|the\s+greatest|better)\b",
        ]
        is_explicit_non_legal = any(re.search(pat, q) for pat in non_legal_patterns)

        # Ensure security injections are evaluated by SECURITY_CHECK, not bypassed as innocent out-of-scope
        is_safe, _, _, _ = self.input_guard.validate_with_score(ctx["query"])
        if not is_safe:
            ctx["intent"] = "adversarial_probe"
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.CLASSIFY.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"intent": "adversarial_probe"}
            )

        # Check for conversational greetings, capability questions, and chatbot interaction
        conversational_patterns = [
            r"(?i)^(?:hi|hello|hey|heya|howdy|namaste|greetings)\b",
            r"(?i)\b(?:how\s+are\s+you|are\s+you\s+(?:working|online|there|alive|ok|alright|ready))\b",
            r"(?i)\b(?:who\s+are\s+you|what\s+is\s+your\s+name|what\s+can\s+you\s+do|introduce\s+yourself|tell\s+me\s+about\s+yourself)\b",
            r"(?i)\b(?:good\s+(?:morning|afternoon|evening|day|night))\b",
            r"(?i)^(?:test|testing|check|help|can\s+you\s+help|start|info)\b",
        ]
        is_conversational = any(re.search(pat, q.strip()) for pat in conversational_patterns)
        if is_conversational and not has_legal_terms:
            ctx["intent"] = "conversational"
            ctx["is_conversational"] = True
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.CLASSIFY.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"intent": "conversational"}
            )

        # A question asked inside a project vault is answered against the user's own
        # uploaded documents, which ARE the corpus for that scope. Requiring a statutory
        # keyword there refused legitimate questions about the user's own material
        # ("what is the notice period in this agreement?") as out-of-scope. The explicit
        # non-legal patterns above still refuse regardless of scope, and Layer 1 has
        # already validated the input, so the security boundary is unchanged.
        vault_scoped = bool(ctx.get("vault_id"))
        # Recorded so retrieval can refuse to pull STATUTORY text for a vault question that has no
        # legal subject ("capital of France" lexically matches an old Act that mentions France).
        ctx["has_legal_terms"] = bool(has_legal_terms)
        has_session_documents = self._session_has_uploads(ctx.get("session_id"))
        user_docs_present = vault_scoped or has_session_documents

        # Check for inquiries about uploaded documents when no documents are present
        doc_inquiry_patterns = [
            r"(?i)\b(?:have\s+i|did\s+i|is\s+there\s+(?:a|any)|what|show\s+(?:me\s+)?(?:the|my)|list)\s+(?:uploaded\s+|my\s+)?(?:pdf|document|file|doc)s?\b",
            r"(?i)\b(?:pdf|document|file)s?\s+(?:uploaded|attached|present|in\s+this\s+(?:session|chat|vault))\b",
            r"(?i)\b(?:do\s+you\s+see|can\s+you\s+see|where\s+is)\s+(?:my\s+|the\s+)?(?:pdf|document|file)\b",
            r"(?i)\b(?:upload|uploaded)\s+(?:the\s+)?(?:pdf|document|file)\b",
        ]
        is_doc_inquiry = any(re.search(pat, q.strip()) for pat in doc_inquiry_patterns)
        if is_doc_inquiry and not user_docs_present:
            ctx["is_out_of_scope"] = True
            ctx["intent"] = "out_of_scope"
            ctx["failure_kind"] = "out_of_scope"
            ctx["clean_answer"] = (
                "No documents or PDFs have been uploaded to this session yet.\n\n"
                "To ask questions about a specific document or contract, please upload it first "
                "using the upload button in the chat or within a Project Vault. "
                "Once uploaded, I can analyze its clauses, summarize contents, and cross-reference provisions with Indian statutory law."
            )
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.CLASSIFY.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="out_of_scope",
                details={"intent": "doc_inquiry_no_uploads", "reason": "User inquired about uploaded documents but none exist in session"}
            )

        if is_explicit_non_legal or (not has_legal_terms and not user_docs_present and len(q.split()) > 5):
            ctx["is_out_of_scope"] = True
            ctx["intent"] = "out_of_scope"
            ctx["failure_kind"] = "out_of_scope"
            ctx["clean_answer"] = (
                "### Legal Scope Refusal: Domain-Restricted System\n\n"
                "DFrag is a dedicated statutory intelligence and legal research system restricted exclusively "
                "to Indian law, procedural codes, compliance, regulatory analysis, and judicial precedent.\n\n"
                "- **Status**: The submitted inquiry falls outside the legal, statutory, and regulatory domain.\n"
                "- **Recommended Action**: Please submit an inquiry regarding Indian statutory law, legal compliance, contract clauses, or judicial proceedings."
            )
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.CLASSIFY.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="out_of_scope",
                details={"intent": "out_of_scope", "reason": "Query does not contain legal or statutory subject matter"}
            )

        if "section" in q or "act" in q or "ipc" in q or "crpc" in q or "bns" in q:
            ctx["intent"] = "statutory_lookup"
        elif "case" in q or "judgment" in q or "vs" in q or "v." in q:
            ctx["intent"] = "case_law"
        else:
            ctx["intent"] = "general_legal"

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.CLASSIFY.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"intent": ctx["intent"]}
        )

    async def _run_security_check(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        if not ctx["shield_on"]:
            ctx["security_passed"] = True
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.SECURITY_CHECK.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="skipped",
                details={"shield_on": False}
            )

        is_safe, reason, inj_score, q_hash = self.input_guard.validate_with_score(ctx["query"])
        ctx["security_passed"] = is_safe
        ctx["injection_score"] = inj_score

        if not is_safe:
            ctx["blocked_by"] = "layer1"
            ctx["block_reason"] = reason
            ctx["failure_kind"] = "security_block"
            ctx["clean_answer"] = f"Query blocked by Security Shield: {reason}"
            self.audit_logger.log(
                action="orchestrator_blocked_input",
                layer="layer1",
                injection_score=inj_score,
                retrieval_hits=0,
                citations_used=0,
                validation_pass_fail="blocked_input",
                model_tier_used=ctx["model"],
                latency_ms=(time.time() - t0) * 1000
            )

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.SECURITY_CHECK.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success" if is_safe else "blocked",
            details={"injection_score": inj_score, "is_safe": is_safe, "reason": reason}
        )

    async def _run_plan(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        # Dynamic planning: determine if tools should be invoked based on query intent
        q = ctx["query"].lower()
        import re

        if any(term in q for term in ["amendment", "in force", "live status", "repealed", "validity", "currency check"]):
            ctx["requires_tool_call"] = True
            ctx["planned_tool"] = "live_statute_checker"
        elif any(term in q for term in ["case law", "precedent", "judgment", "court ruling", "kanoon", " landmark "]):
            ctx["requires_tool_call"] = True
            ctx["planned_tool"] = "ecourts_case_search"
        elif any(term in q for term in ["gazette", "official publication", "indiacode", "enactment date", "registry"]):
            ctx["requires_tool_call"] = True
            ctx["planned_tool"] = "indiacode_fetcher"
        elif re.search(r"\b(?:section|sec\.?)\s*\d+[a-z]*\b", q) and any(act in q for act in ["act", "code", "sanhita", "adhiniyam", "ipc", "crpc", "bns", "it"]):
            # Specific section lookup via MCP tool
            ctx["requires_tool_call"] = True
            ctx["planned_tool"] = "local_provision_lookup"
        else:
            ctx["requires_tool_call"] = False
            ctx["planned_tool"] = None

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.PLAN.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"requires_tool_call": ctx["requires_tool_call"], "planned_tool": ctx["planned_tool"]}
        )

    async def _run_retrieve(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()

        if ctx.get("is_conversational"):
            ctx["retrieved_chunks"] = []
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.RETRIEVE.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"chunks_found": 0, "conversational": True}
            )

        profile = ctx.get("profile") or settings.reasoning.for_effort("medium")
        top_k = int(profile["retrieval_top_k"])
        t_lex = time.perf_counter()
        t1_results, t2_results = self._retrieve_for_query(ctx["query"], ctx, top_k)
        if ctx.get("vault_id") and ctx.get("has_legal_terms") is False:
            t1_results = []
        agent_steps = None
        if settings.retrieval.agentic_retrieval_enabled and not ctx.get("is_conversational"):
            from app.agents import retrieval_agent
            from app.retrieval import relevance
            from app.retrieval.bm25_index import tier1_bm25_index
            if len(retrieval_agent.plan_subqueries(ctx["query"])) > 1:
                stats = tier1_bm25_index.term_stats(relevance.stem)
                def _fetch(sq):
                    a, b = self._retrieve_for_query(sq, ctx, top_k)
                    return [{**c, "_tier": 1} for c in a] + [{**c, "_tier": 2} for c in b]
                out = retrieval_agent.run(
                    ctx["query"], _fetch,
                    lambda sq, ch: any(relevance.supports_query(sq, c.get("text", ""), stats=stats) for c in ch),
                    max_chunks=int(profile["max_evidence_chunks"]) * 2)
                agent_steps = out["steps"]
                merged = out["chunks"]
                t1_results = [{k: v for k, v in c.items() if k != "_tier"} for c in merged if c.get("_tier") == 1]
                t2_results = [{k: v for k, v in c.items() if k != "_tier"} for c in merged if c.get("_tier") == 2]
        retrieval_ms = (time.perf_counter() - t_lex) * 1000

        # Citation-graph context expansion: statutory sections that retrieved sections cite in their own text.
        graph_added = 0
        graph_ms = 0.0
        if int(profile.get("graph_expansion", 0)) and t1_results:
            t_g = time.perf_counter()
            try:
                from app.services.citation_graph_service import citation_graph_service
                neighbors = citation_graph_service.corpus_neighbors(
                    t1_results, limit=max(1, int(profile["max_evidence_chunks"]) // 3)
                )
                have = {(str(c.get("act")), str(c.get("section"))) for c in t1_results}
                for n in neighbors:
                    if (str(n.get("act")), str(n.get("section"))) not in have:
                        t1_results.append(n)
                        graph_added += 1
            except Exception as e:
                logger.debug("Graph expansion skipped: %s", type(e).__name__)
            graph_ms = (time.perf_counter() - t_g) * 1000

        combined = t1_results + t2_results
        # Cap to the budget instead of failing the request when many sources match.
        remaining = max(0, budget.max_retrieved_docs - budget.docs_retrieved)
        combined = combined[:remaining]
        budget.record_docs(len(combined))
        ctx["retrieved_chunks"] = combined
        ctx["metrics"].update({
            "retrieval_ms": round(retrieval_ms, 2),
            "graph_expansion_ms": round(graph_ms, 2),
            "graph_neighbors_added": graph_added,
            "retrieved_chunks": len(combined),
        })

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.RETRIEVE.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"chunks_found": len(combined), "graph_neighbors_added": graph_added, "top_k": top_k,
                     **({"agent_steps": agent_steps} if agent_steps else {})}
        )

    def _retrieve_for_query(self, query: str, ctx: Dict[str, Any], top_k: int):
        """Statutory (relevance-gated) + session + vault retrieval for ONE query string."""
        t1_results = self.tier1_retriever.query(query, top_k=top_k)
        # Relevance gate for statutory hits: ranking returns the "closest" sections even for an
        # unrelated question ("capital of France" -> Companies Act "share capital"). A section
        # is evidence only if it carries the query's distinctive terms (idf-weighted).
        # Explicit section lookups ("Section 66 IT Act") are exact and are not filtered here.
        if not re.search(r"(?i)\b(?:section|sec\.?|s\.|article)\s*\d+", query):
            try:
                from app.retrieval import relevance
                from app.retrieval.bm25_index import tier1_bm25_index
                t1_results = relevance.filter_supported(
                    query, t1_results, settings.retrieval.evidence_min_term_coverage,
                    tier1_bm25_index.term_stats(relevance.stem),
                )
            except Exception as e:
                logger.debug("Statutory relevance gate skipped: %s", type(e).__name__)
        t2_results = self.tier2_retriever.query(ctx["session_id"], query, top_k=top_k, user_id=ctx.get("user_id"))

        # Vault-scoped evidence retrieval (ownership already enforced by the API layer)
        vault_id = ctx.get("vault_id")
        if vault_id:
            try:
                from app.services.ingest import ingest_service
                t2_results.extend(ingest_service.query_vault(vault_id, query, top_k=top_k))
            except Exception as e:
                logger.debug("Vault retrieval notice: %s", type(e).__name__)
        return t1_results, t2_results

    def _extract_tool_arguments(self, tool_name: str, query: str, session_id: str) -> Dict[str, Any]:
        """Dynamically extracts schema-compliant arguments from user query for any planned tool."""
        import re
        q = query.strip()
        
        act_match = re.search(r"(?i)\b([A-Za-z\s]+?)\s+(?:Act|Code|Sanhita)(?:\s*,?\s*\d{4})?", q)
        act_name = act_match.group(0).strip() if act_match else ""

        sec_match = re.search(r"(?i)\b(?:section|sec\.?)\s*(\d+[A-Za-z]*)", q)
        section = f"Section {sec_match.group(1)}" if sec_match else ""
        if tool_name in ("local_provision_lookup", "live_statute_checker") and not (act_name and section):
            return {}  # never substitute a default statute the user did not ask about

        if tool_name == "local_statute_search":
            return {"query": q, "top_k": 5}
        elif tool_name == "local_provision_lookup":
            return {"act": act_name, "section": section}
        elif tool_name == "user_document_search":
            return {"session_id": session_id, "query": q, "top_k": 3}
        elif tool_name == "legal_corpus_query":
            return {"query": q, "domain": "statutory_law"}
        elif tool_name == "live_statute_checker":
            return {"act_name": act_name, "section": section}
        elif tool_name in ("kanoon_case_search", "ecourts_case_search"):
            return {"keywords": q, "max_cases": 3}
        elif tool_name == "indiacode_fetcher":
            return {"act_id": act_name}
        
        return {"query": q}

    async def _run_tool_call(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        tool_name = ctx.get("planned_tool") or "local_provision_lookup"

        # Check circuit breaker before dispatch
        if not circuit_breaker.can_execute("TOOL_CALL"):
            logger.warning("Circuit breaker OPEN for TOOL_CALL; skipping tool dispatch and falling back to retrieval.")
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.TOOL_CALL.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="tripped",
                details={"circuit_breaker": "OPEN", "skipped": True}
            )

        tool_args = self._extract_tool_arguments(tool_name, ctx["query"], ctx["session_id"])
        if not tool_args:
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.TOOL_CALL.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="skipped",
                details={"tool_name": tool_name, "reason": "query does not name a specific act and section"}
            )
        budget.record_tool_call()
        try:
            # Safe dispatch through MCP gateway with output sanitization
            res: MCPResponse = mcp_gateway.execute_tool(
                tool_name=tool_name,
                arguments=tool_args,
                session_id=ctx["session_id"],
                network_mode=None
            )
            if res.success:
                circuit_breaker.record_success("TOOL_CALL")
                ctx["tool_results"].append(res.data)
                outcome = "success"
            else:
                circuit_breaker.record_failure("TOOL_CALL", reason=res.error or "Tool returned failure")
                outcome = "failure"
        except Exception as exc:
            circuit_breaker.record_failure("TOOL_CALL", reason=str(exc))
            outcome = "failure"

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.TOOL_CALL.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome=outcome,
            details={"tool_name": tool_name, "arguments": tool_args}
        )

    async def _run_evidence_validation(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        # Consolidate retrieved chunks and MCP tool results
        valid_chunks = list(ctx.get("retrieved_chunks", []))
        
        # Incorporate verified MCP tool results directly into model evidence context
        for tr in ctx.get("tool_results", []):
            if isinstance(tr, dict):
                if "results" in tr and isinstance(tr["results"], list):
                    for r in tr["results"]:
                        if isinstance(r, dict):
                            r_copy = dict(r)
                            r_copy["doc_type"] = "mcp_tool_result"
                            valid_chunks.append(r_copy)
                elif tr.get("found") and tr.get("text"):
                    valid_chunks.append({
                        "act": tr.get("act", "Statutory Provision"),
                        "section": tr.get("section", ""),
                        "text": tr.get("text", ""),
                        "doc_type": "mcp_tool_result",
                        "source": "mcp_provision_lookup"
                    })
                elif "cases" in tr and isinstance(tr["cases"], list):
                    for c in tr["cases"]:
                        if isinstance(c, dict):
                            valid_chunks.append({
                                "act": c.get("title", "Case Precedent"),
                                "section": c.get("citation", ""),
                                "text": f"Judicial Precedent: {c.get('title')} ({c.get('citation')}). Relevance: {c.get('relevance', 'High')}.",
                                "doc_type": "mcp_tool_result",
                                "source": "mcp_case_search"
                            })
                elif tr.get("details"):
                    valid_chunks.append({
                        "act": tr.get("act_name", "Statutory Authority"),
                        "section": tr.get("section") or "Enactment Status",
                        "text": f"Status: {tr.get('status', 'In Force')}. {tr.get('details')}",
                        "doc_type": "mcp_tool_result",
                        "source": "mcp_statute_checker"
                    })
                elif tr.get("official_title"):
                    valid_chunks.append({
                        "act": tr.get("official_title", "Official Gazette"),
                        "section": tr.get("gazette_ref") or "Gazette Reference",
                        "text": f"Official Enactment Date: {tr.get('enactment_date', 'N/A')}. Gazette Reference: {tr.get('gazette_ref', 'N/A')}",
                        "doc_type": "mcp_tool_result",
                        "source": "mcp_indiacode"
                    })

        query_text = ctx.get("query", "").lower()
        
        # Statutory enactment relevancy gate (Task 1.2.1)
        import re
        act_match = re.search(r"(?i)\b([a-z\s]+?)\s+(?:act|code|sanhita|adhiniyam)(?:\s*,?\s*\d{4})?", query_text)
        if act_match:
            targeted_act = act_match.group(0).lower().strip()
            GENERIC_ACT_WORDS = {
                "the", "under", "this", "that", "with", "from", "laws", "provisions", "rules",
                "act", "code", "sanhita", "adhiniyam", "indian", "bharatiya", "national",
                "central", "state", "union", "section", "sections", "of", "and", "in", "for", "to"
            }
            distinctive_tokens = [w for w in re.findall(r"\b[a-z]+\b", targeted_act) if w not in GENERIC_ACT_WORDS]
            if distinctive_tokens:
                expanded_tokens = set(distinctive_tokens)
                if "information" in distinctive_tokens or "technology" in distinctive_tokens:
                    expanded_tokens.add("it")
                if "it" in distinctive_tokens:
                    expanded_tokens.update(["information", "technology"])
                if "data" in distinctive_tokens or "dpdpa" in distinctive_tokens:
                    expanded_tokens.update(["dpdpa", "data", "protection"])
                if "nyaya" in distinctive_tokens or "bns" in distinctive_tokens:
                    expanded_tokens.update(["bns", "nyaya"])
                if "suraksha" in distinctive_tokens or "bnss" in distinctive_tokens or "nagarik" in distinctive_tokens:
                    expanded_tokens.update(["bnss", "nagarik", "suraksha"])
                if "sakshya" in distinctive_tokens or "bsa" in distinctive_tokens:
                    expanded_tokens.update(["bsa", "sakshya"])
                if "companies" in distinctive_tokens:
                    expanded_tokens.add("companies")
                if "contract" in distinctive_tokens:
                    expanded_tokens.add("contract")
                if "consumer" in distinctive_tokens:
                    expanded_tokens.add("consumer")

                matched_act_chunks = []
                for c in valid_chunks:
                    # Preserve user, vault documents, and verified MCP tool results from pure statutory enactment pruning
                    if c.get("doc_type") in ("user_document", "vault_document", "mcp_tool_result"):
                        matched_act_chunks.append(c)
                        continue
                    chunk_act = (c.get("act") or "").lower()
                    chunk_words = set(re.findall(r"\b[a-z]+\b", chunk_act))
                    if any(tok in chunk_act or tok in chunk_words for tok in expanded_tokens):
                        matched_act_chunks.append(c)
                valid_chunks = matched_act_chunks
        
        if ctx.get("is_conversational"):
            ctx["validated_evidence"] = []
            ctx["sources"] = []
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.EVIDENCE_VALIDATION.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"conversational": True}
            )

        # Numeric threshold gate (Task 1.2.1): Require valid retrieved evidence
        if not valid_chunks:
            ctx["insufficient_evidence"] = True
            ctx["failure_kind"] = "insufficient_evidence"
            ctx["validated_evidence"] = []
            ctx["sources"] = []
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.EVIDENCE_VALIDATION.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="insufficient_evidence",
                details={"reason": "No relevant statutory chunks found in corpus matching the queried legal enactment"}
            )

        # A vault-scoped request names the user's own documents as the context. Ranked
        # purely by RRF they sit below the statutory corpus and are cut by the evidence
        # cap below before the token budget even runs: a question about an uploaded PDF
        # returned five statutes and dropped the one chunk that could answer it.
        # Stable sort, so relative order inside each group is preserved.
        if ctx.get("vault_id") or any(c.get("doc_type") in ("vault_document", "user_document") for c in valid_chunks):
            valid_chunks.sort(
                key=lambda c: 0 if c.get("doc_type") in ("vault_document", "user_document") else 1
            )

        profile = ctx.get("profile") or settings.reasoning.for_effort("medium")
        context_window = self._model_context_window(ctx.get("model"))
        budget_mgr = TokenBudgetManager(
            context_limit=int(context_window * float(profile["context_fraction"])),
            max_output_tokens=int(profile["max_output_tokens"]),
        )
        system_prompt_tokens = max(1, len(self.trusted_context.get_v4_system_prompt()) // 4)
        ranked = self._dedupe_evidence(valid_chunks)[: int(profile["max_evidence_chunks"])]
        fitted_chunks, dropped = budget_mgr.fit_chunks(
            base_prompt_tokens=system_prompt_tokens + len(ctx.get("query", "")) // 4,
            chunks=ranked,
        )
        ctx["validated_evidence"] = fitted_chunks
        # Private case material must never reach a cloud provider (enforced in CloudRuntime).
        from app.runtime import egress_guard
        if ctx.get("vault_id"):
            egress_guard.mark_private_context("request is scoped to a vault")
        egress_guard.mark_private_from_chunks(fitted_chunks)
        ctx["sources"] = self.citation_builder.build(fitted_chunks)
        evidence_tokens = sum(len(c.get("text", "")) // 4 for c in fitted_chunks)
        ctx["metrics"].update({
            "max_context_tokens": context_window,
            "context_budget_tokens": budget_mgr.available_prompt_tokens,
            "system_prompt_tokens_est": system_prompt_tokens,
            "evidence_tokens_est": evidence_tokens,
            "evidence_chunks_used": len(fitted_chunks),
            "evidence_chunks_dropped": dropped + max(0, len(valid_chunks) - len(ranked)),
            "remaining_context_budget_est": max(0, budget_mgr.available_prompt_tokens - evidence_tokens - system_prompt_tokens),
        })

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.EVIDENCE_VALIDATION.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"validated_chunks": len(fitted_chunks), "sources": len(ctx["sources"])}
        )

    async def _run_synthesis(self, ctx: Dict[str, Any], budget: ExecutionBudget, retry_note: Optional[str] = None) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()

        if ctx.get("is_conversational"):
            runtime = RuntimeManager.get()
            target_model = ctx["model"]
            conversational_prompt = (
                f"You are DFrag Legal Copilot, an AI legal workspace assistant specializing in Indian Law. "
                f"Respond to the user in a warm, polite, and natural human-to-human conversational tone. "
                f"Acknowledge their greeting or query, confirm that you are running and ready to help, "
                f"and guide them on how you can assist with Indian statutory research, case precedents, contract clauses, or legal drafting.\n\n"
                f"User: {ctx['query']}\n\nAssistant:"
            )
            ctx["prompt"] = conversational_prompt
            prompt_token_estimate = len(conversational_prompt) // 4
            budget.record_tokens(prompt_token_estimate)
            try:
                raw_answer = await runtime.generate(
                    conversational_prompt, model=target_model, options={"num_predict": 256}
                )
            except Exception as exc:
                logger.warning("Conversational generation unavailable: %s", type(exc).__name__)
                ctx["failure_kind"] = "model_unavailable"
                raw_answer = (
                    "The local model is not available right now, so I can't reply conversationally. "
                    "You can still ask about statutes, sections or your uploaded documents; retrieved excerpts "
                    "will be shown even without the model. Check Hardware & Models to activate a model."
                )
            ctx["raw_answer"] = raw_answer
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.SYNTHESIS.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"raw_length": len(raw_answer), "model": target_model, "conversational": True}
            )

        # Build secure prompt
        evidence = ctx.get("validated_evidence", [])
        profile = ctx.get("profile") or settings.reasoning.for_effort("medium")
        prompt = self.trusted_context.build_prompt(
            ctx["query"],
            evidence,
            reasoning_effort="high" if int(profile.get("deep_thinking", 0)) else "off",
        )
        if retry_note:
            prompt += f"\n\n[CONSTRAINED_RETRY_INSTRUCTION: Ensure all claims cite the provided legal sections strictly. Prior rejection reason: {retry_note}]"

        ctx["prompt"] = prompt
        runtime = RuntimeManager.get()
        target_model = ctx["model"]

        # Track tokens
        prompt_token_estimate = len(prompt) // 4
        budget.record_tokens(prompt_token_estimate)

        options = {
            "num_predict": int(profile["max_output_tokens"]),
            "num_ctx": self._model_context_window(target_model),
        }
        gen_metrics: Dict[str, Any] = {}
        t_gen = time.perf_counter()
        try:
            # The answering model is exactly the resolved model: no silent substitution on failure.
            if hasattr(runtime, "generate_with_metrics"):
                raw_answer, gen_metrics = await runtime.generate_with_metrics(prompt, model=target_model, options=options)
            else:
                raw_answer = await runtime.generate(prompt, model=target_model, options=options)
        except Exception as exc:
            logger.warning("Model '%s' unavailable for synthesis (%s); returning evidence excerpts only.", target_model, type(exc).__name__)
            ctx["failure_kind"] = "model_unavailable"
            ctx["model_error"] = str(exc)[:300]
            raw_answer = self._synthesize_grounded_answer(ctx["query"], evidence)
        ctx["metrics"].update({
            "model_latency_ms": round((time.perf_counter() - t_gen) * 1000, 2),
            "max_output_tokens": options["num_predict"],
            **{k: v for k, v in gen_metrics.items() if v is not None},
        })
        if gen_metrics.get("hit_output_limit"):
            # Distinguish "ran out of generation budget" from "the evidence only supports a short answer".
            ctx["output_truncated"] = True

        # Extract <deep_thinking> CoT reasoning tags if present
        import re
        dt_match = re.search(r"<deep_thinking>(.*?)</deep_thinking>", raw_answer, re.DOTALL | re.IGNORECASE)
        if dt_match:
            ctx["reasoning_trace"] = dt_match.group(1).strip()
            raw_answer = re.sub(r"<deep_thinking>.*?</deep_thinking>", "", raw_answer, flags=re.DOTALL | re.IGNORECASE).strip()

        answer_tokens = gen_metrics.get("generation_tokens") if gen_metrics else None
        budget.record_tokens(int(answer_tokens) if isinstance(answer_tokens, int) else len(raw_answer) // 4)

        ctx["raw_answer"] = raw_answer

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.SYNTHESIS.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"raw_length": len(raw_answer), "model": target_model}
        )

    async def _run_legal_verification(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        evidence = ctx.get("validated_evidence", [])
        raw_ans = ctx.get("raw_answer", "")

        if ctx.get("is_conversational"):
            ctx["verification_passed"] = True
            ctx["clean_answer"] = raw_ans
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.LEGAL_VERIFICATION.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"is_valid": True, "conversational": True}
            )

        if ctx.get("failure_kind") == "model_unavailable":
            ctx["verification_passed"] = True
            ctx["clean_answer"] = raw_ans
            return StateStepTrace(
                step_number=budget.steps_taken,
                state=AgentState.LEGAL_VERIFICATION.value,
                duration_ms=(time.time() - t0) * 1000,
                outcome="success",
                details={"is_valid": True, "evidence_only": True}
            )

        t_v = time.perf_counter()
        is_valid, error_reason = self.output_guard.validate(raw_ans, evidence, ctx["prompt"])
        ctx["metrics"]["output_validation_ms"] = round((time.perf_counter() - t_v) * 1000, 2)
        ctx["verification_passed"] = is_valid

        if not is_valid:
            ctx["blocked_by"] = "layer3"
            ctx["block_reason"] = error_reason
            ctx["failure_kind"] = "security_block"
            ctx["clean_answer"] = f"Response quarantined: {error_reason}"
        else:
            clean_ans = self.output_guard.last_clean_answer

            # Spec 03: verify the citation contract instead of assuming it. Reuses the
            # existing response_parser rather than adding a parallel implementation.
            # Before this, the orchestrator never parsed [^S:...] tokens at all, so an
            # answer with zero citations was indistinguishable from a fully cited one.
            from app.services.response_parser import response_parser
            t_c = time.perf_counter()
            parsed = response_parser.parse(clean_ans, evidence_chunks=evidence)
            ctx["metrics"]["citation_parse_ms"] = round((time.perf_counter() - t_c) * 1000, 2)
            ctx["grounding_score"] = parsed.grounding_score
            ctx["citations_parsed"] = [c.to_dict() for c in parsed.citations]
            ctx["metrics"]["citations_total"] = parsed.total_citations_count
            ctx["metrics"]["citations_resolved"] = parsed.citations_resolved_count

            # A substantive answer drawn from real evidence that cites nothing has broken
            # the contract. compute_grounding_score() already exempts refusals and
            # insufficient-evidence replies, so those never reach this branch.
            # Grounding score alone decides: 0 when a citation resolves to nothing,
            # 40 when a substantive answer cites nothing, 100 for refusals and
            # insufficient-evidence replies, which therefore never trip this.
            # Keying on 'zero citations' missed the worse case: a confident citation
            # pointing at no evidence at all.
            violated = bool(
                evidence
                and parsed.grounding_score < settings.security.min_grounding_score
            )
            ctx["citation_contract_violated"] = violated

            if violated and settings.security.citation_contract_mode == "block":
                ctx["blocked_by"] = "layer3"
                ctx["block_reason"] = (
                    "Answer withheld: no verifiable citation was produced for evidence-backed claims."
                )
                ctx["failure_kind"] = "ungrounded_output"
                ctx["clean_answer"] = (
                    "Response withheld. The model produced an answer from retrieved evidence but "
                    "emitted no verifiable citation, so its claims could not be traced to a source."
                )
                return StateStepTrace(
                    step_number=budget.steps_taken,
                    state=AgentState.LEGAL_VERIFICATION.value,
                    duration_ms=(time.time() - t0) * 1000,
                    outcome="blocked",
                    details={"is_valid": False, "citation_contract": "violated"}
                )

            ctx["clean_answer"] = self.response_formatter.format(parsed.content or clean_ans)
            try:
                from app.services.response_parser import unsupported_section_mentions
                stray = unsupported_section_mentions(parsed.content or clean_ans, evidence)
                ctx["unsupported_sections"] = stray
                if stray:
                    ctx["clean_answer"] += (
                        "\n\n> **Check before relying on this:** the answer names Section "
                        + ", ".join(stray)
                        + " but that section is not among the sources retrieved for this question."
                    )
            except Exception as exc:
                logger.debug("section mention check skipped: %s", type(exc).__name__)

            if violated:
                ctx["failure_kind"] = ctx.get("failure_kind") or "ungrounded_output"
                ctx["clean_answer"] += (
                    "\n\n> **Unverified:** this answer cites no source that can be checked against "
                    "the retrieved evidence. Treat it as unconfirmed."
                )
            if ctx.get("output_truncated"):
                ctx["clean_answer"] += (
                    "\n\n_Note: the answer reached the output limit for this reasoning level and may be incomplete. "
                    "Ask again with a higher reasoning level for a fuller analysis._"
                )

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.LEGAL_VERIFICATION.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success" if is_valid else "blocked",
            details={"is_valid": is_valid, "error_reason": error_reason}
        )

    @staticmethod
    def _model_context_window(model: Optional[str]) -> int:
        """Smaller of the configured context and the model's registry context window (if known)."""
        configured = int(settings.GENERATOR_CONTEXT_TOKENS)
        try:
            from app.system.model_registry import ModelRegistry
            from app.runtime.model_state import normalize_tag
            reg = ModelRegistry()
            entry = reg.get(model or "") or next(
                (m for m in reg.all_models() if normalize_tag(m.ollama_tag) == normalize_tag(model)), None
            )
            if entry and entry.context_window:
                return min(configured, int(entry.context_window))
        except Exception:
            pass
        return configured

    @staticmethod
    def _dedupe_evidence(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drops exact-duplicate evidence (same source/section/text) while keeping rank order."""
        seen = set()
        out = []
        for c in chunks:
            key = (str(c.get("act")), str(c.get("section")), (c.get("text") or "")[:200])
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    def _format_insufficient_evidence_refusal(self, ctx: Dict[str, Any]) -> str:
        """
        Formats an honest, structured refusal when retrieval returns no relevant provisions (Task 1.2.1, Doc 04 §4.1).
        """
        q = ctx.get("query", "").strip()
        import re
        act_match = re.search(r"(?i)\b(?:the\s+)?([a-z\s]{3,35}\s+(?:act|code|sanhita|adhiniyam)(?:\s*,?\s*\d{4})?)\b", q)
        targeted_act_display = None
        if act_match:
            name = re.sub(r"(?i)^.*?\b(?:of|under|in|per)\s+(?:the\s+)?", "", act_match.group(1)).strip()
            targeted_act_display = name.title() if name else None
        indexed = self._indexed_act_matching(targeted_act_display) if targeted_act_display else None

        if targeted_act_display and indexed:
            lines = [
                "### Insufficient verified evidence",
                "",
                f"*{indexed}* is indexed, but no passage in its indexed text matched this question closely enough to answer it reliably.",
                "",
                "**What you can do**: name the specific section, rephrase using the statute's own wording, or check the section list in the Statute Library.",
            ]
        elif targeted_act_display:
            lines = [
                "### Statutory Corpus Scope Notice: Insufficient Grounded Evidence",
                "",
                f"The requested statute (*{targeted_act_display}*) is not in the indexed statutory corpus.",
                "",
                "DFrag operates under a strict grounding policy where legal facts must reside in verified retrieval evidence rather than parametric model memory.",
                "",
                "**Recommended Actions**:",
                f"1. **Upload Statute to Project Vault**: Upload '{targeted_act_display}' (PDF or text) into your active Project Vault for custom indexing and analysis.",
                "2. **Browse Statute Library**: View indexed statutory enactments in the Statute Library catalog.",
                f"3. **Query Indexed Acts**: {self._indexed_acts_sentence()}"
            ]
        else:
            lines = [
                "### Statutory Corpus Scope Notice: Insufficient Grounded Evidence",
                "",
                "The system evaluated the authoritative Indian statutory corpus and local knowledge base for your inquiry:",
                f"- **Query Analyzed**: \"{q}\"",
                "- **Retrieval Outcome**: No directly matching statutory provisions, sections, or verified case precedents met the minimum relevance threshold.",
                "",
                "**Recommended Actions**:",
                "1. **Specify Statute & Provision**: State the exact Act name (e.g., *Companies Act 2013*, *IT Act 2000*, *BNS 2023*) and Section number.",
                "2. **Upload Document / Case File**: Add the relevant PDF brief or contract into your active Project Vault for custom evidence extraction.",
                "3. **Refine Terminology**: Avoid conversational phrasing; use canonical Indian legal terminology."
            ]
        return "\n".join(lines)

    @staticmethod
    def _indexed_act_matching(name: Optional[str]) -> Optional[str]:
        """Title of an indexed statute whose title contains all distinctive words of `name`."""
        if not name:
            return None
        import re as _re
        stop = {"the", "act", "code", "of", "and"}
        words = [w for w in _re.findall(r"[a-z]+", name.lower()) if w not in stop]
        if not words:
            return None
        try:
            from app.db.engine import get_sync_session
            from app.db.models import Statute
            with get_sync_session() as session:
                for (title,) in session.query(Statute.title).all():
                    title_words = [w for w in _re.findall(r"[a-z]+", title.lower()) if w not in stop]
                    # Whole-word match ("contract" -> Indian Contract Act), or a single token that is
                    # the title's acronym ("IT" -> Information Technology Act). Substring matching
                    # would let "it" match "digital".
                    if all(w in title_words for w in words):
                        return title
                    if len(words) == 1 and len(title_words) > 1 and words[0] == "".join(t[0] for t in title_words):
                        return title
        except Exception:
            return None
        return None

    @staticmethod
    def _indexed_acts_sentence() -> str:
        try:
            from app.db.engine import get_sync_session
            from app.db.models import Statute
            with get_sync_session() as session:
                titles = [t for (t,) in session.query(Statute.title).order_by(Statute.title).limit(12).all()]
        except Exception:
            titles = []
        if not titles:
            return "No statutes are indexed yet. Add act texts to the statutory corpus and re-index."
        return "Currently indexed: " + ", ".join(f"*{t}*" for t in titles) + "."

    def _synthesize_grounded_answer(self, query: str, evidence: List[Dict[str, Any]]) -> str:
        """
        Synthesizes a production-grade statutory response directly from validated evidence chunks
        when local LLM inference is offline or unreachable.
        Adheres strictly to Layer 3 output validation and anti-hallucination budgets.
        """
        if not evidence:
            return (
                "I do not have relevant statutory provisions or legal evidence in the corpus to answer this query. "
                "Please provide a specific legal inquiry or statutory reference."
            )

        acts_found = set()
        sections_found = []
        clean_excerpts = []

        for item in evidence:
            act = item.get("act") or "Statutory Authority"
            sec = item.get("section") or ""
            text = item.get("text", "").strip()
            if act:
                acts_found.add(act)
            if sec and sec not in sections_found:
                sections_found.append(sec)
            if text:
                clean_excerpts.append((act, sec, text))

        act_title = ", ".join(sorted(acts_found)) if acts_found else "Indian Statutory Law"
        sec_title = f" (Sections: {', '.join(sections_found[:4])})" if sections_found else ""

        lines = [
            f"### Retrieved provisions: {act_title}{sec_title}",
            "",
            "The local model did not produce an answer, so no legal analysis was generated. "
            "These are the most relevant excerpts retrieved from the indexed corpus; read them directly:",
            "",
        ]

        for i, (act, sec, text) in enumerate(clean_excerpts[:3], 1):
            sec_header = f"**{sec} ({act})**" if sec else f"**Provision {i} ({act})**"
            snippet = text[:400] + "..." if len(text) > 400 else text
            lines.append(f"{i}. {sec_header}:")
            lines.append(f"   > {snippet}")
            lines.append("")

        lines.append(
            "_Excerpts are quoted from the local corpus; whether they fully answer your question, "
            "and whether the text is current, has not been assessed._"
        )

        return "\n".join(lines)

    def _build_result(
        self,
        ctx: Dict[str, Any],
        final_state: AgentState,
        traces: List[StateStepTrace],
        budget: ExecutionBudget,
        start_time: float
    ) -> OrchestrationResult:
        latency_ms = (time.time() - start_time) * 1000
        sources_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in ctx.get("sources", [])]

        # Log completion event to durable audit logger
        self.audit_logger.log(
            action=f"orchestrator_{final_state.value.lower()}",
            layer="orchestrator",
            injection_score=ctx.get("injection_score", 0.0),
            retrieval_hits=len(ctx.get("retrieved_chunks", [])),
            citations_used=len(sources_dict),
            validation_pass_fail=final_state.value,
            model_tier_used=ctx.get("model", settings.DEFAULT_MODEL),
            latency_ms=latency_ms
        )

        reasoning_trace = ctx.get("reasoning_trace")  # only what the model actually emitted
        metrics = dict(ctx.get("metrics", {}))
        metrics["total_latency_ms"] = round(latency_ms, 2)
        model_used = None if ctx.get("failure_kind") == "model_unavailable" and not ctx.get("is_conversational") else ctx.get("model")

        final_answer = ctx.get("clean_answer") or ctx.get("raw_answer", "")

        # Spec 04 §4.1: Emit ChatResponseFinalized internal event to all decoupled handlers
        try:
            from app.events.chat_events import ChatResponseFinalized, emit_chat_response_finalized
            event = ChatResponseFinalized(
                conversation_id=ctx["session_id"],
                message_id=ctx.get("request_id", str(uuid.uuid4())),
                user_id=ctx.get("user_id", "default_user"),
                query=ctx["query"],
                answer=final_answer,
                citations=sources_dict,
                sources=sources_dict,
                model_used=model_used or "none",
                runtime_used=settings.MODEL_RUNTIME,
                reasoning_trace=reasoning_trace,
                grounding_score=ctx.get("grounding_score"),
                injection_score=ctx.get("injection_score", 0.0),
                retrieval_hits=len(ctx.get("retrieved_chunks", [])),
                latency_ms=latency_ms,
                is_deep_thinking=ctx.get("reasoning_effort") == "high",
                vault_id=ctx.get("vault_id"),
                blocked_by=ctx.get("blocked_by"),
                block_reason=ctx.get("block_reason"),
                failure_kind=ctx.get("failure_kind")
            )
            emit_chat_response_finalized(event)
        except Exception as event_err:
            logger.warning(f"Event fanout notice: {event_err}")

        return OrchestrationResult(
            request_id=ctx["request_id"],
            session_id=ctx["session_id"],
            final_state=final_state,
            answer=final_answer,
            sources=sources_dict,
            blocked_by=ctx.get("blocked_by"),
            block_reason=ctx.get("block_reason"),
            failure_kind=ctx.get("failure_kind"),
            correlation_id=ctx.get("request_id"),
            reasoning_trace=reasoning_trace,
            steps_trace=traces,
            budget_snapshot=budget.snapshot(),
            latency_ms=latency_ms,
            model_used=model_used,
            runtime_used=settings.MODEL_RUNTIME,
            metrics=metrics,
            grounding_score=ctx.get("grounding_score"),
            citations_parsed=ctx.get("citations_parsed"),
            citation_contract_violated=bool(ctx.get("citation_contract_violated")),
        )


research_orchestrator = ResearchStateMachine()
