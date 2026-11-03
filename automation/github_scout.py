"""
VERONIKA AI - GitHub Scout Engine
Background scanner that tracks trending / newly-released GitHub repositories
(AI agents, LLM tooling, MCP servers) and alerts the operator when something
noteworthy appears. Mirrors the design of `ai.model_scout`.
"""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_SEARCH = GITHUB_API + "/search/repositories"

# Topic-based searches surfaced to the operator. `{since}` is filled at scan time.
GITHUB_SOURCES: Dict[str, str] = {
    "ai-agents": "topic:ai-agents",
    "llm": "topic:llm",
    "mcp": "topic:mcp",
    "trending": "created:>{since}",
}

# Fragments worth flagging even below the star threshold.
_HOT_HINTS = (
    "agent", "mcp", "llm", "gpt", "rag", "langchain", "autonomous",
    "assistant", "copilot", "multimodal", "voice", "embeddings",
)


@dataclass
class ScoutRepo:
    """A repository discovered by the scout."""
    full_name: str
    html_url: str = ""
    description: str = ""
    stars: int = 0
    language: str = ""
    source: str = ""
    topics: List[str] = field(default_factory=list)
    first_seen: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "html_url": self.html_url,
            "description": self.description,
            "stars": self.stars,
            "language": self.language,
            "source": self.source,
            "topics": list(self.topics),
            "first_seen": self.first_seen,
        }


class GitHubScout:
    """Background scanner that tracks trending GitHub repos and raises alerts.

    Usage:
        scout = GitHubScout(on_alert=lambda text: print(text))
        scout.start()
        ...
        scout.stop()
    """

    def __init__(
        self,
        on_alert: Optional[Callable[[str], None]] = None,
        interval_seconds: int = 3600,
        min_stars: int = 50,
        token: Optional[str] = None,
        sources: Optional[Dict[str, str]] = None,
    ):
        self._on_alert = on_alert
        self._interval = max(300, int(interval_seconds))
        self._min_stars = max(0, int(min_stars))
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._sources = dict(sources or GITHUB_SOURCES)
        self._known: Dict[str, ScoutRepo] = {}
        self._seen: Set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._lock = threading.Lock()
        self._last_scan: Dict[str, str] = {}
        self._scan_count = 0

    # ── Lifecycle ─────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, name="GitHubScout", daemon=True)
        self._thread.start()
        logger.info("GitHub scout started (interval=%ss)", self._interval)

    def stop(self):
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("GitHub scout stopped")

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                self.scan_once()
            except Exception as e:  # noqa: BLE001
                logger.warning("GitHub scout scan failed: %s", e)
            self._stop_flag.wait(self._interval)

    # ── Scanning ──────────────────────────────────────────────

    def scan_once(self) -> List[ScoutRepo]:
        """Scan every source once and return newly discovered repos."""
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        discovered: List[ScoutRepo] = []

        for source, query in self._sources.items():
            resolved = query.replace("{since}", since)
            try:
                repos = self._fetch_source(resolved)
            except Exception as e:  # noqa: BLE001
                logger.debug("GitHub source %s unavailable: %s", source, e)
                continue

            self._last_scan[source] = time.strftime("%Y-%m-%d %H:%M:%S")
            for repo in repos:
                repo.source = source
                if repo.stars < self._min_stars and not self._is_hot(repo):
                    continue
                with self._lock:
                    if repo.full_name in self._seen:
                        continue
                    self._seen.add(repo.full_name)
                    self._known[repo.full_name] = repo
                discovered.append(repo)

        self._scan_count += 1
        self._announce(discovered)
        return discovered

    @staticmethod
    def _is_hot(repo: ScoutRepo) -> bool:
        haystack = f"{repo.full_name} {repo.description} {' '.join(repo.topics)}".lower()
        return any(h in haystack for h in _HOT_HINTS)

    def _fetch_source(self, query: str) -> List[ScoutRepo]:
        params = urllib.parse.urlencode({
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 25,
        })
        url = f"{GITHUB_SEARCH}?{params}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "VERONIKA-AI-GitHubScout",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"GitHub connection failed: {e.reason}")

        return self.parse_payload(payload)

    @staticmethod
    def parse_payload(payload) -> List[ScoutRepo]:
        """Parse a GitHub search-repositories JSON payload into ScoutRepo objects."""
        now = datetime.now().isoformat()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        results: List[ScoutRepo] = []
        for item in items:
            full_name = item.get("full_name") or item.get("name") or ""
            if not full_name:
                continue
            results.append(ScoutRepo(
                full_name=full_name,
                html_url=item.get("html_url", "") or "",
                description=(item.get("description") or "").strip(),
                stars=int(item.get("stargazers_count", 0) or 0),
                language=item.get("language", "") or "",
                topics=list(item.get("topics", []) or []),
                first_seen=now,
                raw={
                    "forks": item.get("forks_count", 0),
                    "open_issues": item.get("open_issues_count", 0),
                },
            ))
        return results

    def _announce(self, discovered: List[ScoutRepo]):
        if not discovered:
            return
        notable = sorted(discovered, key=lambda r: r.stars, reverse=True)[:5]
        lines = []
        for r in notable:
            desc = (r.description or "")[:140]
            lines.append(
                f"Swapnil sir, GitHub pe naya repo mila — {r.full_name} "
                f"({r.stars} stars, {r.language or 'n/a'}): {desc} {r.html_url}"
            )
        message = "\n".join(lines)
        logger.info("GitHub scout alert:\n%s", message)
        if self._on_alert:
            try:
                self._on_alert(message)
            except Exception as e:  # noqa: BLE001
                logger.warning("GitHub scout alert callback failed: %s", e)

    # ── Introspection ─────────────────────────────────────────

    def get_known_repos(self) -> List[dict]:
        with self._lock:
            return [r.to_dict() for r in self._known.values()]

    def get_last_scan_times(self) -> Dict[str, str]:
        return dict(self._last_scan)

    @property
    def scan_count(self) -> int:
        return self._scan_count
