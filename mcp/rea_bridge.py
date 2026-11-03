"""
VERONIKA AI - REA (Reasoning, Execution & Action) Bridge

A single autonomous agent loop that unifies four capabilities requested in the
VERONIKA SUPREME directive:

  1. ReAct loop           - Thought -> Action -> Observation, iterated until a
                            final answer is produced (bounded by max_iterations).
  2. Goal decomposition   - break a high-level goal into ordered sub-goals.
  3. Action execution     - dispatches real system actions through the
                            ActionRegistry and MCP tools through the MCPManager.
  4. Recursive sub-agents - spawn child REA agents for deep/parallel work
                            (the substrate for the Phase 3 sub-agent swarm).
  5. Remote execution     - hooks to run or serialize actions/goals for the
                            sync server (Android / remote control).

It is intentionally decoupled: pass a provider_manager, an action_registry and
an optional mcp_manager, or let it construct sensible defaults.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════

_REA_SYSTEM = """You are the REA (Reasoning, Execution & Action) engine of VERONIKA AI,
created by Swapnil Kumar. You autonomously accomplish a goal by reasoning step by
step and running tools -- the ReAct pattern.

On EVERY turn you must reply with EXACTLY ONE JSON object and nothing else.

To take a step:
{{"thought": "your reasoning", "action": "action_name", "action_input": {{...}}}}

When the goal is fully achieved, or you can answer directly:
{{"thought": "your reasoning", "final_answer": "the conclusive result for the user"}}

Rules:
- Use only actions listed below.
- One action per turn. Inspect the observation, then decide the next action.
- Never invent action results. If an action fails, adapt or report it.
- Prefer the most direct action. Do not loop.
- When no further action is needed, return a final_answer.

Available actions:
{catalog}
"""

_DECOMPOSE_SYSTEM = """You are the planning module of VERONIKA AI. Break the user's
goal into an ordered list of concrete, independently-actionable sub-goals.

Reply with EXACTLY ONE JSON object:
{{"sub_goals": ["first sub-goal", "second sub-goal", "..."]}}

Keep it to 2-6 sub-goals. If the goal is already atomic, return a single item.

Goal: {goal}
"""


# ═══════════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════════

@dataclass
class ReaStep:
    """A single Thought/Action/Observation cycle."""
    index: int
    thought: str = ""
    action: str = ""
    action_args: dict = field(default_factory=dict)
    observation: str = ""
    success: bool = True
    is_final: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "thought": self.thought,
            "action": self.action,
            "action_args": self.action_args,
            "observation": self.observation,
            "success": self.success,
            "is_final": self.is_final,
        }


@dataclass
class ReaResult:
    """The outcome of a full REA run."""
    goal: str
    steps: List[ReaStep] = field(default_factory=list)
    success: bool = False
    final_answer: str = ""
    iterations: int = 0
    error: str = ""

    @property
    def transcript(self) -> str:
        lines = []
        for s in self.steps:
            lines.append(f"[{s.index}] Thought: {s.thought}")
            if s.is_final:
                lines.append(f"    Final: {s.observation}")
            else:
                lines.append(f"    Action: {s.action} {json.dumps(s.action_args, ensure_ascii=False)}")
                lines.append(f"    Observation: {s.observation}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "success": self.success,
            "final_answer": self.final_answer,
            "iterations": self.iterations,
            "error": self.error,
            "steps": [s.to_dict() for s in self.steps],
        }


# ═══════════════════════════════════════════════════════════════
# REA Bridge
# ═══════════════════════════════════════════════════════════════

class ReaBridge:
    """Unified Reasoning, Execution & Action agent."""

    #: Actions that trigger recursive sub-agent spawning rather than a tool call.
    SPAWN_ACTIONS = ("spawn_sub_agent", "delegate", "spawn")

    def __init__(
        self,
        provider_manager=None,
        action_registry=None,
        mcp_manager=None,
        max_iterations: int = 8,
        on_step: Optional[Callable[[ReaStep], None]] = None,
        sub_agent_factory: Optional[Callable[..., "ReaBridge"]] = None,
        depth: int = 0,
        max_depth: int = 3,
    ):
        if provider_manager is None:
            from ai.provider_manager import ProviderManager
            provider_manager = ProviderManager()
        self.provider_manager = provider_manager
        self.action_registry = action_registry
        self.mcp_manager = mcp_manager
        self.max_iterations = max(1, int(max_iterations))
        self._on_step = on_step
        self.depth = depth
        self.max_depth = max_depth
        self.sub_agent_factory = sub_agent_factory or self._default_spawn

    # ── Capability discovery ──────────────────────────────────

    def available_actions(self) -> List[str]:
        names: List[str] = []
        if self.action_registry is not None:
            try:
                names += list(self.action_registry.get_available_actions())
            except Exception as e:  # noqa: BLE001
                logger.debug("Action registry unavailable: %s", e)
        if self.mcp_manager is not None:
            try:
                names += [t["name"] for t in self.mcp_manager.list_tool_dicts()]
            except Exception as e:  # noqa: BLE001
                logger.debug("MCP manager unavailable: %s", e)
        return sorted(set(names))

    def _action_catalog(self) -> str:
        lines: List[str] = []
        if self.action_registry is not None:
            try:
                for a in self.action_registry.get_available_actions():
                    lines.append(f"- {a}")
            except Exception:
                pass
        if self.mcp_manager is not None:
            try:
                for t in self.mcp_manager.list_tool_dicts():
                    desc = (t.get("description") or "").strip()
                    lines.append(f"- {t['name']}" + (f": {desc}" if desc else ""))
            except Exception:
                pass
        lines.append("- spawn_sub_agent: {\"goal\": \"a self-contained sub-task\"}")
        return "\n".join(lines) if lines else "(no actions available)"

    def describe(self) -> dict:
        return {
            "actions": self.available_actions(),
            "max_iterations": self.max_iterations,
            "depth": self.depth,
            "max_depth": self.max_depth,
            "sub_agents": self.depth < self.max_depth,
        }

    # ── Main loop ─────────────────────────────────────────────

    def run(self, goal: str, context: Optional[List[dict]] = None) -> ReaResult:
        """Run the ReAct loop until a final answer or iteration limit."""
        result = ReaResult(goal=goal)
        if not goal or not str(goal).strip():
            result.error = "Empty goal."
            return result

        history: List[dict] = list(context or [])
        exhausted = True

        for i in range(self.max_iterations):
            result.iterations = i + 1
            decision = self._think(goal, history)
            if decision.get("error"):
                result.error = decision["error"]
                exhausted = False
                break

            thought = str(decision.get("thought", "")).strip()

            if decision.get("final_answer") is not None:
                answer = str(decision.get("final_answer"))
                step = ReaStep(index=i + 1, thought=thought, is_final=True,
                               observation=answer, success=True)
                result.steps.append(step)
                self._emit(step)
                result.final_answer = answer
                result.success = True
                exhausted = False
                break

            action = decision.get("action", "") or ""
            args = decision.get("action_input") or decision.get("args") or {}
            if not isinstance(args, dict):
                args = {"input": args}

            step = ReaStep(index=i + 1, thought=thought, action=action, action_args=args)
            observation, ok = self._act(action, args)
            step.observation = observation
            step.success = ok
            result.steps.append(step)
            self._emit(step)

            history.append({
                "step": i + 1,
                "thought": thought,
                "action": action,
                "action_input": args,
                "observation": observation,
            })

        if exhausted and not result.success:
            result.error = (
                f"Reached max iterations ({self.max_iterations}) without a final answer."
            )
            if result.steps:
                result.final_answer = result.steps[-1].observation

        return result

    # ── Reasoning ─────────────────────────────────────────────

    def _think(self, goal: str, history: List[dict]) -> dict:
        prompt = self._build_prompt(goal, history)
        try:
            resp = self.provider_manager.send_message(prompt, system_prompt=_REA_SYSTEM.format(
                catalog=self._action_catalog()
            ))
        except Exception as e:  # noqa: BLE001
            return {"error": f"Reasoning step failed: {e}"}

        if getattr(resp, "is_error", False):
            return {"error": resp.error or "Provider error."}
        content = getattr(resp, "content", "") or ""
        decision = self._extract_json(content)
        if not decision:
            # Model returned prose with no JSON -- treat it as a final answer.
            return {"thought": "", "final_answer": content.strip()}
        return decision

    def _build_prompt(self, goal: str, history: List[dict]) -> str:
        lines = [f"GOAL: {goal}", ""]
        if history:
            lines.append("Trace so far:")
            for h in history:
                lines.append(
                    f"- step {h.get('step')}: action={h.get('action')} "
                    f"input={json.dumps(h.get('action_input', {}), ensure_ascii=False)} "
                    f"-> {h.get('observation')}"
                )
            lines.append("")
        lines.append("Reply with the next single JSON object.")
        return "\n".join(lines)

    def decompose(self, goal: str) -> List[str]:
        """Break a goal into ordered sub-goals (falls back to the goal itself)."""
        if not goal or not str(goal).strip():
            return []
        try:
            resp = self.provider_manager.send_message(
                _DECOMPOSE_SYSTEM.format(goal=goal)
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Goal decomposition failed: %s", e)
            return [goal]

        if getattr(resp, "is_error", False):
            return [goal]
        data = self._extract_json(getattr(resp, "content", "") or "")
        subs = data.get("sub_goals") or data.get("steps") or []
        if isinstance(subs, list) and subs:
            return [str(s) for s in subs if str(s).strip()]
        return [goal]

    # ── Acting ────────────────────────────────────────────────

    def _act(self, action: str, args: dict) -> Tuple[str, bool]:
        if not action:
            return ("No action was provided.", False)

        if action in self.SPAWN_ACTIONS:
            return self._spawn_sub_agent(args)

        if action == "finish":
            return ("Finished.", True)

        # MCP tool?
        if self.mcp_manager is not None:
            try:
                if self.mcp_manager.has_tool(action):
                    from mcp.mcp_client import extract_text
                    raw = self.mcp_manager.call(action, args)
                    return (extract_text(raw) or "(empty result)", True)
            except Exception as e:  # noqa: BLE001
                return (f"MCP tool '{action}' failed: {e}", False)

        # ActionRegistry?
        if self.action_registry is not None:
            try:
                res = self.action_registry.execute(action, args)
                return (getattr(res, "message", str(res)), bool(getattr(res, "success", False)))
            except Exception as e:  # noqa: BLE001
                return (f"Action '{action}' failed: {e}", False)

        return (f"No executor available for action '{action}'.", False)

    # ── Recursive sub-agents (swarm substrate) ────────────────

    def _default_spawn(self, goal: str, depth: int = 1) -> "ReaBridge":
        return ReaBridge(
            provider_manager=self.provider_manager,
            action_registry=self.action_registry,
            mcp_manager=self.mcp_manager,
            max_iterations=max(2, self.max_iterations - 2),
            on_step=self._on_step,
            depth=depth,
            max_depth=self.max_depth,
        )

    def _spawn_sub_agent(self, args: dict) -> Tuple[str, bool]:
        goal = (args or {}).get("goal") or (args or {}).get("task") or (args or {}).get("input")
        if not goal:
            return ("spawn_sub_agent requires a 'goal'.", False)
        if self.depth >= self.max_depth:
            return (f"Max sub-agent depth ({self.max_depth}) reached.", False)

        try:
            child = self.sub_agent_factory(goal, depth=self.depth + 1)
            outcome = child.run(goal) if hasattr(child, "run") else child(goal)
            if hasattr(outcome, "final_answer"):
                text = outcome.final_answer or outcome.error or "(no answer)"
                ok = bool(outcome.success)
            else:
                text = str(outcome)
                ok = True
            return (f"[sub-agent] {text}", ok)
        except Exception as e:  # noqa: BLE001
            return (f"Sub-agent failed: {e}", False)

    # ── Remote execution hooks ────────────────────────────────

    def execute_remote(self, action: str, args: Optional[dict] = None) -> dict:
        """Run a single action on behalf of a remote caller (sync server / Android)."""
        if self.action_registry is not None and not (
            self.mcp_manager is not None and self.mcp_manager.has_tool(action)
        ):
            try:
                res = self.action_registry.execute(action, args or {})
                return res.to_dict()
            except Exception as e:  # noqa: BLE001
                return {"success": False, "message": str(e), "data": None}
        text, ok = self._act(action, args or {})
        return {"success": ok, "message": text, "data": None}

    def handle_remote_request(self, payload: Optional[dict]) -> dict:
        """Entry point for remote REA requests.

        payload may be a one-shot action:  {"action": "...", "args": {...}}
        or a full goal:                    {"goal": "...", "context": [...]}
        """
        payload = payload or {}
        if payload.get("action"):
            return self.execute_remote(payload["action"], payload.get("args"))
        goal = payload.get("goal")
        if goal:
            return self.run(goal, context=payload.get("context")).to_dict()
        return {"success": False, "message": "Provide 'action' or 'goal'.", "data": None}

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Pull the first JSON object out of a model response."""
        if not text:
            return {}
        for block in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
            try:
                obj = json.loads(block)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue

        decoder = json.JSONDecoder()
        pos = 0
        length = len(text)
        while pos < length:
            idx = text.find("{", pos)
            if idx == -1:
                break
            try:
                obj, _ = decoder.raw_decode(text[idx:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
            pos = idx + 1
        return {}

    def _emit(self, step: ReaStep):
        if self._on_step is None:
            return
        try:
            self._on_step(step)
        except Exception as e:  # noqa: BLE001
            logger.debug("on_step callback failed: %s", e)
