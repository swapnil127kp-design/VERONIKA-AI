"""
VERONIKA AI - MCP (Model Context Protocol) Client

Connects to local or remote MCP servers, performs the JSON-RPC 2.0 handshake,
discovers the tools each server exposes, and makes them callable -- both
directly and (later) through the REA bridge / ActionRegistry.

Supported transports:
  - stdio : spawn a server subprocess and speak newline-delimited JSON-RPC
            over its stdin/stdout (the common local MCP transport).
  - http  : streamable-HTTP JSON-RPC (POST a JSON-RPC request, accept a plain
            JSON body or a `text/event-stream` SSE reply).

Nothing here mutates existing application behaviour -- it is purely additive.
"""
import json
import logging
import os
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Protocol revision we advertise during initialize.
MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "veronika-ai", "version": "1.0.0"}

# Windows: hide the console window when spawning stdio MCP servers.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class MCPError(Exception):
    """Raised when an MCP server returns an error or the connection fails."""


# ═══════════════════════════════════════════════════════════════
# Configuration + data models
# ═══════════════════════════════════════════════════════════════

@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    name: str
    transport: str = "stdio"           # "stdio" | "http"
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    enabled: bool = True
    timeout: int = 30

    @classmethod
    def from_dict(cls, name: str, data: Optional[dict]) -> "MCPServerConfig":
        data = data or {}
        return cls(
            name=name,
            transport=(data.get("transport") or "stdio").lower(),
            command=data.get("command", ""),
            args=list(data.get("args", []) or []),
            env=dict(data.get("env", {}) or {}),
            url=data.get("url", ""),
            enabled=bool(data.get("enabled", True)),
            timeout=int(data.get("timeout", 30)),
        )


@dataclass
class MCPTool:
    """A tool advertised by an MCP server."""
    server: str
    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"mcp__{self.server}__{self.name}"

    def to_dict(self) -> dict:
        return {
            "name": self.full_name,
            "server": self.server,
            "tool": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def extract_text(result: dict) -> str:
    """Flatten an MCP tools/call result's content blocks into plain text."""
    if not isinstance(result, dict):
        return str(result)
    parts: List[str] = []
    for block in result.get("content", []) or []:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue
        btype = block.get("type")
        if btype == "text":
            parts.append(str(block.get("text", "")))
        elif btype == "resource":
            res = block.get("resource", {}) or {}
            parts.append(str(res.get("text") or res.get("uri") or ""))
        elif btype == "image":
            parts.append("[image]")
        else:
            parts.append(str(block.get("text", "")))
    if not parts and "structuredContent" in result:
        return json.dumps(result["structuredContent"], ensure_ascii=False)
    return "\n".join(p for p in parts if p).strip()


# ═══════════════════════════════════════════════════════════════
# Transports
# ═══════════════════════════════════════════════════════════════

class _StdioTransport:
    """Newline-delimited JSON-RPC over a child process' stdin/stdout."""

    def __init__(self, cfg: MCPServerConfig):
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None

    def open(self):
        if not self.cfg.command:
            raise MCPError(f"MCP server '{self.cfg.name}' has no command")
        env = os.environ.copy()
        env.update(self.cfg.env or {})
        try:
            self._proc = subprocess.Popen(
                [self.cfg.command, *self.cfg.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as e:
            raise MCPError(f"Failed to launch MCP server '{self.cfg.name}': {e}")

    def send(self, payload: dict, expect_response: bool) -> Optional[dict]:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise MCPError("MCP stdio transport is not open")
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPError(f"MCP server '{self.cfg.name}' closed the pipe: {e}")

        if not expect_response:
            return None

        rid = payload.get("id")
        while True:
            raw = self._proc.stdout.readline()
            if not raw:
                raise MCPError(f"MCP server '{self.cfg.name}' closed the connection")
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  # ignore non-JSON log lines
            if msg.get("id") != rid:
                continue  # notification or unrelated message
            if "error" in msg:
                raise MCPError(str(msg["error"]))
            return msg.get("result", {})

    def close(self):
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class _HttpTransport:
    """Streamable-HTTP JSON-RPC transport."""

    def __init__(self, cfg: MCPServerConfig):
        self.cfg = cfg

    def open(self):
        if not self.cfg.url:
            raise MCPError(f"MCP server '{self.cfg.name}' has no url")

    def send(self, payload: dict, expect_response: bool) -> Optional[dict]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        token = (self.cfg.env or {}).get("MCP_AUTH_TOKEN") or os.environ.get("MCP_AUTH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(self.cfg.url, data=body, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise MCPError(f"MCP HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise MCPError(f"MCP HTTP connection failed: {e.reason}")

        if not expect_response:
            return None
        return self._parse(raw, payload.get("id"))

    @staticmethod
    def _parse(raw: str, rid) -> dict:
        raw = (raw or "").strip()
        if not raw:
            return {}
        # SSE framing?
        if raw.startswith("event:") or "data:" in raw[:16]:
            for line in raw.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    msg = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == rid:
                    if "error" in msg:
                        raise MCPError(str(msg["error"]))
                    return msg.get("result", {})
            return {}
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            raise MCPError(f"Invalid JSON from MCP server: {e}")
        if "error" in msg:
            raise MCPError(str(msg["error"]))
        return msg.get("result", {})


def _default_transport_factory(cfg: MCPServerConfig):
    if cfg.transport == "http":
        return _HttpTransport(cfg)
    if cfg.transport == "stdio":
        return _StdioTransport(cfg)
    raise MCPError(f"Unsupported MCP transport: {cfg.transport}")


# ═══════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════

class MCPClient:
    """A JSON-RPC client for a single MCP server."""

    def __init__(
        self,
        cfg: MCPServerConfig,
        transport_factory: Optional[Callable[[MCPServerConfig], object]] = None,
    ):
        self.cfg = cfg
        self._transport = None
        self._transport_factory = transport_factory or _default_transport_factory
        self._tools: List[MCPTool] = []
        self._counter = 0
        self._lock = threading.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def tools(self) -> List[MCPTool]:
        return list(self._tools)

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _request(self, method: str, params: Optional[dict] = None) -> dict:
        with self._lock:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params or {},
            }
            return self._transport.send(payload, True) or {}

    def _notify(self, method: str, params: Optional[dict] = None):
        with self._lock:
            payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
            self._transport.send(payload, False)

    def connect(self) -> "MCPClient":
        if self._connected:
            return self
        self._transport = self._transport_factory(self.cfg)
        self._transport.open()
        self._request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": _CLIENT_INFO,
        })
        self._notify("notifications/initialized", {})
        self._connected = True
        logger.info("MCP connected: %s (%s)", self.cfg.name, self.cfg.transport)
        return self

    def list_tools(self) -> List[MCPTool]:
        if not self._connected:
            self.connect()
        result = self._request("tools/list", {})
        tools: List[MCPTool] = []
        for t in (result.get("tools", []) or []):
            name = t.get("name", "")
            if not name:
                continue
            tools.append(MCPTool(
                server=self.cfg.name,
                name=name,
                description=t.get("description", "") or "",
                input_schema=t.get("inputSchema", {}) or {},
            ))
        self._tools = tools
        return list(tools)

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> dict:
        if not self._connected:
            self.connect()
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self):
        try:
            if self._transport is not None:
                self._transport.close()
        finally:
            self._connected = False
            self._transport = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()


# ═══════════════════════════════════════════════════════════════
# Manager (aggregates several servers)
# ═══════════════════════════════════════════════════════════════

def build_mcp_manager(start: bool = True) -> Optional["MCPManager"]:
    """Create (and optionally connect) an MCPManager from app config.

    Returns None when MCP is disabled, so callers can pass the result straight
    into ActionRegistry/ReaBridge without extra guards.
    """
    from app.config import config
    if not config.get("mcp", "enabled", False):
        return None
    manager = MCPManager()
    if start:
        manager.start()
    return manager


def load_servers_from_config(config_section: Optional[dict] = None) -> Dict[str, MCPServerConfig]:
    """Read MCP server definitions from the app config (or an explicit dict)."""
    if config_section is None:
        from app.config import config
        config_section = config.get_section("mcp")
    servers_raw = (config_section or {}).get("servers", {}) or {}
    return {
        name: MCPServerConfig.from_dict(name, data)
        for name, data in servers_raw.items()
    }


class MCPManager:
    """Owns connections to every configured MCP server and routes tool calls."""

    def __init__(
        self,
        servers: Optional[Dict[str, MCPServerConfig]] = None,
        transport_factory: Optional[Callable[[MCPServerConfig], object]] = None,
    ):
        if servers is None:
            servers = load_servers_from_config()
        self._configs: Dict[str, MCPServerConfig] = {}
        for name, cfg in servers.items():
            self._configs[name] = cfg if isinstance(cfg, MCPServerConfig) else MCPServerConfig.from_dict(name, cfg)
        self._transport_factory = transport_factory
        self._clients: Dict[str, MCPClient] = {}
        self._tools_by_full: Dict[str, Tuple[MCPClient, MCPTool]] = {}
        self._errors: Dict[str, str] = {}

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> "MCPManager":
        for name, cfg in self._configs.items():
            if not cfg.enabled:
                continue
            try:
                client = MCPClient(cfg, transport_factory=self._transport_factory)
                client.connect()
                client.list_tools()
                self._clients[name] = client
            except Exception as e:  # noqa: BLE001 - keep one bad server from killing startup
                self._errors[name] = str(e)
                logger.warning("MCP server '%s' unavailable: %s", name, e)
        self._rebuild_index()
        return self

    def stop(self):
        for client in self._clients.values():
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()
        self._tools_by_full.clear()

    def _rebuild_index(self):
        self._tools_by_full = {}
        for client in self._clients.values():
            for tool in client.tools:
                self._tools_by_full[tool.full_name] = (client, tool)

    # ── Introspection ─────────────────────────────────────────

    @property
    def connected_servers(self) -> List[str]:
        return list(self._clients.keys())

    def get_tools(self) -> List[MCPTool]:
        return [tool for _, tool in self._tools_by_full.values()]

    def list_tool_dicts(self) -> List[dict]:
        return [tool.to_dict() for _, tool in self._tools_by_full.values()]

    def has_tool(self, full_name: str) -> bool:
        return full_name in self._tools_by_full

    def get_status(self) -> dict:
        return {
            "connected": self.connected_servers,
            "errors": dict(self._errors),
            "tool_count": len(self._tools_by_full),
        }

    # ── Execution ─────────────────────────────────────────────

    def call(self, full_name: str, arguments: Optional[dict] = None) -> dict:
        entry = self._tools_by_full.get(full_name)
        if not entry:
            raise MCPError(f"Unknown MCP tool: {full_name}")
        client, tool = entry
        return client.call_tool(tool.name, arguments)

    def as_actions(self, wrap: Optional[Callable[[str, bool, str, dict], object]] = None) -> Dict[str, Callable]:
        """Expose each MCP tool as a `**kwargs -> result` callable.

        `wrap(full_name, success, text, raw)` (if given) converts a raw call
        into a custom result object (e.g. ActionRegistry.ActionResult).
        """
        actions: Dict[str, Callable] = {}
        for full_name, (client, tool) in self._tools_by_full.items():
            actions[full_name] = self._make_action(full_name, tool, wrap)
        return actions

    def _make_action(self, full_name: str, tool: MCPTool, wrap) -> Callable:
        def _action(**kwargs):
            try:
                raw = self.call(full_name, kwargs)
                text = extract_text(raw)
                if wrap:
                    return wrap(full_name, True, text, raw)
                return {"success": True, "message": text, "data": raw}
            except Exception as e:  # noqa: BLE001
                if wrap:
                    return wrap(full_name, False, str(e), {})
                return {"success": False, "message": str(e), "data": {}}
        _action.__name__ = full_name
        return _action
