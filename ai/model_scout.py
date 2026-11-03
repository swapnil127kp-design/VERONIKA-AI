"""
VERONIKA AI - Model Scout Engine
Automated scanner that tracks active free AI models across providers and
alerts the operator when a new high-speed free model becomes available.
"""
import json
import logging
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Endpoints that list models without requiring payment (key optional).
FREE_MODEL_SOURCES = {
    "omniroute": "http://127.0.0.1:20128/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "huggingface": (
        "https://huggingface.co/api/models"
        "?pipeline_tag=text-generation&sort=downloads&direction=-1&limit=30"
    ),
}

# Providers where a key is required to query the model list.
_KEY_ENV_FOR_SOURCE = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# Free-tier model name fragments worth flagging to the operator.
_FREE_HINTS = (
    "free", "flash", "lite", "mini", "qwen", "deepseek", "glm", "llama",
    "mistral", "gemma", "phi", "coder",
)


@dataclass
class ScoutModel:
    """A model discovered by the scout."""
    model_id: str
    provider: str
    free_hint: bool = False
    first_seen: str = ""
    raw: dict = field(default_factory=dict)


class ModelScout:
    """Background scanner that tracks free models and raises alerts.

    Usage:
        scout = ModelScout(on_alert=lambda text: print(text))
        scout.start()
        ...
        scout.stop()
    """

    def __init__(
        self,
        on_alert: Optional[Callable[[str], None]] = None,
        interval_seconds: int = 3600,
    ):
        self._on_alert = on_alert
        self._interval = max(60, int(interval_seconds))
        self._known: Dict[str, ScoutModel] = {}
        self._seen_ids: Set[str] = set()
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
        self._thread = threading.Thread(
            target=self._run, name="ModelScout", daemon=True
        )
        self._thread.start()
        logger.info("Model scout started (interval=%ss)", self._interval)

    def stop(self):
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("Model scout stopped")

    def _run(self):
        # Initial scan shortly after startup, then periodic rescans.
        while not self._stop_flag.is_set():
            try:
                self.scan_once()
            except Exception as e:
                logger.warning("Model scout scan failed: %s", e)
            self._stop_flag.wait(self._interval)

    # ── Scanning ──────────────────────────────────────────────

    def scan_once(self) -> List[ScoutModel]:
        """Scan every source once and return newly discovered models."""
        discovered: List[ScoutModel] = []
        for source, url in FREE_MODEL_SOURCES.items():
            try:
                models = self._fetch_source(source, url)
            except Exception as e:
                logger.debug("Scout source %s unavailable: %s", source, e)
                continue

            self._last_scan[source] = time.strftime("%Y-%m-%d %H:%M:%S")
            for model in models:
                with self._lock:
                    if model.model_id in self._seen_ids:
                        continue
                    self._seen_ids.add(model.model_id)
                    self._known[model.model_id] = model
                discovered.append(model)

        self._scan_count += 1
        self._announce(discovered)
        return discovered

    def _fetch_source(self, source: str, url: str) -> List[ScoutModel]:
        headers = {"Content-Type": "application/json"}

        env_name = _KEY_ENV_FOR_SOURCE.get(source)
        if env_name:
            import os
            key = os.environ.get(env_name)
            if not key:
                return []
            if source == "groq":
                headers["Authorization"] = f"Bearer {key}"
            elif source == "openrouter":
                headers["Authorization"] = f"Bearer {key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        return self._parse_source(source, payload)

    @staticmethod
    def _parse_source(source: str, payload) -> List[ScoutModel]:
        from datetime import datetime
        now = datetime.now().isoformat()
        results: List[ScoutModel] = []

        if source == "huggingface":
            for item in payload if isinstance(payload, list) else []:
                model_id = item.get("modelId") or item.get("id") or ""
                if not model_id:
                    continue
                results.append(ScoutModel(
                    model_id=model_id,
                    provider="huggingface",
                    free_hint=True,
                    first_seen=now,
                    raw={"downloads": item.get("downloads", 0)},
                ))
            return results

        # OpenAI-compatible /models payloads (omniroute, groq, openrouter)
        data = payload.get("data", []) if isinstance(payload, dict) else []
        for item in data:
            model_id = item.get("id") or item.get("name") or ""
            if not model_id:
                continue
            hint = any(h in model_id.lower() for h in _FREE_HINTS)
            if source == "openrouter":
                pricing = item.get("pricing", {}) or {}
                is_free = pricing.get("prompt") == "0" and pricing.get("completion") == "0"
                prompt = pricing.get("prompt", "1")
                try:
                    is_free = is_free or float(prompt) == 0.0
                except (TypeError, ValueError):
                    pass
                hint = hint or is_free
            results.append(ScoutModel(
                model_id=model_id,
                provider=source,
                free_hint=hint,
                first_seen=now,
                raw=item,
            ))
        return results

    def _announce(self, discovered: List[ScoutModel]):
        notable = [m for m in discovered if m.free_hint or m.provider in ("omniroute", "groq")]
        if not notable:
            return
        lines = []
        for m in notable[:5]:
            lines.append(
                f"Swapnil sir, market me ye naya high-speed free model [{m.model_id}] "
                f"available hai. Iska API link ye hai "
                f"({m.provider}): {FREE_MODEL_SOURCES.get(m.provider, 'n/a')}"
            )
        message = "\n".join(lines)
        logger.info("Model scout alert:\n%s", message)
        if self._on_alert:
            try:
                self._on_alert(message)
            except Exception as e:
                logger.warning("Model scout alert callback failed: %s", e)

    # ── Introspection ─────────────────────────────────────────

    def get_known_models(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "model_id": m.model_id,
                    "provider": m.provider,
                    "free_hint": m.free_hint,
                    "first_seen": m.first_seen,
                }
                for m in self._known.values()
            ]

    def get_last_scan_times(self) -> Dict[str, str]:
        return dict(self._last_scan)

    @property
    def scan_count(self) -> int:
        return self._scan_count
