"""
VERONIKA AI - Sub-Agent Swarm Coordinator (Phase 3)

VERONIKA's Supreme Host can farm work out to a swarm of REA sub-agents that
reason and act in parallel. This module owns:

  - spawning many sub-agents at once (bounded ThreadPoolExecutor),
  - tracking their task status,
  - aggregating their final answers into one swarm summary,
  - acting as the `sub_agent_factory` for the REA bridge, so a single goal can
    recursively explode into a parallel swarm.

It is intentionally transport-agnostic: it drives REA bridges, which in turn
drive the ActionRegistry + MCP tools.
"""
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════════

@dataclass
class SwarmTask:
    """A single sub-agent task in the swarm."""
    task_id: str
    goal: str
    status: str = "pending"          # pending | running | done | failed
    result: Optional[dict] = None
    error: str = ""

    @property
    def answer(self) -> str:
        if self.result:
            return self.result.get("final_answer") or ""
        return ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status,
            "answer": self.answer,
            "error": self.error,
        }


@dataclass
class SwarmResult:
    """Aggregated outcome of a swarm run."""
    tasks: List[SwarmTask] = field(default_factory=list)
    success: bool = False
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "summary": self.summary,
            "tasks": [t.to_dict() for t in self.tasks],
        }


# ═══════════════════════════════════════════════════════════════
# Coordinator
# ═══════════════════════════════════════════════════════════════

class SwarmCoordinator:
    """Runs a parallel swarm of REA sub-agents and aggregates their answers."""

    def __init__(
        self,
        provider_manager=None,
        action_registry=None,
        mcp_manager=None,
        max_workers: int = 4,
        max_iterations: int = 6,
        max_depth: int = 2,
        agent_factory: Optional[Callable[[str, int], object]] = None,
    ):
        self.provider_manager = provider_manager
        self.action_registry = action_registry
        self.mcp_manager = mcp_manager
        self.max_workers = max(1, int(max_workers))
        self.max_iterations = max(1, int(max_iterations))
        self.max_depth = max(0, int(max_depth))
        self._agent_factory = agent_factory

        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="rea-swarm"
        )
        self._tasks: Dict[str, SwarmTask] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._closed = False

    # ── Agent factory (also the REA sub_agent_factory hook) ───

    def make_agent(self, goal: str, depth: int = 1):
        """Create a REA agent for a sub-goal. Overridable via agent_factory."""
        if self._agent_factory is not None:
            return self._agent_factory(goal, depth)
        from mcp.rea_bridge import ReaBridge
        return ReaBridge(
            provider_manager=self.provider_manager,
            action_registry=self.action_registry,
            mcp_manager=self.mcp_manager,
            max_iterations=self.max_iterations,
            depth=depth,
            max_depth=self.max_depth,
            sub_agent_factory=self.make_agent,
        )

    # ── Task lifecycle ────────────────────────────────────────

    def _new_task_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"swarm-{self._counter}"

    def spawn(self, goal: str, context: Optional[List[dict]] = None) -> SwarmTask:
        """Queue a sub-agent to run the given goal asynchronously."""
        if self._closed:
            raise RuntimeError("SwarmCoordinator is shut down")
        task = SwarmTask(task_id=self._new_task_id(), goal=goal)
        with self._lock:
            self._tasks[task.task_id] = task
            self._futures[task.task_id] = self._executor.submit(self._run_task, task, context)
        return task

    def _run_task(self, task: SwarmTask, context: Optional[List[dict]]):
        task.status = "running"
        try:
            agent = self.make_agent(task.goal, depth=1)
            outcome = agent.run(task.goal, context=context) if hasattr(agent, "run") else agent(task.goal)
            if hasattr(outcome, "to_dict"):
                task.result = outcome.to_dict()
                task.status = "done" if getattr(outcome, "success", False) else "failed"
                task.error = getattr(outcome, "error", "") or ""
            else:
                task.result = {"final_answer": str(outcome)}
                task.status = "done"
        except Exception as e:  # noqa: BLE001
            task.status = "failed"
            task.error = str(e)
            logger.warning("Swarm task %s failed: %s", task.task_id, e)
        return task

    def run(self, goals: List[str], context: Optional[List[dict]] = None) -> SwarmResult:
        """Run all goals in parallel and block until every sub-agent finishes."""
        goals = [g for g in (goals or []) if g and str(g).strip()]
        if not goals:
            return SwarmResult(tasks=[], success=False, summary="No goals provided.")

        tasks = [self.spawn(g, context) for g in goals]
        futures = [self._futures[t.task_id] for t in tasks]
        wait(futures)
        return self._summarize(tasks)

    def run_and_wait(self, goal: str, context: Optional[List[dict]] = None) -> SwarmResult:
        """Convenience: one goal -> one sub-agent -> SwarmResult."""
        return self.run([goal], context=context)

    def decompose_and_run(
        self,
        goal: str,
        planner=None,
        context: Optional[List[dict]] = None,
    ) -> SwarmResult:
        """Use a REA planner to break a goal into sub-goals, then swarm them."""
        planner = planner or self.make_agent(goal, depth=0)
        try:
            sub_goals = planner.decompose(goal) if hasattr(planner, "decompose") else [goal]
        except Exception as e:  # noqa: BLE001
            logger.debug("Planner decomposition failed: %s", e)
            sub_goals = [goal]
        if not sub_goals:
            sub_goals = [goal]
        return self.run(sub_goals, context=context)

    # ── Introspection ─────────────────────────────────────────

    def _summarize(self, tasks: List[SwarmTask]) -> SwarmResult:
        success = all(t.status == "done" for t in tasks) and bool(tasks)
        lines = []
        for t in tasks:
            marker = {"done": "OK", "failed": "FAIL", "running": "...", "pending": "..."}[t.status]
            lines.append(f"[{marker}] {t.goal} -> {t.answer or t.error or '(no answer)'}")
        return SwarmResult(tasks=list(tasks), success=success, summary="\n".join(lines))

    def get_task(self, task_id: str) -> Optional[SwarmTask]:
        return self._tasks.get(task_id)

    def get_tasks(self) -> List[SwarmTask]:
        with self._lock:
            return list(self._tasks.values())

    def status(self) -> dict:
        tasks = self.get_tasks()
        counts: Dict[str, int] = {}
        for t in tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return {"total": len(tasks), "by_status": counts, "workers": self.max_workers}

    # ── Shutdown ──────────────────────────────────────────────

    def shutdown(self, wait_for_tasks: bool = False):
        self._closed = True
        try:
            self._executor.shutdown(wait=wait_for_tasks)
        except Exception:
            pass
