import os
import yaml
import logging
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


class PolicyDecision(BaseModel):
    """Encapsulates the decision rendered by the MCP Policy Engine."""
    is_allowed: bool
    reason: str
    tool_name: str
    category: str
    required_mode: str
    timeout_sec: float
    max_calls: int


class MCPPolicyEngine:
    """
    Layer 2 MCP Policy Engine (Phase 08).
    Evaluates tool invocation permissions against:
    - Tool category allowlists (`mcp_permissions.yaml`).
    - Network mode enforcement (OFFLINE mode strictly blocks ONLINE tools).
    - Per-request tool invocation budgets.
    - Explicit server/tool deny lists.
    """

    def __init__(self, permissions_path: Optional[str] = None):
        self.permissions_path = permissions_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "mcp_permissions.yaml"
        )
        self._policy_data = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        if os.path.exists(self.permissions_path):
            try:
                with open(self.permissions_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load mcp_permissions.yaml: {e}")
        return {}

    def reload(self) -> None:
        self._policy_data = self._load_policy()

    def evaluate(
        self,
        tool_name: str,
        current_mode: Optional[str] = None,
        call_count_in_request: int = 0
    ) -> PolicyDecision:
        """
        Evaluates whether a tool call is permitted.
        
        Args:
            tool_name: Name of tool being invoked.
            current_mode: "OFFLINE" or "ONLINE" (defaults to settings.network_mode.default_mode).
            call_count_in_request: Number of tool calls already executed in the current request.
        """
        if not current_mode:
            from app.network.mode_enforcer import mode_enforcer
            mode = mode_enforcer.get_mode().upper()
        else:
            mode = current_mode.upper()
        global_cfg = self._policy_data.get("global", {})
        categories = self._policy_data.get("categories", {})
        servers = self._policy_data.get("servers", {})

        # 1. Global MCP Kill-switch check
        if not global_cfg.get("enabled", True):
            return PolicyDecision(
                is_allowed=False,
                reason="MCP subsystem is globally disabled via configuration policy.",
                tool_name=tool_name,
                category="UNKNOWN",
                required_mode="NONE",
                timeout_sec=0.0,
                max_calls=0
            )

        # 2. Match tool to registered category
        target_category = None
        category_config = None

        for cat_name, cat_data in categories.items():
            if tool_name in cat_data.get("allowed_tools", []):
                target_category = cat_name
                category_config = cat_data
                break

        # Check server allowlists if not in categories
        if not target_category:
            for srv_name, srv_data in servers.items():
                if not srv_data.get("enabled", True):
                    continue
                if tool_name in srv_data.get("denied_tools", []):
                    return PolicyDecision(
                        is_allowed=False,
                        reason=f"Tool '{tool_name}' is explicitly denied by server policy for '{srv_name}'.",
                        tool_name=tool_name,
                        category="SERVER_DENIED",
                        required_mode="NONE",
                        timeout_sec=0.0,
                        max_calls=0
                    )
                if tool_name in srv_data.get("allowed_tools", []):
                    target_category = "EXTERNAL_MCP"
                    category_config = {
                        "required_mode": "OFFLINE",
                        "max_calls_per_request": 5,
                        "timeout_sec": 10.0
                    }
                    break

        if not target_category or not category_config:
            return PolicyDecision(
                is_allowed=False,
                reason=f"Tool '{tool_name}' is not in the authorized MCP permission allowlist.",
                tool_name=tool_name,
                category="UNAUTHORIZED",
                required_mode="NONE",
                timeout_sec=0.0,
                max_calls=0
            )

        required_mode = category_config.get("required_mode", "OFFLINE").upper()
        max_calls = category_config.get("max_calls_per_request", global_cfg.get("max_calls_per_request", 10))
        timeout_sec = category_config.get("timeout_sec", global_cfg.get("default_timeout_sec", 10.0))

        # 3. Enforce Network Mode
        if required_mode == "ONLINE" and mode == "OFFLINE":
            return PolicyDecision(
                is_allowed=False,
                reason=f"Tool '{tool_name}' requires ONLINE mode (current system network mode is OFFLINE).",
                tool_name=tool_name,
                category=target_category,
                required_mode=required_mode,
                timeout_sec=timeout_sec,
                max_calls=max_calls
            )

        # 4. Enforce Request Call Budget
        if call_count_in_request >= max_calls:
            return PolicyDecision(
                is_allowed=False,
                reason=f"Request tool quota exceeded: '{tool_name}' allows maximum {max_calls} calls per request (attempted call #{call_count_in_request + 1}).",
                tool_name=tool_name,
                category=target_category,
                required_mode=required_mode,
                timeout_sec=timeout_sec,
                max_calls=max_calls
            )

        # Approved
        return PolicyDecision(
            is_allowed=True,
            reason="Approved by MCP Policy Engine.",
            tool_name=tool_name,
            category=target_category,
            required_mode=required_mode,
            timeout_sec=timeout_sec,
            max_calls=max_calls
        )


policy_engine = MCPPolicyEngine()
