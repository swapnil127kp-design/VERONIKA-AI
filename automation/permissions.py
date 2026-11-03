"""
VERONIKA AI - Automation Permissions
Manages which actions and directories are permitted.
"""
import logging
from pathlib import Path
from typing import List, Set
import re

from app.config import config

logger = logging.getLogger(__name__)


class PermissionManager:
    """Controls what automation actions are allowed."""

    # Actions that require user confirmation
    DESTRUCTIVE_ACTIONS = {
        "delete_file", "move_file", "overwrite_file",
        "clear_all_data", "clear_all_memories",
    }

    # Paths that must never be accessed
    FORBIDDEN_PATTERNS = [
        r"[/\\]\.ssh([/\\]|$)",
        r"[/\\]\.gnupg([/\\]|$)",
        r"[/\\]Credentials([/\\]|$)",
        r"[/\\]Login Data",
        r"[/\\]\.password",
        r"[/\\]\.env$",
        r"[/\\]passwords?\.",
        r"[/\\]private[_\s]?key",
        r"[/\\]AppData[/\\].*[/\\]Google[/\\]Chrome[/\\]User Data([/\\]|$)",
        r"[/\\]AppData[/\\].*[/\\]Mozilla[/\\]Firefox[/\\]Profiles([/\\]|$)",
    ]

    def __init__(self):
        self._compiled_forbidden = [
            re.compile(p, re.IGNORECASE) for p in self.FORBIDDEN_PATTERNS
        ]

    def is_path_allowed(self, path: str) -> bool:
        """Check if a file path is allowed for access."""
        path_str = str(Path(path).resolve())
        for pattern in self._compiled_forbidden:
            if pattern.search(path_str):
                logger.warning("Access denied to forbidden path: %s", path_str)
                return False
        return True

    def is_path_in_allowed_dirs(self, path: str) -> bool:
        """Check if path is within user-configured allowed directories."""
        allowed = config.get("automation", "allowed_directories", [])
        if not allowed:
            # If no restrictions configured, allow non-forbidden paths
            return self.is_path_allowed(path)

        resolved = Path(path).resolve()
        for allowed_dir in allowed:
            try:
                resolved.relative_to(Path(allowed_dir).resolve())
                return self.is_path_allowed(path)
            except ValueError:
                continue
        return False

    def requires_confirmation(self, action_type: str) -> bool:
        """Check if an action requires explicit user confirmation."""
        if config.get("automation", "confirm_destructive", True):
            return action_type in self.DESTRUCTIVE_ACTIONS
        return False

    def validate_url(self, url: str) -> bool:
        """Validate a URL is safe to open."""
        if not url:
            return False
        # Must start with http/https or be a known protocol
        allowed_schemes = ("http://", "https://", "ms-settings:")
        return any(url.lower().startswith(s) for s in allowed_schemes)

    def validate_app_name(self, name: str) -> bool:
        """Validate an application name doesn't contain injection characters."""
        # Reject shell metacharacters
        dangerous = set(';&|`$(){}[]<>!\\"\'\n\r')
        return not any(c in name for c in dangerous)


permissions = PermissionManager()
