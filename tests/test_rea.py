"""
Tests for the REA (Reasoning, Execution & Action) bridge.
"""
from automation.action_registry import ActionResult
from ai.provider_base import AIResponse
from mcp.rea_bridge import ReaBridge, ReaResult, ReaStep


# ── Test doubles ─────────────────────────────────────────────

class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    def send_message(self, user_message, **kwargs):
        self.prompts.append(user_message)
        if self._responses:
            content = self._responses.pop(0)
        else:
            content = '{"final_answer": "default done"}'
        return AIResponse(content=content)


class FakeRegistry:
    def __init__(self, available=None):
        self._available = list(available or ["calculate", "run_shell"])
        self.executed = []

    def get_available_actions(self):
        return list(self._available)

    def execute(self, action, args=None):
        self.executed.append((action, args))
        return ActionResult(True, f"ran:{action}")


class FakeMCP:
    def __init__(self, tools):
        self.tools = dict(tools)
        self.called = []

    def list_tool_dicts(self):
        return [{"name": n, "description": d, "input_schema": {}} for n, d in self.tools.items()]

    def has_tool(self, name):
        return name in self.tools

    def call(self, name, args=None):
        self.called.append((name, args))
        return {"content": [{"type": "text", "text": f"mcp-result:{name}"}]}


class StubAgent:
    def __init__(self, result):
        self._result = result

    def run(self, goal, context=None):
        return self._result


# ── Tests ────────────────────────────────────────────────────

def test_run_reaches_final_answer_after_action():
    provider = FakeProvider([
        '{"thought": "need math", "action": "calculate", "action_input": {"expression": "2+2"}}',
        '{"thought": "done", "final_answer": "The answer is 4"}',
    ])
    registry = FakeRegistry()
    rea = ReaBridge(provider_manager=provider, action_registry=registry)

    result = rea.run("What is 2+2?")

    assert result.success is True
    assert result.final_answer == "The answer is 4"
    assert result.iterations == 2
    assert len(result.steps) == 2
    assert result.steps[0].action == "calculate"
    assert result.steps[0].observation == "ran:calculate"
    assert result.steps[1].is_final is True
    assert registry.executed == [("calculate", {"expression": "2+2"})]


def test_run_returns_error_when_max_iterations_exhausted():
    provider = FakeProvider([
        '{"thought": "again", "action": "calculate", "action_input": {}}',
        '{"thought": "again", "action": "calculate", "action_input": {}}',
    ])
    rea = ReaBridge(provider_manager=provider, action_registry=FakeRegistry(), max_iterations=2)
    result = rea.run("loop forever")

    assert result.success is False
    assert "max iterations" in result.error.lower()
    assert result.iterations == 2


def test_run_empty_goal():
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=FakeRegistry())
    result = rea.run("   ")
    assert result.success is False
    assert result.error == "Empty goal."


def test_provider_error_is_surfaced():
    class ErrorProvider:
        def send_message(self, user_message, **kwargs):
            return AIResponse(content="", error="boom")

    rea = ReaBridge(provider_manager=ErrorProvider(), action_registry=FakeRegistry())
    result = rea.run("do it")
    assert result.success is False
    assert "boom" in result.error


def test_prose_response_is_treated_as_final_answer():
    provider = FakeProvider(["Hello Swapnil sir, kaise ho?"])
    rea = ReaBridge(provider_manager=provider, action_registry=FakeRegistry())
    result = rea.run("hi")
    assert result.success is True
    assert result.final_answer == "Hello Swapnil sir, kaise ho?"


def test_action_without_executor_reports_failure():
    provider = FakeProvider([
        '{"thought": "x", "action": "nonexistent", "action_input": {}}',
        '{"thought": "give up", "final_answer": "could not"}',
    ])
    rea = ReaBridge(provider_manager=provider, action_registry=None)
    result = rea.run("do unknown")
    assert result.steps[0].success is False
    assert "No executor" in result.steps[0].observation


def test_mcp_tool_dispatch():
    provider = FakeProvider([
        '{"thought": "use mcp", "action": "mcp__alpha__echo", "action_input": {"text": "hi"}}',
        '{"thought": "done", "final_answer": "ok"}',
    ])
    mcp = FakeMCP({"mcp__alpha__echo": "Echo"})
    rea = ReaBridge(provider_manager=provider, action_registry=None, mcp_manager=mcp)
    result = rea.run("echo hi")
    assert result.steps[0].observation == "mcp-result:mcp__alpha__echo"
    assert mcp.called == [("mcp__alpha__echo", {"text": "hi"})]


def test_available_actions_merges_registry_and_mcp():
    mcp = FakeMCP({"mcp__alpha__echo": "Echo"})
    rea = ReaBridge(
        provider_manager=FakeProvider([]),
        action_registry=FakeRegistry(["calculate"]),
        mcp_manager=mcp,
    )
    actions = rea.available_actions()
    assert "calculate" in actions
    assert "mcp__alpha__echo" in actions


def test_decompose_returns_subgoals():
    provider = FakeProvider(['{"sub_goals": ["step one", "step two"]}'])
    rea = ReaBridge(provider_manager=provider, action_registry=FakeRegistry())
    assert rea.decompose("big goal") == ["step one", "step two"]


def test_decompose_falls_back_on_error():
    class ErrorProvider:
        def send_message(self, user_message, **kwargs):
            return AIResponse(content="", error="nope")

    rea = ReaBridge(provider_manager=ErrorProvider(), action_registry=FakeRegistry())
    assert rea.decompose("big goal") == ["big goal"]


def test_decompose_empty_goal():
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=FakeRegistry())
    assert rea.decompose("") == []


def test_spawn_sub_agent_uses_factory():
    stub = StubAgent(ReaResult(goal="sub", success=True, final_answer="sub result"))
    provider = FakeProvider([
        '{"thought": "delegate", "action": "spawn_sub_agent", "action_input": {"goal": "sub task"}}',
        '{"thought": "done", "final_answer": "combined"}',
    ])
    rea = ReaBridge(
        provider_manager=provider,
        action_registry=FakeRegistry(),
        sub_agent_factory=lambda goal, depth=1: stub,
    )
    result = rea.run("big task")
    assert "[sub-agent] sub result" in result.steps[0].observation
    assert result.success is True


def test_spawn_sub_agent_depth_guard():
    provider = FakeProvider([
        '{"thought": "delegate", "action": "spawn_sub_agent", "action_input": {"goal": "sub"}}',
        '{"thought": "done", "final_answer": "ok"}',
    ])
    rea = ReaBridge(
        provider_manager=provider,
        action_registry=FakeRegistry(),
        depth=3,
        max_depth=3,
    )
    result = rea.run("task")
    assert "Max sub-agent depth" in result.steps[0].observation


def test_spawn_sub_agent_requires_goal():
    provider = FakeProvider([
        '{"thought": "delegate", "action": "spawn_sub_agent", "action_input": {}}',
        '{"thought": "done", "final_answer": "ok"}',
    ])
    rea = ReaBridge(provider_manager=provider, action_registry=FakeRegistry())
    result = rea.run("task")
    assert "requires a 'goal'" in result.steps[0].observation


def test_execute_remote_dispatches_to_registry():
    registry = FakeRegistry()
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=registry)
    out = rea.execute_remote("calculate", {"expression": "1+1"})
    assert out["success"] is True
    assert out["message"] == "ran:calculate"
    assert registry.executed == [("calculate", {"expression": "1+1"})]


def test_handle_remote_request_with_action():
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=FakeRegistry())
    out = rea.handle_remote_request({"action": "calculate", "args": {"expression": "1"}})
    assert out["success"] is True


def test_handle_remote_request_with_goal():
    provider = FakeProvider(['{"thought": "t", "final_answer": "remote done"}'])
    rea = ReaBridge(provider_manager=provider, action_registry=FakeRegistry())
    out = rea.handle_remote_request({"goal": "do remote"})
    assert out["success"] is True
    assert out["final_answer"] == "remote done"


def test_handle_remote_request_without_input():
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=FakeRegistry())
    out = rea.handle_remote_request({})
    assert out["success"] is False
    assert "Provide 'action' or 'goal'" in out["message"]


def test_describe_reports_sub_agent_availability():
    rea = ReaBridge(provider_manager=FakeProvider([]), action_registry=FakeRegistry(), depth=0, max_depth=3)
    info = rea.describe()
    assert info["sub_agents"] is True
    assert info["max_iterations"] == 8


def test_extract_json_variants():
    assert ReaBridge._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ReaBridge._extract_json('prefix {"b": 2} suffix') == {"b": 2}
    assert ReaBridge._extract_json('no json here') == {}
    assert ReaBridge._extract_json('') == {}


def test_result_transcript_and_to_dict():
    result = ReaResult(goal="g", success=True, final_answer="a")
    result.steps.append(ReaStep(index=1, thought="t", action="calculate",
                                action_args={"x": 1}, observation="o"))
    text = result.transcript
    assert "Thought: t" in text
    assert "Action: calculate" in text
    assert result.to_dict()["steps"][0]["action"] == "calculate"
