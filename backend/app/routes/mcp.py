import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.mcp.tool_registry import tool_registry
from app.mcp.policy_engine import policy_engine
from app.mcp.gateway import mcp_gateway, MCPResponse
from app.db.engine import get_sync_session
from app.db.models import MCPToolCall, Conversation
from app.routes.auth import get_current_user
from app.security.ownership import claim_session, current_user_id, is_admin

from app.mcp.server_manager import mcp_server_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of registered tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments matching tool schema")
    session_id: Optional[str] = Field(default="default_session", description="Active user session ID")
    # Accepted for backwards compatibility and IGNORED: clients can never override the network mode.
    network_mode: Optional[str] = Field(default=None, description="Ignored; the server-side network mode always applies")


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
    active servers (with real subprocess/health monitoring), and schema-validated tool definitions.
    """
    categories = list(policy_engine._policy_data.get("categories", {}).keys())
    active_servers = mcp_server_manager.get_all_servers_status()
    all_tools = tool_registry.list_tools()

    from app.network.mode_enforcer import mode_enforcer

    return MCPStatusResponse(
        enabled=policy_engine._policy_data.get("global", {}).get("enabled", True),
        current_network_mode=mode_enforcer.get_mode(),
        categories=categories,
        active_servers=active_servers,
        total_registered_tools=len(all_tools),
        tools=all_tools
    )


@router.post("/servers/{server_name}/reconnect")
def reconnect_mcp_server(server_name: str):
    """
    Triggers re-connection and health check for a specific MCP server.
    """
    try:
        updated = mcp_server_manager.reconnect_server(server_name)
        return {"status": "ok", "server": updated}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"MCP Server '{server_name}' not recognized")


@router.post("/discover")
def discover_mcp_tools():
    """
    Spec 04 §2.3: Auto-discovery across connected MCP servers.
    Fetches tool schemas and normalizes them for prompt manifest injection.
    """
    discovered = mcp_server_manager.discover_tools()
    return {
        "status": "ok",
        "total_discovered": len(discovered),
        "tools": discovered
    }



@router.post("/tool-call", response_model=MCPResponse)
def execute_tool_call(request: MCPToolCallRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Executes a tool call through Policy Engine, Permission Layer, Gateway,
    Context Sanitizer, and Cryptographic Audit Ledger.
    """
    # The session must exist and belong to the caller; the verified id (never a client-supplied
    # argument) is what session-scoped tools receive.
    # A shared literal default would let the first caller own it; scope it per user instead.
    if not request.session_id or request.session_id == "default_session":
        request.session_id = f"mcp_{current_user_id(current_user)}"[:64]
    with get_sync_session() as db:
        claim_session(db, request.session_id, current_user)
    arguments = dict(request.arguments)
    if "session_id" in arguments:
        arguments["session_id"] = request.session_id
    response = mcp_gateway.execute_tool(
        tool_name=request.tool_name,
        arguments=arguments,
        session_id=request.session_id,
        network_mode=None,
    )
    return response


@router.get("/history")
def get_mcp_history(limit: int = Query(default=50, ge=1, le=200), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetches recent MCP tool invocation telemetry and audit logs."""
    try:
        with get_sync_session() as session:
            q = session.query(MCPToolCall)
            if not is_admin(current_user):
                owned = session.query(Conversation.conversation_id).filter(
                    Conversation.user_id == current_user_id(current_user))
                q = q.filter(MCPToolCall.session_id.in_(owned))
            calls = q.order_by(MCPToolCall.id.desc()).limit(limit).all()
            return {"total": len(calls), "history": [c.to_dict() for c in calls]}
    except Exception as e:
        logger.error(f"Error fetching MCP history: {e}")
        return {"total": 0, "history": []}
