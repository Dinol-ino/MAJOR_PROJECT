import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MCP_SERVERS_CONFIG: Dict[str, Dict[str, Any]] = {
    "ansvar-systems-india-law-mcp": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/server-india-law"],
        "capabilities": ["full_text_search", "get_section", "statute_currency_check"],
        "description": "India Code central acts: DPDPA 2023, IT Act, Companies Act, Consumer Protection Act",
        "domain": "cyber/corporate",
        "default_enabled": True,
        "env": {}
    },
    "themis-mcp": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/themis-india-law"],
        "capabilities": ["section_lookup", "offence_search", "old_new_mapping"],
        "description": "BNS, BNSS, BSA, IPC (old -> new criminal code mapping & cross-walk)",
        "domain": "criminal",
        "default_enabled": True,
        "env": {}
    },
    "nyaya-mcp": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/nyaya-mcp"],
        "capabilities": ["case_search", "judgment_retrieve", "constitution_parts"],
        "description": "Constitution of India + landmark Supreme Court judgments",
        "domain": "constitutional",
        "default_enabled": True,
        "env": {}
    },
    "taxbykk-mcp": {
        "transport": "stdio",
        "command": ["npx", "-y", "@modelcontextprotocol/taxbykk-mcp"],
        "capabilities": ["gst_search", "tax_section_cite"],
        "description": "GST, CGST, indirect tax - page-level statutory citations",
        "domain": "tax",
        "default_enabled": True,
        "env": {}
    }
}


class MCPServerInstance:
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get("default_enabled", True)
        self.status = "connecting"  # connected | connecting | error | disabled
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
            self.status = "error"
            self.error_reason = f"Executable '{executable}' not found in system PATH. Install Node.js/npx to activate."
        else:
            self.status = "connected"
            self.error_reason = None
            self.last_ping = time.time()

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
        """Populates canonical tool declarations matching server capabilities."""
        if instance.name == "ansvar-systems-india-law-mcp":
            instance.discovered_tools = [
                {
                    "name": "india_code_full_text_search",
                    "description": "Full text search across India Code central acts including DPDPA 2023, IT Act, Companies Act.",
                    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                },
                {
                    "name": "india_code_get_section",
                    "description": "Fetches exact text and heading for a specific statute section.",
                    "input_schema": {"type": "object", "properties": {"act": {"type": "string"}, "section": {"type": "string"}}, "required": ["act", "section"]}
                },
                {
                    "name": "statute_currency_check",
                    "description": "Verifies whether a statute or section has been amended, substituted, or repealed.",
                    "input_schema": {"type": "object", "properties": {"act": {"type": "string"}, "section": {"type": "string"}}, "required": ["act"]}
                }
            ]
        elif instance.name == "themis-mcp":
            instance.discovered_tools = [
                {
                    "name": "themis_section_lookup",
                    "description": "Direct provision lookup in Bharatiya Nyaya Sanhita (BNS), BNSS, BSA, or legacy IPC.",
                    "input_schema": {"type": "object", "properties": {"code": {"type": "string"}, "section": {"type": "string"}}, "required": ["code", "section"]}
                },
                {
                    "name": "themis_old_new_mapping",
                    "description": "Cross-walk mapping between legacy Indian Penal Code (IPC) and Bharatiya Nyaya Sanhita (BNS 2023).",
                    "input_schema": {"type": "object", "properties": {"ipc_section": {"type": "string"}, "bns_section": {"type": "string"}}}
                }
            ]
        elif instance.name == "nyaya-mcp":
            instance.discovered_tools = [
                {
                    "name": "nyaya_constitution_parts",
                    "description": "Queries provisions, Fundamental Rights, and Articles of the Constitution of India.",
                    "input_schema": {"type": "object", "properties": {"article": {"type": "string"}}, "required": ["article"]}
                },
                {
                    "name": "nyaya_case_search",
                    "description": "Searches landmark Supreme Court of India precedents and constitutional bench judgments.",
                    "input_schema": {"type": "object", "properties": {"keywords": {"type": "string"}}, "required": ["keywords"]}
                }
            ]
        elif instance.name == "taxbykk-mcp":
            instance.discovered_tools = [
                {
                    "name": "taxbykk_gst_search",
                    "description": "Search Goods and Services Tax (GST / CGST) acts, rules, and rate schedules.",
                    "input_schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]}
                },
                {
                    "name": "taxbykk_tax_section_cite",
                    "description": "Retrieves official tax section citations with page-level statutory references.",
                    "input_schema": {"type": "object", "properties": {"section": {"type": "string"}, "act": {"type": "string"}}, "required": ["section"]}
                }
            ]

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
