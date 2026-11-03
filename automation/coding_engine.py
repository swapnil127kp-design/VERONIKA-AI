"""
VERONIKA AI - Coding & Shell Engine
Extreme automation: shell execution, Python runner with live output,
file editing, git operations, and a self-correction loop that feeds
failures back to a code-specialist model for an automatic fix + retry.
"""
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from automation.permissions import permissions

logger = logging.getLogger(__name__)

DEFAULT_SHELL_TIMEOUT = 60
DEFAULT_PY_TIMEOUT = 30
MAX_CORRECTION_ATTEMPTS = 3

# Path patterns that must never be touched by shell/code execution.
_FORBIDDEN_SHELL_TARGETS = re.compile(
    r"(\.ssh|\.env|credentials|login data|sam\.system|ntuser\.dat|"
    r"boot\.ini|format\s+[a-z]:|Remove-Item\s+.*-Recurse\s+.*[\\/]$)",
    re.IGNORECASE,
)

# Windows commands that are too destructive to run automatically.
_BLOCKED_COMMANDS = (
    "format ", "rd /s", "rmdir /s", "Remove-Item",
    "diskpart", "mkfs", "dd if=", ":(){", "del /f /s",
)


class CodingEngine:
    """Shell / Python / Git execution with security checks."""

    def __init__(self, provider_manager=None):
        self._provider_manager = provider_manager

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    @staticmethod
    def _is_safe_command(command: str) -> Tuple[bool, str]:
        if not command or not command.strip():
            return False, "Empty command."
        lowered = command.lower()
        for blocked in _BLOCKED_COMMANDS:
            if blocked in lowered:
                return False, f"Blocked dangerous command pattern: {blocked.strip()}"
        if _FORBIDDEN_SHELL_TARGETS.search(command):
            return False, "Command touches a protected path."
        return True, ""

    # ------------------------------------------------------------------
    # Shell execution
    # ------------------------------------------------------------------

    def run_shell(
        self,
        command: str,
        directory: str = "",
        timeout: int = DEFAULT_SHELL_TIMEOUT,
    ) -> dict:
        """Run a PowerShell command and capture stdout/stderr."""
        ok, reason = self._is_safe_command(command)
        if not ok:
            return {"success": False, "stdout": "", "stderr": reason, "code": -1}

        workdir = directory or os.getcwd()
        if directory and not permissions.is_path_allowed(directory):
            return {"success": False, "stdout": "",
                    "stderr": "Access to this directory is not permitted.", "code": -1}
        if directory and not Path(directory).is_dir():
            return {"success": False, "stdout": "",
                    "stderr": f"Not a valid directory: {directory}", "code": -1}

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=workdir,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=max(1, min(int(timeout or DEFAULT_SHELL_TIMEOUT), 600)),
            )
            return {
                "success": proc.returncode == 0,
                "stdout": (proc.stdout or "")[-8000:],
                "stderr": (proc.stderr or "")[-8000:],
                "code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out.", "code": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "code": -1}

    # ------------------------------------------------------------------
    # Python execution
    # ------------------------------------------------------------------

    def run_python(
        self,
        code: str,
        directory: str = "",
        timeout: int = DEFAULT_PY_TIMEOUT,
    ) -> dict:
        """Execute a Python snippet in a subprocess with live output capture."""
        if not code or not code.strip():
            return {"success": False, "stdout": "", "stderr": "Empty code.", "code": -1}
        if _FORBIDDEN_SHELL_TARGETS.search(code):
            return {"success": False, "stdout": "",
                    "stderr": "Code touches a protected path.", "code": -1}

        import sys
        workdir = directory or os.getcwd()
        if directory and not permissions.is_path_allowed(directory):
            return {"success": False, "stdout": "",
                    "stderr": "Access to this directory is not permitted.", "code": -1}

        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=workdir,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=max(1, min(int(timeout or DEFAULT_PY_TIMEOUT), 300)),
            )
            return {
                "success": proc.returncode == 0,
                "stdout": (proc.stdout or "")[-8000:],
                "stderr": (proc.stderr or "")[-8000:],
                "code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Code timed out.", "code": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "code": -1}

    # ------------------------------------------------------------------
    # File editing
    # ------------------------------------------------------------------

    @staticmethod
    def edit_file(path: str, old: str, new: str, count: int = 0) -> dict:
        """Replace `old` with `new` in a text file."""
        if not path:
            return {"success": False, "message": "No path given."}
        if not permissions.is_path_allowed(path):
            return {"success": False, "message": "Access to this file is not permitted."}

        p = Path(path)
        if not p.exists():
            return {"success": False, "message": f"File does not exist: {path}"}
        if not p.is_file():
            return {"success": False, "message": f"Not a file: {path}"}
        if p.stat().st_size > 5 * 1024 * 1024:
            return {"success": False, "message": "File too large to edit (>5 MB)."}

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"success": False, "message": f"Read failed: {e}"}

        if old not in text:
            return {"success": False, "message": "Target text not found in file."}

        replaced = text.replace(old, new, count) if count else text.replace(old, new)
        try:
            p.write_text(replaced, encoding="utf-8")
        except OSError as e:
            return {"success": False, "message": f"Write failed: {e}"}

        occurrences = text.count(old)
        return {
            "success": True,
            "message": f"Replaced {occurrences} occurrence(s) in {path}",
            "occurrences": occurrences,
        }

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def git_operation(
        self, operation: str = "status", message: str = "", directory: str = ""
    ) -> dict:
        """Perform a common git operation in a repository."""
        allowed = {"status", "log", "diff", "branch", "commit", "push", "pull", "add"}
        op = (operation or "").lower()
        if op not in allowed:
            return {"success": False,
                    "message": f"Unsupported git operation '{operation}'. "
                               f"Allowed: {', '.join(sorted(allowed))}"}

        workdir = directory or os.getcwd()
        repo = Path(workdir)
        if not repo.is_dir():
            return {"success": False, "message": f"Not a directory: {workdir}"}
        if not (repo / ".git").exists():
            return {"success": False, "message": f"Not a git repository: {workdir}"}

        if op == "commit":
            if not message or not message.strip():
                return {"success": False, "message": "Commit message required."}
            # Stage everything the user asked for, then commit.
            stage = self.run_shell("git add -A", directory=workdir)
            if not stage["success"]:
                return {"success": False, "message": stage["stderr"]}
            args = ["git", "commit", "-m", message]
        elif op == "add":
            args = ["git", "add", "-A"]
        else:
            args = ["git", op]

        try:
            proc = subprocess.run(
                args, cwd=workdir, capture_output=True, text=True,
                errors="replace", timeout=60,
            )
        except Exception as e:
            return {"success": False, "message": str(e)}

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()[-4000:]
        return {
            "success": proc.returncode == 0,
            "message": output or f"git {op} completed",
            "code": proc.returncode,
        }


class SelfCorrectingRunner:
    """Runs Python code; on failure, asks a code model to fix it and retries.

    The error traceback is fed back to the orchestrator with TaskType.CODE,
    which routes to the code-specialist model (kr/qwen3-coder-next via the
    local OmniRoute gateway, or the next available code-capable provider).
    """

    def __init__(self, coding_engine: CodingEngine, provider_manager=None):
        self._engine = coding_engine
        self._provider_manager = provider_manager

    def run(
        self,
        code: str,
        directory: str = "",
        timeout: int = DEFAULT_PY_TIMEOUT,
        max_attempts: int = MAX_CORRECTION_ATTEMPTS,
        on_attempt: Optional[Callable[[int, dict], None]] = None,
    ) -> dict:
        """Execute code, auto-fixing and retrying on failure."""
        from ai.provider_manager import TaskType

        attempts: List[dict] = []
        current = code
        last = None

        for attempt in range(1, max(1, int(max_attempts)) + 1):
            result = self._engine.run_python(current, directory=directory, timeout=timeout)
            attempts.append({"attempt": attempt, "code": current, "result": result})
            if on_attempt:
                try:
                    on_attempt(attempt, result)
                except Exception:
                    pass

            if result["success"]:
                return {
                    "success": True,
                    "attempts": attempt,
                    "output": result["stdout"],
                    "code": current,
                    "history": attempts,
                }
            last = result

            if self._provider_manager is None:
                break
            if attempt >= max(1, int(max_attempts)):
                break

            fixed = self._request_fix(current, result, directory)
            if not fixed or fixed.strip() == current.strip():
                logger.info("Self-correction: no better fix produced (attempt %d)", attempt)
                break
            current = fixed
            logger.info("Self-correction: retrying with revised code (attempt %d)", attempt + 1)

        return {
            "success": False,
            "attempts": len(attempts),
            "output": (last or {}).get("stdout", ""),
            "error": (last or {}).get("stderr", ""),
            "code": current,
            "history": attempts,
        }

    def _request_fix(self, code: str, result: dict, directory: str = "") -> Optional[str]:
        from ai.provider_manager import TaskType
        from ai.provider_base import ModelConfig

        prompt = (
            "You are a Python debugging expert. The code below failed. "
            "Return ONLY the corrected, complete, runnable Python code inside a "
            "```python code block, with no explanation before or after.\n\n"
            f"Working directory: {directory or os.getcwd()}\n\n"
            f"FAILED CODE:\n```python\n{code}\n```\n\n"
            f"STDOUT:\n{result.get('stdout', '')}\n\n"
            f"STDERR / TRACEBACK:\n{result.get('stderr', '')}\n\n"
            "Return the fixed code now."
        )
        try:
            # Prefer the code-specialist route; fall back to whatever is available.
            cfg = ModelConfig(model="kr/qwen3-coder-next", temperature=0.2, max_tokens=2048)
            response = self._provider_manager.send_message(
                prompt, task=TaskType.CODE, model_config=cfg
            )
            if response.is_error:
                logger.warning("Self-correction model error: %s", response.error)
                return None
            return self._extract_code(response.content)
        except Exception as e:
            logger.warning("Self-correction request failed: %s", e)
            return None

    @staticmethod
    def _extract_code(text: str) -> Optional[str]:
        if not text:
            return None
        m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        return text.strip()
