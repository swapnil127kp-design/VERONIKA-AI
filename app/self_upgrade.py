"""
Self-upgrade engine for VERONIKA AI.

Provides safe self-upgrade capabilities:
- Git repository validation and status checks
- Timestamped backups of the repository
- Git fetch/pull from remote
- Post-upgrade validation (pytest collection/import check)
- Safe mode with automatic rollback on validation failure
- Upgrade state tracking for rollback
"""
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import APP_DATA_DIR, config

logger = logging.getLogger(__name__)

BACKUP_DIR = APP_DATA_DIR / "backups"
STATE_FILE = APP_DATA_DIR / "upgrade_state.json"


class UpgradeResult:
    """Result of an upgrade operation."""

    def __init__(self, success: bool = False, message: str = "", data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }


class SelfUpgrader:
    """Self-upgrade manager for the VERONIKA AI application."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path(__file__).parent.parent
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load upgrade state: %s", e)
        return {}

    def _save_state(self, state: Dict[str, Any]):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            self._state = state
        except OSError as e:
            logger.error("Failed to save upgrade state: %s", e)

    def is_git_repo(self) -> bool:
        """Check if the repository is a git repository."""
        git_dir = self.repo_root / ".git"
        return git_dir.exists()

    def _run_git(self, args: List[str], cwd: Optional[Path] = None, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repository."""
        cwd = cwd or self.repo_root
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=capture_output,
            text=True,
            check=False,
            timeout=300,
        )

    def current_commit(self) -> str:
        """Get the current commit hash (short)."""
        if not self.is_git_repo():
            return "unknown"
        result = self._run_git(["rev-parse", "--short", "HEAD"])
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"

    def current_branch(self) -> str:
        """Get the current git branch."""
        if not self.is_git_repo():
            return "unknown"
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"

    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes in the working tree."""
        if not self.is_git_repo():
            return False
        result = self._run_git(["status", "--porcelain"])
        if result.returncode != 0:
            return False
        return bool(result.stdout.strip())

    def remote_url(self) -> str:
        """Get the origin remote URL."""
        if not self.is_git_repo():
            return ""
        result = self._run_git(["remote", "get-url", "origin"])
        if result.returncode == 0:
            return result.stdout.strip()
        return ""

    def fetch(self) -> UpgradeResult:
        """Fetch latest changes from remote."""
        if not self.is_git_repo():
            return UpgradeResult(False, "Not a git repository")
        if self.has_uncommitted_changes():
            logger.warning("Repository has uncommitted changes; fetch may be safe but pull could conflict")
        result = self._run_git(["fetch", "--all", "--prune"])
        if result.returncode != 0:
            return UpgradeResult(False, f"Fetch failed: {result.stderr.strip()}")
        return UpgradeResult(True, "Fetched latest changes from remote")

    def backup(self, include_logs: bool = False) -> UpgradeResult:
        """Create a timestamped backup of the repository."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"veronika_backup_{timestamp}"
        try:
            ignore = shutil.ignore_patterns(
                ".venv",
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                ".git",
                "dist",
                "build",
                "*.egg-info",
            )
            shutil.copytree(
                self.repo_root,
                backup_path,
                ignore=ignore,
                dirs_exist_ok=False,
            )
            # Optionally skip logs to save space
            if not include_logs:
                logs_dir = backup_path / "logs"
                if logs_dir.exists():
                    shutil.rmtree(logs_dir, ignore_errors=True)
            commit = self.current_commit()
            manifest = {
                "timestamp": timestamp,
                "commit_before": commit,
                "branch": self.current_branch(),
                "repo_root": str(self.repo_root),
            }
            with open(backup_path / "BACKUP_MANIFEST.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            self._save_state({
                "last_backup": str(backup_path),
                "commit_before": commit,
                "backup_timestamp": timestamp,
            })
            return UpgradeResult(True, f"Backup created at {backup_path}", {"path": str(backup_path)})
        except Exception as e:
            logger.error("Backup failed: %s", e)
            return UpgradeResult(False, f"Backup failed: {e}")

    def pull(self, branch: Optional[str] = None) -> UpgradeResult:
        """Pull latest changes from remote."""
        if not self.is_git_repo():
            return UpgradeResult(False, "Not a git repository")
        if self.has_uncommitted_changes():
            return UpgradeResult(False, "Repository has uncommitted changes; commit or stash first")
        args = ["pull"]
        if branch:
            args.extend(["origin", branch])
        result = self._run_git(args)
        if result.returncode != 0:
            return UpgradeResult(False, f"Pull failed: {result.stderr.strip() or result.stdout.strip()}")
        new_commit = self.current_commit()
        self._save_state({**self._state, "commit_after_pull": new_commit, "pulled_at": datetime.now().isoformat()})
        return UpgradeResult(True, f"Pulled successfully (commit: {new_commit})", {"commit": new_commit})

    def validate(self, quick: bool = True) -> UpgradeResult:
        """Validate the upgraded codebase."""
        errors: List[str] = []
        # Try to import key modules
        try:
            import importlib
            for mod_name in ["app.config", "app.self_upgrade", "ai.swarm_coordinator", "automation.action_registry", "mcp.rea_bridge"]:
                try:
                    importlib.import_module(mod_name)
                except Exception as e:
                    errors.append(f"Import {mod_name} failed: {e}")
        except Exception as e:
            errors.append(f"Import validation failed: {e}")
        if quick:
            return UpgradeResult(len(errors) == 0, "Quick validation passed" if not errors else "Quick validation had issues", {"errors": errors})
        # Full validation: run pytest collection
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                errors.append(f"pytest collection failed: {result.stderr.strip()}")
        except Exception as e:
            errors.append(f"pytest validation failed: {e}")
        ok = len(errors) == 0
        return UpgradeResult(ok, "Validation passed" if ok else "Validation failed", {"errors": errors})

    def upgrade(self, branch: Optional[str] = None, auto_backup: bool = True, auto_validate: bool = True, safe_mode: bool = True) -> UpgradeResult:
        """Perform a full self-upgrade with safety checks."""
        if not self.is_git_repo():
            return UpgradeResult(False, "Not a git repository; cannot self-upgrade via git")
        commit_before = self.current_commit()
        branch_cur = self.current_branch()
        if self.has_uncommitted_changes() and safe_mode:
            return UpgradeResult(False, "Uncommitted changes detected. Stash or commit before upgrading in safe mode.")
        backup_res = UpgradeResult(True, "Backup skipped")
        if auto_backup:
            backup_res = self.backup()
            if not backup_res.success and safe_mode:
                return UpgradeResult(False, f"Backup failed; aborting upgrade: {backup_res.message}")
        fetch_res = self.fetch()
        if not fetch_res.success:
            return UpgradeResult(False, f"Fetch failed: {fetch_res.message}")
        pull_res = self.pull(branch=branch or branch_cur)
        if not pull_res.success:
            return UpgradeResult(False, f"Pull failed: {pull_res.message}")
        commit_after = pull_res.data.get("commit") or self.current_commit()
        validation_res = UpgradeResult(True, "Validation skipped")
        if auto_validate:
            validation_res = self.validate(quick=False)
            if not validation_res.success and safe_mode:
                logger.warning("Validation failed after upgrade; initiating rollback")
                rb = self.rollback()
                return UpgradeResult(False, f"Upgrade validation failed and rolled back: {validation_res.message}", {
                    "rollback": rb.to_dict(),
                    "validation_errors": validation_res.data.get("errors", []),
                })
        state = {
            "last_upgrade": datetime.now().isoformat(),
            "commit_before": commit_before,
            "commit_after": commit_after,
            "branch_before": branch_cur,
            "branch_after": self.current_branch(),
            "backup_path": backup_res.data.get("path") if backup_res.data else self._state.get("last_backup"),
            "validation_ok": validation_res.success,
        }
        self._save_state({**self._state, **state})
        return UpgradeResult(True, f"Upgrade completed ( {commit_before} -> {commit_after} )", state)

    def rollback(self) -> UpgradeResult:
        """Rollback to the last backup if available."""
        backup_path = self._state.get("last_backup")
        if not backup_path:
            return UpgradeResult(False, "No backup path found in upgrade state")
        bpath = Path(backup_path)
        if not bpath.exists():
            return UpgradeResult(False, f"Backup path does not exist: {backup_path}")
        try:
            # Simple restore: copy files back (excluding .git from backup; but backup didn't copy .git)
            # Best-effort: overwrite non-venv files
            ignore = shutil.ignore_patterns(
                ".venv",
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                "dist",
                "build",
                "*.egg-info",
            )
            for item in bpath.rglob("*"):
                if any(part in {".venv", "__pycache__", "node_modules"} for part in item.relative_to(bpath).parts):
                    continue
                rel = item.relative_to(bpath)
                dst = self.repo_root / rel
                if item.is_dir():
                    dst.mkdir(parents=True, exist_ok=True)
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(item, dst)
                except Exception as e:
                    logger.debug("Skip copy %s: %s", rel, e)
            self._save_state({**self._state, "rolled_back_at": datetime.now().isoformat()})
            return UpgradeResult(True, f"Rollback completed from {backup_path}")
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            return UpgradeResult(False, f"Rollback failed: {e}")

    def status(self) -> Dict[str, Any]:
        """Get current upgrade/status information."""
        return {
            "git_repo": self.is_git_repo(),
            "repo_root": str(self.repo_root),
            "branch": self.current_branch(),
            "commit": self.current_commit(),
            "uncommitted_changes": self.has_uncommitted_changes(),
            "remote": self.remote_url(),
            "backup_dir": str(BACKUP_DIR),
            "state": self._state,
        }
