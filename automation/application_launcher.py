"""
VERONIKA AI - Application Launcher
Safely launches installed applications on Windows.
"""
import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, List

from automation.permissions import permissions

logger = logging.getLogger(__name__)

# Known application mappings for Windows
KNOWN_APPS: Dict[str, List[str]] = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "windows terminal": [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
        "wt.exe",
    ],
    "vscode": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        "code",
    ],
    "visual studio code": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        "code",
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "google chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "microsoft edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
    ],
    "snipping tool": ["SnippingTool.exe"],
}


class ApplicationLauncher:
    """Safely discovers and launches Windows applications."""

    def find_application(self, name: str) -> Optional[str]:
        """Find the executable path for a named application."""
        if not permissions.validate_app_name(name):
            logger.warning("Invalid application name: %s", name)
            return None

        name_lower = name.lower().strip()

        # Check known apps first
        if name_lower in KNOWN_APPS:
            for path in KNOWN_APPS[name_lower]:
                expanded = os.path.expandvars(path)
                if Path(expanded).exists():
                    return expanded
                # Try shutil.which for PATH-available commands
                found = shutil.which(expanded)
                if found:
                    return found

        # Try to find on PATH
        found = shutil.which(name_lower)
        if found:
            return found

        # Try with .exe extension
        found = shutil.which(name_lower + ".exe")
        if found:
            return found

        return None

    def launch(self, name: str, args: List[str] = None) -> Dict:
        """Launch an application by name."""
        result = {"success": False, "message": "", "app": name}

        exe_path = self.find_application(name)
        if not exe_path:
            result["message"] = (
                f"Could not find application '{name}'. "
                f"It may not be installed or not in the expected location."
            )
            return result

        try:
            cmd = [exe_path] + (args or [])
            logger.info("Launching: %s", " ".join(cmd))
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else subprocess.DETACHED_PROCESS,
            )
            result["success"] = True
            result["message"] = f"Successfully launched {name}"
        except FileNotFoundError:
            result["message"] = f"Application file not found: {exe_path}"
        except PermissionError:
            result["message"] = f"Permission denied when launching {name}"
        except Exception as e:
            result["message"] = f"Failed to launch {name}: {e}"

        return result

    def get_known_apps(self) -> List[str]:
        """Return list of known application names."""
        return sorted(set(KNOWN_APPS.keys()))
