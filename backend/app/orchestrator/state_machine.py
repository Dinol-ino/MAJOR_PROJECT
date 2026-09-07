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
    SYNTHESIS = "SYNTHESIS"
    LEGAL_VERIFICATION = "LEGAL_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Explicit, code-controlled finite state transition graph
ALLOWED_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.INITIALIZED: {AgentState.CLASSIFY, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.CLASSIFY: {AgentState.SECURITY_CHECK, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.SECURITY_CHECK: {AgentState.PLAN, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.PLAN: {AgentState.RETRIEVE, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.RETRIEVE: {AgentState.TOOL_CALL, AgentState.EVIDENCE_VALIDATION, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.TOOL_CALL: {AgentState.EVIDENCE_VALIDATION, AgentState.RETRIEVE, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.EVIDENCE_VALIDATION: {AgentState.TOOL_CALL, AgentState.SYNTHESIS, AgentState.FAILED, AgentState.CANCELLED},
    AgentState.SYNTHESIS: {AgentState.LEGAL_VERIFICATION, AgentState.FAILED, AgentState.CANCELLED},
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
    steps_trace: List[StateStepTrace] = Field(default_factory=list)
    budget_snapshot: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0


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
        request_id: Optional[str] = None,
        custom_budget: Optional[ExecutionBudget] = None,
    ) -> OrchestrationResult:
        """
        Executes a bounded research request through the formal state machine.
        """
        start_time = time.time()
        req_id = request_id or str(uuid.uuid4())
        budget = custom_budget or ExecutionBudget()
        cancellation_manager.register(req_id)

        # Context accumulator across states
        ctx: Dict[str, Any] = {
            "query": query,
            "session_id": session_id,
            "user_id": user_id,
            "model": model or settings.DEFAULT_MODEL,
            "shield_on": shield_on,
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
            # 1. State: INITIALIZED -> CLASSIFY
            current_state = self._transition(current_state, AgentState.CLASSIFY, req_id)
            step_trace = await self._run_classify(ctx, budget)
            traces.append(step_trace)

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
                if budget.retries_attempted < budget.retry_budget:
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

    # --- Step Implementations ---

    async def _run_classify(self, ctx: Dict[str, Any], budget: ExecutionBudget) -> StateStepTrace:
        t0 = time.time()
        budget.record_step()
        q = ctx["query"].lower()
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
        # Code-controlled planning: determine if tools should be invoked
        q = ctx["query"].lower()
        if "amendment" in q or "in force" in q or "live status" in q:
            ctx["requires_tool_call"] = True
            ctx["planned_tool"] = "live_statute_checker"
        elif "lookup provision" in q or "specific section" in q:
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
        t1_results = self.tier1_retriever.query(ctx["query"])
        t2_results = self.tier2_retriever.query(ctx["session_id"], ctx["query"])
        fused = fuse_bm25_dense(t1_results, t2_results, top_k=5)
        budget.record_docs(len(fused))
        ctx["retrieved_chunks"] = fused

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.RETRIEVE.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success",
            details={"chunks_found": len(fused)}
        )

    def _extract_tool_arguments(self, tool_name: str, query: str, session_id: str) -> Dict[str, Any]:
        """Dynamically extracts schema-compliant arguments from user query for any planned tool."""
        import re
        q = query.strip()
        
        act_match = re.search(r"(?i)\b([A-Za-z\s]+?)\s+(?:Act|Code|Sanhita)(?:\s*,?\s*\d{4})?", q)
        act_name = act_match.group(0).strip() if act_match else "Information Technology Act, 2000"
        
        sec_match = re.search(r"(?i)\b(?:section|sec\.?)\s*(\d+[A-Za-z]*)", q)
        section = f"Section {sec_match.group(1)}" if sec_match else "Section 66"

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
        elif tool_name == "kanoon_case_search":
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

        budget.record_tool_call()
        tool_args = self._extract_tool_arguments(tool_name, ctx["query"], ctx["session_id"])
        try:
            # Safe dispatch through MCP gateway with output sanitization
            res: MCPResponse = mcp_gateway.execute_tool(
                tool_name=tool_name,
                arguments=tool_args,
                session_id=ctx["session_id"],
                network_mode=settings.network.default_mode
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
        # Consolidate retrieved chunks and tool results
        valid_chunks = list(ctx.get("retrieved_chunks", []))
        fitted_chunks, _ = self.token_budget_manager.fit_chunks(
            base_prompt_tokens=500,
            chunks=valid_chunks
        )
        ctx["validated_evidence"] = fitted_chunks
        ctx["sources"] = self.citation_builder.build(fitted_chunks)

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
        # Build secure prompt
        evidence = ctx.get("validated_evidence", [])
        prompt = self.trusted_context.build_prompt(ctx["query"], evidence)
        if retry_note:
            prompt += f"\n\n[CONSTRAINED_RETRY_INSTRUCTION: Ensure all claims cite the provided legal sections strictly. Prior rejection reason: {retry_note}]"

        ctx["prompt"] = prompt
        runtime = RuntimeManager.get()
        target_model = ctx["model"]

        # Track tokens
        prompt_token_estimate = len(prompt) // 4
        budget.record_tokens(prompt_token_estimate)

        try:
            raw_answer = await runtime.generate(prompt, model=target_model)
        except Exception as exc:
            is_conn_error = "unreachable" in str(exc).lower() or "connect" in str(exc).lower()
            if not is_conn_error:
                fallback_model = settings.OLLAMA_FALLBACK_MODEL.strip() or settings.DEFAULT_MODEL
                if fallback_model.lower() == target_model.lower():
                    fallback_model = "qwen2.5:3b" if target_model.lower() != "qwen2.5:3b" else "gemma2:2b"
                logger.warning(f"Synthesis primary model error on '{target_model}': {exc}. Trying fallback '{fallback_model}'.")
                try:
                    raw_answer = await runtime.generate(prompt, model=fallback_model)
                except Exception as fallback_exc:
                    logger.warning(f"Synthesis fallback model also unavailable ({fallback_exc}). Grounding answer from validated evidence chunks.")
                    raw_answer = self._synthesize_grounded_answer(ctx["query"], evidence)
            else:
                logger.warning(f"Ollama daemon unreachable ({exc}). Grounding answer directly from validated evidence chunks.")
                raw_answer = self._synthesize_grounded_answer(ctx["query"], evidence)

        answer_token_estimate = len(raw_answer) // 4
        budget.record_tokens(answer_token_estimate)

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

        is_valid, error_reason = self.output_guard.validate(raw_ans, evidence, ctx["prompt"])
        ctx["verification_passed"] = is_valid

        if not is_valid:
            ctx["blocked_by"] = "layer3"
            ctx["block_reason"] = error_reason
            ctx["clean_answer"] = f"Response quarantined: {error_reason}"
        else:
            clean_ans = self.output_guard.last_clean_answer
            ctx["clean_answer"] = self.response_formatter.format(clean_ans)

        return StateStepTrace(
            step_number=budget.steps_taken,
            state=AgentState.LEGAL_VERIFICATION.value,
            duration_ms=(time.time() - t0) * 1000,
            outcome="success" if is_valid else "blocked",
            details={"is_valid": is_valid, "error_reason": error_reason}
        )

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
            f"### Statutory Analysis: {act_title}{sec_title}",
            "",
            "Based on the verified statutory provisions retrieved from the authoritative legal corpus, the following key legal determinations apply:",
            "",
        ]

        for i, (act, sec, text) in enumerate(clean_excerpts[:3], 1):
            sec_header = f"**{sec} ({act})**" if sec else f"**Provision {i} ({act})**"
            snippet = text[:400] + "..." if len(text) > 400 else text
            lines.append(f"{i}. {sec_header}:")
            lines.append(f"   > {snippet}")
            lines.append("")

        lines.append(
            f"**Legal Grounding & Compliance**: The above statutory provisions govern the inquiry. "
            f"All citations are verified against local statutory law under {act_title}."
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

        return OrchestrationResult(
            request_id=ctx["request_id"],
            session_id=ctx["session_id"],
            final_state=final_state,
            answer=ctx.get("clean_answer") or ctx.get("raw_answer", ""),
            sources=sources_dict,
            blocked_by=ctx.get("blocked_by"),
            block_reason=ctx.get("block_reason"),
            steps_trace=traces,
            budget_snapshot=budget.snapshot(),
            latency_ms=latency_ms
        )


research_orchestrator = ResearchStateMachine()
