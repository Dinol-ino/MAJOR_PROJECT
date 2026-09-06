import logging
from typing import Dict, Any, Tuple, Optional
from pydantic import ValidationError

from app.mcp.tool_registry import tool_registry, ToolDefinition

logger = logging.getLogger(__name__)


class MCPPermissionLayer:
    """
    Layer 2 Schema Validation & Permission Boundary (Phase 08).
    Validates tool call request payloads against strict Pydantic schemas.
    Rejects malformed inputs, unapproved parameters, or type violations before dispatch.
    """

    def __init__(self):
        pass

    def validate_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validates arguments against the tool's registered input schema.
        
        Returns:
            Tuple[is_valid, error_message, validated_dict]
        """
        tool: Optional[ToolDefinition] = tool_registry.get_tool(tool_name)
        if not tool:
            return False, f"Unknown tool '{tool_name}' — not found in Tool Registry.", None

        try:
            validated_model = tool.validate_input(arguments or {})
            return True, None, validated_model.model_dump()
        except ValidationError as val_err:
            err_details = "; ".join([f"{e['loc']}: {e['msg']}" for e in val_err.errors()])
            logger.warning(f"Schema violation for tool '{tool_name}': {err_details}")
            return False, f"Schema validation failed for tool '{tool_name}': {err_details}", None
        except Exception as e:
            logger.error(f"Unexpected error validating tool '{tool_name}': {e}")
            return False, f"Unexpected validation error: {str(e)}", None

    def validate_response(
        self,
        tool_name: str,
        result_payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validates execution results against the tool's output schema.
        """
        tool: Optional[ToolDefinition] = tool_registry.get_tool(tool_name)
        if not tool:
            return True, None, result_payload

        try:
            validated_output = tool.validate_output(result_payload or {})
            return True, None, validated_output.model_dump()
        except ValidationError as val_err:
            err_details = "; ".join([f"{e['loc']}: {e['msg']}" for e in val_err.errors()])
            logger.warning(f"Output schema mismatch for tool '{tool_name}': {err_details}")
            return False, f"Output schema validation failed: {err_details}", None
        except Exception as e:
            return True, None, result_payload


permission_layer = MCPPermissionLayer()
