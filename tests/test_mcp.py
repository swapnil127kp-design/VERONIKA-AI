"""
Tests for the MCP (Model Context Protocol) client subsystem.
"""
import pytest

from mcp.mcp_client import (
    MCPClient,
    MCPManager,
    MCPTool,
    MCPServerConfig,
    MCPError,
    extract_text,
)


# ── Test doubles ─────────────────────────────────────────────

class FakeTransport:
    """In-memory MCP transport that answers initialize / tools/list / tools/call."""

    def __init__(self, cfg, tools=None, fail_open=False):
        self.cfg = cfg
        self.tools = tools or []
        self.fail_open = fail_open
        self.calls = []
        self.opened = False
        self.closed = False

    def open(self):
        if self.fail_open:
            raise MCPError(f"cannot open {self.cfg.name}")
        self.opened = True

    def send(self, payload, expect_response):
        self.calls.append(payload)
        if not expect_response:
            return None
        method = payload.get("method")
        if method == "initialize":
            return {"protocolVersion": "2024-11-05", "serverInfo": {"name": self.cfg.name}}
        if method == "tools/list":
            return {
                "tools": [
                    {"name": n, "description": d, "inputSchema": s}
                    for (n, d, s) in self.tools
                ]
            }
        if method == "tools/call":
            name = payload["params"]["name"]
            return {"content": [{"type": "text", "text": f"called:{name}"}]}
        return {}

    def close(self):
        self.closed = True


def make_factory(tool_map, failing=()):
    created = {}

    def factory(cfg):
        if cfg.name in failing:
            t = FakeTransport(cfg, [], fail_open=True)
        else:
            t = FakeTransport(cfg, tool_map.get(cfg.name, []))
        created[cfg.name] = t
        return t

    return factory, created


# ── Config model ─────────────────────────────────────────────

def test_server_config_from_dict():
    cfg = MCPServerConfig.from_dict("fs", {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "server-filesystem"],
        "env": {"FOO": "bar"},
    })
    assert cfg.name == "fs"
    assert cfg.transport == "stdio"
    assert cfg.command == "npx"
    assert cfg.args == ["-y", "server-filesystem"]
    assert cfg.env == {"FOO": "bar"}
    assert cfg.enabled is True


def test_server_config_from_empty_dict_defaults():
    cfg = MCPServerConfig.from_dict("x", None)
    assert cfg.transport == "stdio"
    assert cfg.enabled is True
    assert cfg.timeout == 30


# ── Client ───────────────────────────────────────────────────

def test_client_connect_sends_initialize_then_notification():
    factory, created = make_factory({"alpha": [("echo", "Echo text", {})]})
    cfg = MCPServerConfig(name="alpha")
    client = MCPClient(cfg, transport_factory=factory)
    client.connect()

    transport = created["alpha"]
    assert transport.opened
    assert client.connected
    methods = [c["method"] for c in transport.calls]
    assert methods[0] == "initialize"
    assert "notifications/initialized" in methods


def test_client_list_tools_builds_full_names():
    factory, _ = make_factory({"alpha": [("echo", "Echo text", {"type": "object"})]})
    client = MCPClient(MCPServerConfig(name="alpha"), transport_factory=factory)
    tools = client.list_tools()
    assert len(tools) == 1
    assert tools[0].full_name == "mcp__alpha__echo"
    assert tools[0].description == "Echo text"
    assert tools[0].input_schema == {"type": "object"}


def test_client_call_tool_returns_content():
    factory, _ = make_factory({"alpha": [("echo", "", {})]})
    client = MCPClient(MCPServerConfig(name="alpha"), transport_factory=factory)
    result = client.call_tool("echo", {"text": "hi"})
    assert result["content"][0]["text"] == "called:echo"


def test_client_close_marks_disconnected():
    factory, created = make_factory({"alpha": []})
    client = MCPClient(MCPServerConfig(name="alpha"), transport_factory=factory)
    client.connect()
    client.close()
    assert not client.connected
    assert created["alpha"].closed


# ── Manager ──────────────────────────────────────────────────

def test_manager_aggregates_tools_from_multiple_servers():
    tool_map = {
        "alpha": [("echo", "Echo", {})],
        "beta": [("read", "Read file", {}), ("write", "Write file", {})],
    }
    factory, _ = make_factory(tool_map)
    mgr = MCPManager(
        servers={
            "alpha": MCPServerConfig(name="alpha"),
            "beta": MCPServerConfig(name="beta"),
        },
        transport_factory=factory,
    ).start()

    assert sorted(mgr.connected_servers) == ["alpha", "beta"]
    names = sorted(t["name"] for t in mgr.list_tool_dicts())
    assert names == ["mcp__alpha__echo", "mcp__beta__read", "mcp__beta__write"]
    assert mgr.has_tool("mcp__beta__write")
    assert not mgr.has_tool("mcp__beta__missing")


def test_manager_records_error_for_failing_server_but_keeps_others():
    tool_map = {"alpha": [("echo", "Echo", {})]}
    factory, _ = make_factory(tool_map, failing=("broken",))
    mgr = MCPManager(
        servers={
            "alpha": MCPServerConfig(name="alpha"),
            "broken": MCPServerConfig(name="broken"),
        },
        transport_factory=factory,
    ).start()

    status = mgr.get_status()
    assert status["connected"] == ["alpha"]
    assert "broken" in status["errors"]
    assert status["tool_count"] == 1


def test_manager_disabled_server_is_skipped():
    factory, created = make_factory({"alpha": [("echo", "", {})]})
    mgr = MCPManager(
        servers={"alpha": MCPServerConfig(name="alpha", enabled=False)},
        transport_factory=factory,
    ).start()
    assert mgr.connected_servers == []
    assert created == {}


def test_manager_call_routes_to_correct_server():
    tool_map = {"alpha": [("echo", "", {})], "beta": [("read", "", {})]}
    factory, _ = make_factory(tool_map)
    mgr = MCPManager(
        servers={
            "alpha": MCPServerConfig(name="alpha"),
            "beta": MCPServerConfig(name="beta"),
        },
        transport_factory=factory,
    ).start()
    result = mgr.call("mcp__beta__read", {"path": "x"})
    assert result["content"][0]["text"] == "called:read"


def test_manager_call_unknown_tool_raises():
    factory, _ = make_factory({})
    mgr = MCPManager(servers={}, transport_factory=factory).start()
    with pytest.raises(MCPError):
        mgr.call("mcp__nope__x", {})


def test_manager_as_actions_returns_callable_results():
    factory, _ = make_factory({"alpha": [("echo", "", {})]})
    mgr = MCPManager(
        servers={"alpha": MCPServerConfig(name="alpha")},
        transport_factory=factory,
    ).start()

    actions = mgr.as_actions()
    assert "mcp__alpha__echo" in actions
    out = actions["mcp__alpha__echo"](text="hi")
    assert out["success"] is True
    assert out["message"] == "called:echo"


def test_manager_as_actions_supports_wrap():
    factory, _ = make_factory({"alpha": [("echo", "", {})]})
    mgr = MCPManager(
        servers={"alpha": MCPServerConfig(name="alpha")},
        transport_factory=factory,
    ).start()

    actions = mgr.as_actions(wrap=lambda name, ok, text, raw: ("W", ok, text))
    assert actions["mcp__alpha__echo"](text="hi") == ("W", True, "called:echo")


def test_manager_stop_clears_state():
    factory, created = make_factory({"alpha": [("echo", "", {})]})
    mgr = MCPManager(
        servers={"alpha": MCPServerConfig(name="alpha")},
        transport_factory=factory,
    ).start()
    mgr.stop()
    assert mgr.connected_servers == []
    assert created["alpha"].closed


# ── extract_text ─────────────────────────────────────────────

def test_extract_text_text_block():
    assert extract_text({"content": [{"type": "text", "text": "hello"}]}) == "hello"


def test_extract_text_multiple_blocks():
    result = {"content": [
        {"type": "text", "text": "line1"},
        {"type": "text", "text": "line2"},
    ]}
    assert extract_text(result) == "line1\nline2"


def test_extract_text_structured_content_fallback():
    out = extract_text({"content": [], "structuredContent": {"ok": True}})
    assert '"ok": true' in out


def test_extract_text_non_dict():
    assert extract_text("plain") == "plain"


def test_tool_to_dict():
    tool = MCPTool(server="s", name="n", description="d", input_schema={"a": 1})
    data = tool.to_dict()
    assert data["name"] == "mcp__s__n"
    assert data["server"] == "s"
    assert data["tool"] == "n"
    assert data["input_schema"] == {"a": 1}
