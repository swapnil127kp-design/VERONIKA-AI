"""
Tests for the sub-agent swarm coordinator.
"""
import time

import pytest

from ai.swarm_coordinator import SwarmCoordinator, SwarmTask, SwarmResult
from mcp.rea_bridge import ReaResult


class FakeAgent:
    def __init__(self, result=None, error=None, delay=0.0):
        self._result = result
        self._error = error
        self._delay = delay
        self.goals = []

    def run(self, goal, context=None):
        self.goals.append(goal)
        if self._delay:
            time.sleep(self._delay)
        if self._error:
            raise RuntimeError(self._error)
        return self._result


def ok_agent_factory(answer_prefix="ans"):
    def factory(goal, depth):
        return FakeAgent(ReaResult(goal=goal, success=True, final_answer=f"{answer_prefix}:{goal}"))
    return factory


def test_run_multiple_goals_parallel():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.run(["task A", "task B", "task C"])
    assert result.success is True
    assert len(result.tasks) == 3
    assert "ans:task A" in result.summary
    assert "ans:task C" in result.summary


def test_run_empty_goals():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.run([])
    assert result.success is False
    assert "No goals" in result.summary


def test_run_filters_blank_goals():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.run(["  ", "", "real"])
    assert len(result.tasks) == 1
    assert result.success is True


def test_failing_agent_marks_task_failed():
    def factory(goal, depth):
        if goal == "bad":
            return FakeAgent(error="kaboom")
        return FakeAgent(ReaResult(goal=goal, success=True, final_answer="good"))

    swarm = SwarmCoordinator(agent_factory=factory)
    result = swarm.run(["bad", "good"])
    assert result.success is False
    statuses = {t.goal: t.status for t in result.tasks}
    assert statuses["bad"] == "failed"
    assert statuses["good"] == "done"


def test_agent_returning_failure_result():
    def factory(goal, depth):
        return FakeAgent(ReaResult(goal=goal, success=False, error="no luck"))

    swarm = SwarmCoordinator(agent_factory=factory)
    result = swarm.run(["x"])
    assert result.success is False
    assert result.tasks[0].status == "failed"
    assert result.tasks[0].error == "no luck"


def test_spawn_and_status():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    task = swarm.spawn("single")
    assert isinstance(task, SwarmTask)
    assert swarm.get_task(task.task_id) is task
    # wait for the future to complete
    time.sleep(0.2)
    assert swarm.get_task(task.task_id).status == "done"
    st = swarm.status()
    assert st["total"] == 1
    assert st["workers"] >= 1


def test_decompose_and_run_uses_planner():
    class Planner:
        def decompose(self, goal):
            return ["sub1", "sub2"]

    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.decompose_and_run("big goal", planner=Planner())
    goals = sorted(t.goal for t in result.tasks)
    assert goals == ["sub1", "sub2"]


def test_decompose_and_run_falls_back_on_planner_error():
    class BadPlanner:
        def decompose(self, goal):
            raise RuntimeError("no plan")

    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.decompose_and_run("solo", planner=BadPlanner())
    assert [t.goal for t in result.tasks] == ["solo"]


def test_shutdown_blocks_new_spawn():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    swarm.shutdown()
    with pytest.raises(RuntimeError):
        swarm.spawn("nope")


def test_result_to_dict():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    result = swarm.run(["a"])
    data = result.to_dict()
    assert data["success"] is True
    assert data["tasks"][0]["goal"] == "a"
    assert data["tasks"][0]["answer"] == "ans:a"


def test_summarize_marks_statuses():
    swarm = SwarmCoordinator(agent_factory=ok_agent_factory())
    tasks = [
        SwarmTask(task_id="1", goal="g1", status="done", result={"final_answer": "a"}),
        SwarmTask(task_id="2", goal="g2", status="failed", error="e"),
    ]
    result = swarm._summarize(tasks)
    assert result.success is False
    assert "[OK] g1 -> a" in result.summary
    assert "[FAIL] g2 -> e" in result.summary
