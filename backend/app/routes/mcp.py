import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp.tool_registry import tool_registry
from app.mcp.policy_engine import policy_engine
from app.mcp.gateway import mcp_gateway, MCPResponse
from app.db.engine import get_sync_session
from app.db.models import MCPToolCall

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of registered tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments matching tool schema")
    session_id: Optional[str] = Field(default="default_session", description="Active user session ID")
    network_mode: Optional[str] = Field(default=None, description="Optional override for network mode (OFFLINE / ONLINE)")


class MCPStatusResponse(BaseModel):
    enabled: bool
    current_network_mode: str
    categories: List[str]
    active_servers: List[Dict[str, Any]]
    total_registered_tools: int
    tools: List[Dict[str, Any]]


@router.get("/status", response_model=MCPStatusResponse)
def get_mcp_status():
    """
    Returns real-time status of the MCP gateway, registered categories,
    active servers, and schema-validated tool definitions.
    """
    categories = list(policy_engine._policy_data.get("categories", {}).keys())
    servers_cfg = policy_engine._policy_data.get("servers", {})
    
    active_servers = []
    for srv_name, srv_data in servers_cfg.items():
        active_servers.append({
            "name": srv_name,
            "enabled": srv_data.get("enabled", True),
            "policy": srv_data.get("default_policy", "allow"),
            "allowed_tools": srv_data.get("allowed_tools", []),
            "denied_tools": srv_data.get("denied_tools", [])
        })

    all_tools = tool_registry.list_tools()

    return MCPStatusResponse(
        enabled=policy_engine._policy_data.get("global", {}).get("enabled", True),
        current_network_mode=settings.network_mode.default_mode,
        categories=categories,
        active_servers=active_servers,
        total_registered_tools=len(all_tools),
        tools=all_tools
    )


@router.post("/tool-call", response_model=MCPResponse)
def execute_tool_call(request: MCPToolCallRequest):
    """
    Executes a tool call through Policy Engine, Permission Layer, Gateway,
    Context Sanitizer, and Cryptographic Audit Ledger.
    """
    response = mcp_gateway.execute_tool(
        tool_name=request.tool_name,
        arguments=request.arguments,
        session_id=request.session_id,
        network_mode=request.network_mode
    )
    return response


@router.get("/history")
def get_mcp_history(limit: int = Query(default=50, ge=1, le=200)):
    """Fetches recent MCP tool invocation telemetry and audit logs."""
    try:
        with get_sync_session() as session:
            calls = session.query(MCPToolCall).order_by(MCPToolCall.id.desc()).limit(limit).all()
            return {"total": len(calls), "history": [c.to_dict() for c in calls]}
    except Exception as e:
        logger.error(f"Error fetching MCP history: {e}")
        return {"total": 0, "history": []}
