"""
VERONIKA AI - Action Registry
Central registry mapping action names to handlers.
"""
import logging
import os
import subprocess
import math
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from automation.permissions import permissions
from automation.application_launcher import ApplicationLauncher
from automation.file_actions import FileActions
from automation.browser_actions import BrowserActions
from automation.coding_engine import CodingEngine, SelfCorrectingRunner

logger = logging.getLogger(__name__)


class ActionResult:
    """Result of an executed action."""

    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data

    def to_dict(self) -> dict:
        return {"success": self.success, "message": self.message, "data": self.data}


class ActionRegistry:
    """Central action dispatcher for VERONIKA AI automation."""

    def __init__(self, memory_manager=None, provider_manager=None,
                 mcp_manager=None, rea_bridge=None, upgrader=None, **kwargs):
        if upgrader is None:
            upgrader = kwargs.get('self_upgrader') or kwargs.get('upgrade_manager') or kwargs.get('upgrader_obj')
        self.app_launcher = ApplicationLauncher()
        self.file_actions = FileActions()
        self.browser_actions = BrowserActions()
        self.memory_manager = memory_manager
        self.workflow_engine = None

        # Coding & shell engine (imported at module top; now actually wired in)
        self.provider_manager = provider_manager
        self.coding_engine = CodingEngine(provider_manager=provider_manager)
        self.self_correcting_runner = SelfCorrectingRunner(
            self.coding_engine, provider_manager=provider_manager
        )

        # MCP tool servers + REA autonomous reasoning (Phase 2)
        self.mcp_manager = mcp_manager
        self.rea_bridge = rea_bridge
        self.exam_predictor = None
        self.swarm = None
        self.upgrader = upgrader

        self._actions: Dict[str, Callable] = {
            "launch_app": self._launch_app,
            "open_folder": self._open_folder,
            "open_website": self._open_website,
            "open_settings": self._open_settings,
            "create_file": self._create_file,
            "delete_file": self._delete_file,
            "search_files": self._search_files,
            "take_screenshot": self._take_screenshot,
            "create_reminder": self._create_reminder,
            "open_terminal": self._open_terminal,
            "browser_search": self._browser_search,
            "calculate": self._calculate,
            "save_note": self._save_note,
            "list_directory": self._list_directory,
            "read_file": self._read_file,
            "file_info": self._file_info,
            "start_workflow": self._start_workflow,
            # Coding & execution tools (advertised in the persona protocol)
            "run_shell": self._run_shell,
            "run_python": self._run_python,
            "run_python_autofix": self._run_python_autofix,
            "edit_file": self._edit_file,
            "git_operation": self._git_operation,
            # REA autonomous reasoning (Phase 2)
            "reason": self._reason,
            "decompose_goal": self._decompose_goal,
            # Phase 3: swarm + exam prediction
            "swarm_run": self._swarm_run,
            "predict_exam": self._predict_exam,
            "add_past_question": self._add_past_question,
            "upgrade_status": self._upgrade_status,
            "upgrade_backup": self._upgrade_backup,
            "upgrade_validate": self._upgrade_validate,
            "upgrade_run": self._upgrade_run,
            "upgrade_rollback": self._upgrade_rollback,
        }

        # Expose MCP server tools as first-class actions (namespaced mcp__*).
        if mcp_manager is not None:
            self.register_mcp_tools(mcp_manager)

    def register_mcp_tools(self, mcp_manager) -> list:
        """Register every tool from an MCPManager as an action. Returns names."""
        self.mcp_manager = mcp_manager
        actions = mcp_manager.as_actions(wrap=self._wrap_mcp_result)
        self._actions.update(actions)
        return sorted(actions.keys())

    @staticmethod
    def _wrap_mcp_result(full_name: str, ok: bool, text: str, raw: dict) -> "ActionResult":
        return ActionResult(
            bool(ok),
            text or f"MCP tool '{full_name}' returned no output.",
            raw,
        )

    def _get_rea(self):
        """Lazily construct a REA bridge wired to this registry (self-avoiding)."""
        if self.rea_bridge is None:
            from mcp.rea_bridge import ReaBridge
            from app.config import config
            self.rea_bridge = ReaBridge(
                provider_manager=self.provider_manager,
                action_registry=self,
                mcp_manager=self.mcp_manager,
                max_iterations=config.get("rea", "max_iterations", 8),
                max_depth=config.get("rea", "max_sub_agent_depth", 3),
            )
        return self.rea_bridge

    def _reason(self, goal: str = "", **kwargs) -> ActionResult:
        """Autonomously accomplish a goal via the REA (ReAct) loop."""
        if not goal:
            return ActionResult(False, "Please specify a goal to reason about.")
        res = self._get_rea().run(goal)
        return ActionResult(
            res.success,
            res.final_answer or res.error or "No result.",
            res.to_dict(),
        )

    def _decompose_goal(self, goal: str = "", **kwargs) -> ActionResult:
        """Break a goal into ordered sub-goals."""
        if not goal:
            return ActionResult(False, "Please specify a goal to decompose.")
        subs = self._get_rea().decompose(goal)
        listing = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(subs))
        return ActionResult(True, f"Sub-goals:\n{listing}", {"sub_goals": subs})

    def _get_swarm(self):
        if self.swarm is None:
            from ai.swarm_coordinator import SwarmCoordinator
            from app.config import config
            self.swarm = SwarmCoordinator(
                provider_manager=self.provider_manager,
                action_registry=self,
                mcp_manager=self.mcp_manager,
                max_workers=config.get("swarm", "max_workers", 4),
                max_iterations=config.get("swarm", "max_iterations", 6),
                max_depth=config.get("swarm", "max_depth", 2),
            )
        return self.swarm

    def _swarm_run(self, goals=None, goal: str = "", **kwargs) -> ActionResult:
        """Run a parallel swarm of sub-agents over several goals."""
        if goals is None:
            goals = [goal] if goal else []
        if isinstance(goals, str):
            goals = [goals]
        goals = [g for g in goals if g and str(g).strip()]
        if not goals:
            return ActionResult(False, "Please provide one or more goals.")
        result = self._get_swarm().run(goals)
        return ActionResult(result.success, result.summary, result.to_dict())

    def _get_exam(self):
        if self.exam_predictor is None:
            from ai.exam_predictor import ExamPredictor
            self.exam_predictor = ExamPredictor(
                provider_manager=self.provider_manager,
                memory_manager=self.memory_manager,
            )
        return self.exam_predictor

    def _predict_exam(self, subject: str = "", syllabus: str = "",
                      num_topics: int = 8, num_questions: int = 10, **kwargs) -> ActionResult:
        """Predict likely exam topics and questions for a subject."""
        if not subject:
            return ActionResult(False, "Please specify a subject.")
        prediction = self._get_exam().predict(
            subject, syllabus=syllabus,
            num_topics=num_topics, num_questions=num_questions,
        )
        self._get_exam().save_prediction(prediction)
        ok = bool(prediction.topics or prediction.questions)
        return ActionResult(ok, prediction.summary(), prediction.to_dict())

    def _add_past_question(self, subject: str = "", question: str = "",
                           year: str = "", marks: int = 0, **kwargs) -> ActionResult:
        """Record a past-exam question to improve future predictions."""
        if not subject or not question:
            return ActionResult(False, "Please specify both 'subject' and 'question'.")
        entry = self._get_exam().add_past_question(subject, question, year=year, marks=marks)
        return ActionResult(True, f"Recorded past question for {subject}.", entry)

    def _get_upgrader(self):
        if self.upgrader is None:
            from app.self_upgrade import SelfUpgrader
            self.upgrader = SelfUpgrader()
        return self.upgrader

    def _upgrade_status(self, **kwargs) -> ActionResult:
        st = self._get_upgrader().status()
        return ActionResult(True, "Upgrade status", st)

    def _upgrade_backup(self, include_logs: bool = False, **kwargs) -> ActionResult:
        res = self._get_upgrader().backup(include_logs=include_logs)
        return ActionResult(res.success, res.message, res.data)

    def _upgrade_validate(self, quick: bool = True, **kwargs) -> ActionResult:
        res = self._get_upgrader().validate(quick=quick)
        return ActionResult(res.success, res.message, res.data)

    def _upgrade_run(self, branch: str = None, auto_backup: bool = True,
                     auto_validate: bool = True, safe_mode: bool = True, **kwargs) -> ActionResult:
        res = self._get_upgrader().upgrade(
            branch=branch,
            auto_backup=auto_backup,
            auto_validate=auto_validate,
            safe_mode=safe_mode,
        )
        return ActionResult(res.success, res.message, res.data)

    def _upgrade_rollback(self, **kwargs) -> ActionResult:
        res = self._get_upgrader().rollback()
        return ActionResult(res.success, res.message, res.data)

    def get_available_actions(self) -> list:
        """Return list of registered action names."""
        return sorted(self._actions.keys())

    def execute(self, action_type: str, args: Dict[str, Any] = None) -> ActionResult:
        """Execute a registered action."""
        args = args or {}

        handler = self._actions.get(action_type)
        if not handler:
            return ActionResult(False, f"Unknown action: {action_type}")

        # Check if confirmation needed
        if permissions.requires_confirmation(action_type):
            return ActionResult(
                False,
                f"Action '{action_type}' requires user confirmation before execution.",
                {"requires_confirmation": True},
            )

        try:
            logger.info("Executing action: %s with args: %s", action_type, args)
            result = handler(**args)

            # Record in automation history
            if self.memory_manager:
                self.memory_manager.record_automation(
                    action_type, args, result.message, result.success
                )

            return result
        except TypeError as e:
            return ActionResult(False, f"Invalid arguments for action '{action_type}': {e}")
        except Exception as e:
            logger.error("Action execution error: %s", e)
            return ActionResult(False, f"Action failed: {e}")

    def _launch_app(self, name: str = "", **kwargs) -> ActionResult:
        if not name:
            return ActionResult(False, "Please specify an application name.")
        r = self.app_launcher.launch(name)
        return ActionResult(r["success"], r["message"])

    def _open_folder(self, path: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a folder path.")
        if not permissions.is_path_allowed(path):
            return ActionResult(False, "Access to this folder is not permitted.")

        p = Path(path)
        if not p.exists():
            return ActionResult(False, f"Folder does not exist: {path}")
        if not p.is_dir():
            return ActionResult(False, f"Not a directory: {path}")

        try:
            os.startfile(str(p))
            return ActionResult(True, f"Opened folder: {path}")
        except Exception as e:
            return ActionResult(False, f"Failed to open folder: {e}")

    def _open_website(self, url: str = "", **kwargs) -> ActionResult:
        if not url:
            return ActionResult(False, "Please specify a URL.")
        r = self.browser_actions.open_url(url)
        return ActionResult(r["success"], r["message"])

    def _open_settings(self, page: str = "", **kwargs) -> ActionResult:
        if not page:
            pages = self.browser_actions.get_available_settings()
            return ActionResult(
                False,
                f"Please specify a settings page. Available: {', '.join(pages)}",
            )
        r = self.browser_actions.open_settings(page)
        return ActionResult(r["success"], r["message"])

    def _create_file(self, path: str = "", content: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a file path.")
        r = self.file_actions.create_file(path, content)
        return ActionResult(r["success"], r["message"])

    def _search_files(self, directory: str = "", pattern: str = "*", **kwargs) -> ActionResult:
        if not directory:
            return ActionResult(False, "Please specify a directory to search.")
        r = self.file_actions.search_files(directory, pattern)
        return ActionResult(r["success"], r["message"], r.get("files"))

    def _take_screenshot(self, **kwargs) -> ActionResult:
        try:
            from vision.screenshot_capture import ScreenshotCapture
            capture = ScreenshotCapture()
            path = capture.capture_screen()
            if path:
                return ActionResult(True, f"Screenshot saved: {path}", {"path": path})
            return ActionResult(False, "Failed to capture screenshot.")
        except Exception as e:
            return ActionResult(False, f"Screenshot error: {e}")

    def _create_reminder(self, title: str = "", due_at: str = "", **kwargs) -> ActionResult:
        if not title:
            return ActionResult(False, "Please specify a reminder title.")
        if not due_at:
            return ActionResult(False, "Please specify when the reminder is due (ISO datetime).")

        if self.memory_manager:
            try:
                rid = self.memory_manager.create_reminder(title, due_at)
                return ActionResult(True, f"Reminder created: '{title}' due at {due_at}")
            except Exception as e:
                return ActionResult(False, f"Failed to create reminder: {e}")
        return ActionResult(False, "Memory manager not available.")

    def _open_terminal(self, directory: str = "", **kwargs) -> ActionResult:
        dir_path = directory or os.path.expanduser("~")
        if not permissions.is_path_allowed(dir_path):
            return ActionResult(False, "Access to this directory is not permitted.")
        if not Path(dir_path).is_dir():
            return ActionResult(False, f"Not a valid directory: {dir_path}")

        try:
            # Try Windows Terminal first, fall back to cmd
            result = self.app_launcher.launch("windows terminal", ["-d", dir_path])
            if not result["success"]:
                subprocess.Popen(
                    ["cmd", "/k", f"cd /d {dir_path}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                return ActionResult(True, f"Opened Command Prompt in {dir_path}")
            return ActionResult(True, result["message"])
        except Exception as e:
            return ActionResult(False, f"Failed to open terminal: {e}")

    def _browser_search(self, query: str = "", **kwargs) -> ActionResult:
        if not query:
            return ActionResult(False, "Please specify a search query.")
        r = self.browser_actions.browser_search(query)
        return ActionResult(r["success"], r["message"])

    def _calculate(self, expression: str = "", **kwargs) -> ActionResult:
        if not expression:
            return ActionResult(False, "Please specify a math expression.")

        # Safe evaluation using only math functions
        safe_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("_")
        }
        safe_names.update({"abs": abs, "round": round, "min": min, "max": max})

        try:
            # Only allow safe characters
            import re
            if not re.match(r'^[\d\s\+\-\*/\.\(\),a-zA-Z_]+$', expression):
                return ActionResult(False, "Expression contains invalid characters.")

            result = eval(expression, {"__builtins__": {}}, safe_names)
            return ActionResult(True, f"{expression} = {result}", {"result": result})
        except Exception as e:
            return ActionResult(False, f"Calculation error: {e}")

    def _save_note(self, title: str = "", content: str = "", **kwargs) -> ActionResult:
        if not title:
            return ActionResult(False, "Please specify a note title.")
        if self.memory_manager:
            self.memory_manager.save_memory("notes", title, content or "")
            return ActionResult(True, f"Note saved: '{title}'")
        return ActionResult(False, "Memory manager not available.")

    def _list_directory(self, path: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a directory path.")
        r = self.file_actions.list_directory(path)
        return ActionResult(r["success"], r["message"], r.get("files"))

    def _read_file(self, path: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a file path.")
        r = self.file_actions.read_file(path)
        return ActionResult(r["success"], r.get("message", ""), r.get("content"))

    def _file_info(self, path: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a file path.")
        r = self.file_actions.get_file_info(path)
        return ActionResult(r["success"], r["message"], r.get("info"))

    def _delete_file(self, path: str = "", **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a file path.")
        r = self.file_actions.delete_file(path)
        return ActionResult(r["success"], r["message"])

    # â”€â”€ Coding & execution tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _run_shell(self, command: str = "", directory: str = "", timeout: int = 60,
                   **kwargs) -> ActionResult:
        if not command:
            return ActionResult(False, "Please specify a command to run.")
        result = self.coding_engine.run_shell(command, directory=directory, timeout=timeout)
        ok = result.get("success", False)
        output = (result.get("stdout") or "").strip()
        error = (result.get("stderr") or "").strip()
        if ok:
            return ActionResult(True, output or "Command completed.", result)
        return ActionResult(False, error or "Command failed.", result)

    def _run_python(self, code: str = "", directory: str = "", timeout: int = 30,
                    **kwargs) -> ActionResult:
        if not code:
            return ActionResult(False, "Please provide Python code to run.")
        result = self.coding_engine.run_python(code, directory=directory, timeout=timeout)
        ok = result.get("success", False)
        output = (result.get("stdout") or "").strip()
        error = (result.get("stderr") or "").strip()
        if ok:
            return ActionResult(True, output or "Code executed successfully.", result)
        return ActionResult(False, error or "Code execution failed.", result)

    def _run_python_autofix(self, code: str = "", directory: str = "",
                            timeout: int = 30, **kwargs) -> ActionResult:
        """Run Python with automatic self-correction via a code model."""
        if not code:
            return ActionResult(False, "Please provide Python code to run.")
        result = self.self_correcting_runner.run(code, directory=directory, timeout=timeout)
        if result.get("success"):
            return ActionResult(
                True,
                f"Succeeded after {result.get('attempts', 1)} attempt(s).\n"
                f"{result.get('output', '').strip()}",
                result,
            )
        return ActionResult(
            False,
            f"Failed after {result.get('attempts', 1)} attempt(s).\n"
            f"{result.get('error', '').strip()}",
            result,
        )

    def _edit_file(self, path: str = "", old: str = "", new: str = "",
                   count: int = 0, **kwargs) -> ActionResult:
        if not path:
            return ActionResult(False, "Please specify a file path.")
        result = self.coding_engine.edit_file(path, old, new, count=count)
        return ActionResult(result.get("success", False), result.get("message", ""), result)

    def _git_operation(self, operation: str = "status", message: str = "",
                       directory: str = "", **kwargs) -> ActionResult:
        result = self.coding_engine.git_operation(operation, message, directory)
        return ActionResult(result.get("success", False), result.get("message", ""), result)

    def _start_workflow(self, workflow: str = "", **kwargs) -> ActionResult:
        if not workflow:
            return ActionResult(False, "Please specify a workflow name.")
        if not self.workflow_engine:
            from automation.workflow_engine import WorkflowEngine
            self.workflow_engine = WorkflowEngine(self)
        success = self.workflow_engine.start_workflow(workflow)
        if success:
            return ActionResult(True, f"Started workflow: '{workflow}'")
        return ActionResult(
            False,
            f"Could not start workflow '{workflow}'. Check if the workflow name is valid or if another workflow is already running.",
        )

