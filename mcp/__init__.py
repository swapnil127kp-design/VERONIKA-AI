"""
VERONIKA AI - MCP (Model Context Protocol) subsystem.

  - mcp_client : connect to MCP servers, discover and call their tools.
  - rea_bridge : unified Reasoning, Execution & Action agent loop that uses
                 those tools (plus the ActionRegistry) autonomously.
"""
from mcp.mcp_client import (
    MCPClient,
    MCPManager,
    MCPTool,
    MCPServerConfig,
    MCPError,
    extract_text,
    build_mcp_manager,
    load_servers_from_config,
)
from mcp.rea_bridge import ReaBridge, ReaResult, ReaStep

__all__ = [
    "MCPClient",
    "MCPManager",
    "MCPTool",
    "MCPServerConfig",
    "MCPError",
    "extract_text",
    "build_mcp_manager",
    "load_servers_from_config",
    "ReaBridge",
    "ReaResult",
    "ReaStep",
]
