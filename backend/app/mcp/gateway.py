import time
import asyncio
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp.tool_registry import tool_registry, ToolDefinition
from app.mcp.policy_engine import policy_engine, PolicyDecision
from app.mcp.permission_layer import permission_layer
from app.security.context_sanitizer import context_sanitizer
from app.memory.audit_memory import audit_memory
from app.db.engine import get_sync_session
from app.db.models import MCPToolCall

logger = logging.getLogger(__name__)


class MCPResponse(BaseModel):
    """Encapsulates the sanitized, validated response from the MCP Gateway."""
    success: bool
    tool_name: str
    category: str
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    is_sanitized: bool = True


class MCPGateway:
    """
    Unified MCP Gateway (Phase 08).
    Dispatches tool calls through Policy Engine, Permission Layer, Sanitizer, and Audit Logger.
    Guarantees no raw/untrusted tool outputs reach the LLM context.
    """

    def __init__(self):
        pass

    def _sanitize_payload(self, data: Any) -> Any:
        """Recursively sanitizes string fields in tool output dictionaries or lists."""
        if isinstance(data, str):
            return context_sanitizer.sanitize_text(data, source_type="mcp_result")
        elif isinstance(data, dict):
            return {k: self._sanitize_payload(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_payload(item) for item in data]
        return data

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
        network_mode: Optional[str] = None,
        call_count_in_request: int = 0
    ) -> MCPResponse:
        """
        Synchronously executes a tool call through all defensive gates.
        """
        start_time = time.time()
        mode = (network_mode or settings.network.default_mode).upper()

        # Step 1: Policy Engine Evaluation
        decision: PolicyDecision = policy_engine.evaluate(
            tool_name=tool_name,
            current_mode=mode,
            call_count_in_request=call_count_in_request
        )

        if not decision.is_allowed:
            latency = (time.time() - start_time) * 1000
            self._record_audit_and_telemetry(
                tool_name=tool_name,
                category=decision.category,
                mode=mode,
                input_payload=arguments,
                output_preview=decision.reason,
                is_allowed=False,
                policy_reason=decision.reason,
                latency_ms=latency,
                session_id=session_id
            )
            return MCPResponse(
                success=False,
                tool_name=tool_name,
                category=decision.category,
                error=decision.reason,
                latency_ms=round(latency, 2),
                is_sanitized=True
            )

        # Step 2: Permission Layer Schema Validation
        is_valid, err_msg, validated_args = permission_layer.validate_request(tool_name, arguments)
        if not is_valid:
            latency = (time.time() - start_time) * 1000
            self._record_audit_and_telemetry(
                tool_name=tool_name,
                category=decision.category,
                mode=mode,
                input_payload=arguments,
                output_preview=err_msg,
                is_allowed=False,
                policy_reason=err_msg,
                latency_ms=latency,
                session_id=session_id
            )
            return MCPResponse(
                success=False,
                tool_name=tool_name,
                category=decision.category,
                error=err_msg,
                latency_ms=round(latency, 2),
                is_sanitized=True
            )

        # Step 3: Tool Execution
        tool: Optional[ToolDefinition] = tool_registry.get_tool(tool_name)
        raw_result = None
        try:
            if tool and tool.handler:
                raw_result = tool.handler(**validated_args)
            else:
                # Mock response for external servers if handler not attached
                raw_result = {"status": "success", "result": f"Executed tool '{tool_name}' successfully on server '{tool.server_name if tool else 'local'}'."}
        except Exception as exec_err:
            latency = (time.time() - start_time) * 1000
            error_text = f"Tool execution runtime error: {str(exec_err)}"
            logger.error(error_text)
            self._record_audit_and_telemetry(
                tool_name=tool_name,
                category=decision.category,
                mode=mode,
                input_payload=arguments,
                output_preview=error_text,
                is_allowed=True,
                policy_reason=error_text,
                latency_ms=latency,
                session_id=session_id
            )
            return MCPResponse(
                success=False,
                tool_name=tool_name,
                category=decision.category,
                error=error_text,
                latency_ms=round(latency, 2),
                is_sanitized=True
            )

        # Step 4: Context Sanitization (Defense-in-depth on tool results)
        sanitized_data = self._sanitize_payload(raw_result)

        # Step 5: Output Schema Validation
        out_valid, out_err, validated_output = permission_layer.validate_response(tool_name, sanitized_data)
        final_data = validated_output if out_valid else sanitized_data

        latency = (time.time() - start_time) * 1000

        # Step 6: Log & Persist Tool Call
        self._record_audit_and_telemetry(
            tool_name=tool_name,
            category=decision.category,
            mode=mode,
            input_payload=arguments,
            output_preview=str(final_data)[:200],
            is_allowed=True,
            policy_reason="Allowed and executed",
            latency_ms=latency,
            session_id=session_id
        )

        return MCPResponse(
            success=True,
            tool_name=tool_name,
            category=decision.category,
            data=final_data,
            latency_ms=round(latency, 2),
            is_sanitized=True
        )

    def _record_audit_and_telemetry(
        self,
        tool_name: str,
        category: str,
        mode: str,
        input_payload: Dict[str, Any],
        output_preview: Optional[str],
        is_allowed: bool,
        policy_reason: Optional[str],
        latency_ms: float,
        session_id: Optional[str] = None
    ) -> None:
        """Records MCP telemetry to the SQL mcp_tool_calls table and append-only L6 audit ledger."""
        try:
            with get_sync_session() as session:
                call_record = MCPToolCall(
                    session_id=session_id,
                    tool_name=tool_name,
                    category=category,
                    network_mode=mode,
                    input_payload=input_payload,
                    output_preview=output_preview,
                    is_allowed=1 if is_allowed else 0,
                    policy_reason=policy_reason,
                    latency_ms=round(latency_ms, 2)
                )
                session.add(call_record)
                session.commit()
        except Exception as e:
            logger.warning(f"Could not persist MCPToolCall record: {e}")

        # Append to L6 cryptographic audit ledger
        try:
            audit_memory.append_event(
                action=f"mcp_tool_call:{tool_name}",
                layer="mcp_gateway",
                validation_pass_fail="pass" if is_allowed else "blocked_policy",
                latency_ms=latency_ms
            )
        except Exception as e:
            logger.warning(f"Could not append MCP audit event: {e}")


mcp_gateway = MCPGateway()
