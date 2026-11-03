"""
VERONIKA AI - File Actions
Safe file operations for the file assistant feature.
"""
import logging
import os
import stat
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from automation.permissions import permissions

logger = logging.getLogger(__name__)

# Supported text file extensions for reading
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".conf", ".log", ".csv",
    ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
    ".php", ".sql", ".sh", ".bat", ".ps1", ".r", ".dart", ".kt",
    ".swift", ".lua", ".pl", ".scala", ".tex", ".rst", ".org",
}

# Maximum file size for reading (10 MB)
MAX_READ_SIZE = 10 * 1024 * 1024


class FileActions:
    """Safe file operations restricted to allowed paths."""

    def list_directory(self, path: str) -> Dict:
        """List files in a directory."""
        result = {"success": False, "files": [], "message": ""}

        if not permissions.is_path_allowed(path):
            result["message"] = "Access to this directory is not permitted."
            return result

        dir_path = Path(path)
        if not dir_path.exists():
            result["message"] = f"Directory does not exist: {path}"
            return result
        if not dir_path.is_dir():
            result["message"] = f"Not a directory: {path}"
            return result

        try:
            entries = []
            for entry in sorted(dir_path.iterdir()):
                try:
                    stat_info = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "size": stat_info.st_size if entry.is_file() else None,
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    })
                except (PermissionError, OSError):
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "size": None,
                        "modified": None,
                        "error": "Permission denied",
                    })

            result["success"] = True
            result["files"] = entries
            result["message"] = f"Found {len(entries)} items in {path}"
        except PermissionError:
            result["message"] = f"Permission denied: {path}"
        except Exception as e:
            result["message"] = f"Error listing directory: {e}"

        return result

    def search_files(self, directory: str, pattern: str, max_results: int = 50) -> Dict:
        """Search for files matching a pattern."""
        result = {"success": False, "files": [], "message": ""}

        if not permissions.is_path_allowed(directory):
            result["message"] = "Access to this directory is not permitted."
            return result

        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            result["message"] = f"Invalid directory: {directory}"
            return result

        try:
            found = []
            for match in dir_path.rglob(pattern):
                if len(found) >= max_results:
                    break
                if permissions.is_path_allowed(str(match)):
                    found.append({
                        "name": match.name,
                        "path": str(match),
                        "is_dir": match.is_dir(),
                    })

            result["success"] = True
            result["files"] = found
            result["message"] = f"Found {len(found)} files matching '{pattern}'"
        except PermissionError:
            result["message"] = f"Permission denied while searching: {directory}"
        except Exception as e:
            result["message"] = f"Search error: {e}"

        return result

    def read_file(self, path: str) -> Dict:
        """Read a text file's contents."""
        result = {"success": False, "content": "", "message": ""}

        if not permissions.is_path_allowed(path):
            result["message"] = "Access to this file is not permitted."
            return result

        file_path = Path(path)
        if not file_path.exists():
            result["message"] = f"File does not exist: {path}"
            return result
        if not file_path.is_file():
            result["message"] = f"Not a file: {path}"
            return result
        if file_path.suffix.lower() not in TEXT_EXTENSIONS:
            result["message"] = f"Unsupported file type: {file_path.suffix}. Only text-based files are supported."
            return result
        if file_path.stat().st_size > MAX_READ_SIZE:
            result["message"] = f"File too large ({file_path.stat().st_size / 1024 / 1024:.1f} MB). Maximum is 10 MB."
            return result

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            result["success"] = True
            result["content"] = content
            result["message"] = f"Read {len(content)} characters from {file_path.name}"
        except PermissionError:
            result["message"] = f"Permission denied: {path}"
        except Exception as e:
            result["message"] = f"Error reading file: {e}"

        return result

    def create_file(self, path: str, content: str, overwrite: bool = False) -> Dict:
        """Create a new text file."""
        result = {"success": False, "message": ""}

        if not permissions.is_path_allowed(path):
            result["message"] = "Cannot create files in this location."
            return result

        file_path = Path(path)
        if file_path.exists() and not overwrite:
            result["message"] = (
                f"File already exists: {path}. "
                "Use overwrite=True to replace it."
            )
            return result

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            result["success"] = True
            result["message"] = f"File created: {path}"
        except PermissionError:
            result["message"] = f"Permission denied creating file: {path}"
        except Exception as e:
            result["message"] = f"Error creating file: {e}"

        return result

    def get_file_info(self, path: str) -> Dict:
        """Get metadata about a file."""
        result = {"success": False, "info": {}, "message": ""}

        if not permissions.is_path_allowed(path):
            result["message"] = "Access to this file is not permitted."
            return result

        file_path = Path(path)
        if not file_path.exists():
            result["message"] = f"Path does not exist: {path}"
            return result

        try:
            stat_info = file_path.stat()
            result["success"] = True
            result["info"] = {
                "name": file_path.name,
                "path": str(file_path.resolve()),
                "extension": file_path.suffix,
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "size_bytes": stat_info.st_size,
                "size_human": self._human_size(stat_info.st_size),
                "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
                "readable": os.access(str(file_path), os.R_OK),
                "writable": os.access(str(file_path), os.W_OK),
            }
            result["message"] = f"File info retrieved for {file_path.name}"
        except Exception as e:
            result["message"] = f"Error getting file info: {e}"

        return result

    def delete_file(self, path: str) -> Dict:
        """Safely delete a file (restricted to allowed paths)."""
        result = {"success": False, "message": ""}

        if not permissions.is_path_allowed(path):
            result["message"] = "Cannot delete files in this location."
            return result

        file_path = Path(path)
        if not file_path.exists():
            result["message"] = f"File does not exist: {path}"
            return result
        if not file_path.is_file():
            result["message"] = f"Path is not a regular file: {path}"
            return result

        try:
            file_path.unlink()
            result["success"] = True
            result["message"] = f"Successfully deleted file: {file_path.name}"
        except PermissionError:
            result["message"] = f"Permission denied deleting file: {path}"
        except Exception as e:
            result["message"] = f"Error deleting file: {e}"

        return result

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
