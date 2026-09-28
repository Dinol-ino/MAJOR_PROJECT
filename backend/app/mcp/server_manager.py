import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def _load_server_config() -> Dict[str, Dict[str, Any]]:
    """External MCP servers come from configuration only (MCP_SERVERS_CONFIG_PATH or app/config/mcp_servers.yaml)."""
    import yaml
    path = os.getenv("MCP_SERVERS_CONFIG_PATH") or os.path.join(os.path.dirname(__file__), "..", "config", "mcp_servers.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        servers = data.get("servers") or {}
        return {str(k): dict(v or {}) for k, v in servers.items()}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.error("MCP server config unreadable (%s); no external servers loaded.", type(exc).__name__)
        return {}


MCP_SERVERS_CONFIG: Dict[str, Dict[str, Any]] = _load_server_config()


class MCPServerInstance:
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = bool(config.get("enabled", config.get("default_enabled", False)))
        self.status = "unavailable"  # configured | unavailable | disabled  (never "connected" without a handshake)
        self.error_reason: Optional[str] = None
        self.last_ping: Optional[float] = None
        self.discovered_tools: List[Dict[str, Any]] = []
        self._process = None

    def check_health(self) -> str:
        if not self.enabled:
            self.status = "disabled"
            self.error_reason = "Administratively disabled"
            return self.status

        # If running in local environment without node/npx installed or in offline mode
        # check if command executable exists
        cmd = self.config.get("command", [])
        executable = cmd[0] if cmd else None
        
        # Verify if executable exists in PATH
        import shutil
        has_exec = shutil.which(executable) if executable else False

        if not has_exec:
            self.status = "unavailable"
            self.error_reason = f"Executable '{executable}' not found."
        else:
            # The executable exists, but no MCP handshake has been performed: report that honestly.
            self.status = "configured"
            self.error_reason = "Not started: no live MCP session has been established."
            self.last_ping = None

        return self.status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.config.get("description", ""),
            "domain": self.config.get("domain", ""),
            "transport": self.config.get("transport", "stdio"),
            "capabilities": self.config.get("capabilities", []),
            "enabled": self.enabled,
            "status": self.status,
            "error_reason": self.error_reason,
            "last_ping": self.last_ping,
            "tools_count": len(self.discovered_tools),
            "tools": [t.get("name") for t in self.discovered_tools]
        }


class MCPServerManager:
    """
    Manages live connections, health monitoring, and auto-discovery for all Indian Legal MCP servers.
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerInstance] = {}
        self._initialize_servers()

    def _initialize_servers(self):
        for name, cfg in MCP_SERVERS_CONFIG.items():
            instance = MCPServerInstance(name, cfg)
            instance.check_health()
            self._register_default_server_tools(instance)
            self._servers[name] = instance

    def _register_default_server_tools(self, instance: MCPServerInstance):
        """Tools are only known after a real MCP handshake; none are invented from server names."""
        instance.discovered_tools = []

    def get_all_servers_status(self) -> List[Dict[str, Any]]:
        result = []
        for server in self._servers.values():
            server.check_health()
            result.append(server.to_dict())
        return result

    def get_server(self, name: str) -> Optional[MCPServerInstance]:
        return self._servers.get(name)

    def reconnect_server(self, name: str) -> Dict[str, Any]:
        server = self._servers.get(name)
        if not server:
            raise KeyError(f"Server '{name}' not found")
        server.status = "connecting"
        server.check_health()
        return server.to_dict()

    def discover_tools(self) -> List[Dict[str, Any]]:
        all_discovered = []
        for server in self._servers.values():
            for tool in server.discovered_tools:
                t = dict(tool)
                t["server"] = server.name
                t["domain"] = server.config.get("domain", "")
                all_discovered.append(t)
        return all_discovered


mcp_server_manager = MCPServerManager()
