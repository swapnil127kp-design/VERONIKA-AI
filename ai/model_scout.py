"""
VERONIKA AI - Model Scout (Phase 4)

Read-only live catalogue scout for the free-first policy (directive §5.3):
  - Queries official model-catalogue endpoints (OpenRouter public /models,
    Groq /models, Gemini /models) and local gateways (OmniRoute, Ollama).
  - Classifies each model: cost tier (free/paid/local), vision, tool support,
    context length.
  - Produces a recommendation report with a verification date and the exact
    source endpoint -- no invented links.

IMPORTANT: This module NEVER writes configuration. Activation of any scouted
model is a manual, owner-approved step (approval-before-activation).
"""
import json
import logging
import threading
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.config import config

logger = logging.getLogger(__name__)

_USER_AGENT = "VERONIKA-ModelScout/1.0 (personal assistant; free-first policy)"

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class ScoutedModel:
    """One model discovered from a live catalogue (or local gateway)."""
    provider: str
    model_id: str
    display_name: str = ""
    context_length: Optional[int] = None
    cost_tier: str = "unknown"      # free | paid | local | unknown
    vision: bool = False
    tools: bool = False
    verified_at: str = ""           # ISO-8601 UTC date of the live check
    source: str = ""                # official endpoint the data came from
    notes: str = ""

    def to_row(self) -> Dict[str, object]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "context_length": self.context_length,
            "cost_tier": self.cost_tier,
            "vision": self.vision,
            "tools": self.tools,
            "verified_at": self.verified_at,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass
class ScoutResult:
    """Result of scouting one provider (success or an honest failure)."""
    provider: str
    status: str                     # "ok" | "no_key" | "unreachable" | "error"
    detail: str = ""
    models: List[ScoutedModel] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fetch_json(url: str, headers: Optional[Dict[str, str]] = None,
                timeout: int = 20) -> object:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ═══════════════════════════════════════════════════════════════
# Provider-specific scouts
# ═══════════════════════════════════════════════════════════════

def scout_openrouter() -> ScoutResult:
    """OpenRouter's /models catalogue is public -- no key required."""
    try:
        data = _fetch_json(_OPENROUTER_MODELS_URL, {"User-Agent": _USER_AGENT})
    except Exception as e:
        return ScoutResult("openrouter", "unreachable", str(e))

    models: List[ScoutedModel] = []
    for m in data.get("data", []):
        if not isinstance(m, dict) or not m.get("id"):
            continue
        pricing = m.get("pricing") or {}
        prompt_price = str(pricing.get("prompt", "0") or "0")
        completion_price = str(pricing.get("completion", "0") or "0")
        try:
            is_free = float(prompt_price) == 0.0 and float(completion_price) == 0.0
        except ValueError:
            is_free = False

        arch = m.get("architecture") or {}
        modalities = arch.get("input_modalities") or []
        params = m.get("supported_parameters") or []

        models.append(ScoutedModel(
            provider="openrouter",
            model_id=m["id"],
            display_name=m.get("name", ""),
            context_length=m.get("context_length"),
            cost_tier="free" if is_free else "paid",
            vision="image" in modalities,
            tools="tools" in params or "tool_choice" in params,
            verified_at=_utc_now(),
            source=_OPENROUTER_MODELS_URL,
        ))
    return ScoutResult("openrouter", "ok", f"{len(models)} models", models)


def scout_groq() -> ScoutResult:
    """Groq /models -- requires a key; degrades to an honest no_key result."""
    api_key = config.get_api_key("groq")
    if not api_key:
        return ScoutResult("groq", "no_key",
                           "GROQ_API_KEY not configured; catalogue not checked")
    try:
        data = _fetch_json(
            _GROQ_MODELS_URL,
            {"Authorization": f"Bearer {api_key}", "User-Agent": _USER_AGENT},
        )
    except Exception as e:
        return ScoutResult("groq", "unreachable", str(e))

    models = []
    for m in data.get("data", []):
        if not isinstance(m, dict) or not m.get("id"):
            continue
        # Groq's catalogue does not expose per-model pricing; its free tier is
        # rate-limited rather than per-token, so tier is reported as "free_tier".
        models.append(ScoutedModel(
            provider="groq",
            model_id=m["id"],
            display_name=m.get("name") or m["id"],
            context_length=m.get("context_window"),
            cost_tier="free_tier",
            vision=False,
            tools="tools" in (m.get("capabilities") or {}) or True,
            verified_at=_utc_now(),
            source=_GROQ_MODELS_URL,
            notes="free tier is rate-limited, not per-token billed",
        ))
    return ScoutResult("groq", "ok", f"{len(models)} models", models)


def scout_gemini() -> ScoutResult:
    """Gemini /models -- requires a key; degrades to an honest no_key result."""
    api_key = config.get_api_key("google")
    if not api_key:
        return ScoutResult("google", "no_key",
                           "GOOGLE_API_KEY not configured; catalogue not checked")
    try:
        data = _fetch_json(
            _GEMINI_MODELS_URL,
            {"x-goog-api-key": api_key, "User-Agent": _USER_AGENT},
        )
    except Exception as e:
        return ScoutResult("google", "unreachable", str(e))

    models = []
    for m in data.get("models", []):
        if not isinstance(m, dict) or not m.get("name"):
            continue
        model_id = m["name"].split("/")[-1]
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        supported = m.get("supportedInputTypes") or []
        models.append(ScoutedModel(
            provider="google",
            model_id=model_id,
            display_name=m.get("displayName", ""),
            context_length=m.get("inputTokenLimit"),
            cost_tier="free_tier",  # Gemini free tier exists; paid beyond quota
            vision=any("image" in str(t).lower() for t in supported),
            tools=False,
            verified_at=_utc_now(),
            source=_GEMINI_MODELS_URL,
            notes="free tier with per-day quotas; paid beyond quota",
        ))
    return ScoutResult("google", "ok", f"{len(models)} models", models)


def scout_local() -> ScoutResult:
    """Probe local gateways (OmniRoute, Ollama) via their /models endpoints."""
    models: List[ScoutedModel] = []
    for name, base, key in (
        ("omniroute", config.get("ai", "omniroute_base_url",
                                 "http://127.0.0.1:20128/v1"), None),
        ("ollama", config.get("ai", "ollama_base_url",
                              "http://127.0.0.1:11434/v1"), None),
    ):
        url = f"{base.rstrip('/')}/models"
        try:
            data = _fetch_json(url, {"User-Agent": _USER_AGENT}, timeout=4)
        except Exception as e:
            models.append(ScoutedModel(
                provider=name, model_id="(unreachable)",
                cost_tier="local", verified_at=_utc_now(), source=url,
                notes=f"offline: {e}",
            ))
            continue
        items = data.get("data", []) if isinstance(data, dict) else []
        for m in items:
            if isinstance(m, dict) and m.get("id"):
                models.append(ScoutedModel(
                    provider=name, model_id=m["id"],
                    cost_tier="local", verified_at=_utc_now(), source=url,
                ))
    return ScoutResult("local", "ok", "local gateways probed", models)


# ═══════════════════════════════════════════════════════════════
# Report generation (recommendation format per directive §5.3)
# ═══════════════════════════════════════════════════════════════

def generate_report(max_per_provider: int = 12) -> Dict[str, object]:
    """Scout all providers and build a free-first recommendation report.

    Read-only: nothing here changes configuration. Activation of a scouted
    model is always a separate, owner-approved step.
    """
    results = [scout_openrouter(), scout_groq(), scout_gemini(), scout_local()]

    recommendations: List[Dict[str, object]] = []
    for res in results:
        usable = [m for m in res.models if m.model_id != "(unreachable)"]
        # Free-first ordering: free tier first, then biggest context.
        usable.sort(key=lambda m: (
            0 if m.cost_tier in ("free", "free_tier", "local") else 1,
            -(m.context_length or 0),
        ))
        for m in usable[:max_per_provider]:
            recommendations.append(m.to_row())

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy": "free-first; paid models listed but never auto-activated",
        "providers": [
            {"provider": r.provider, "status": r.status, "detail": r.detail,
             "model_count": len(r.models)}
            for r in results
        ],
        "recommendations": recommendations,
        "disclaimer": (
            "Data comes live from the official endpoints listed in 'source' on "
            "'generated_at'. Model availability/pricing changes without notice; "
            "re-run the scout before relying on any entry. No model is activated "
            "automatically -- owner approval is required."
        ),
    }


def format_report(report: Dict[str, object]) -> str:
    """Human-readable text rendering of generate_report()."""
    lines = [
        f"VERONIKA Model Scout — {report['generated_at']}",
        f"Policy: {report['policy']}",
        "",
        "Provider status:",
    ]
    for p in report["providers"]:
        lines.append(f"  {p['provider']:<12} {p['status']:<12} {p['detail']}")
    lines.append("")
    lines.append("Recommendations (free-first):")
    lines.append(f"  {'PROVIDER':<12} {'MODEL':<46} {'TIER':<10} "
                 f"{'CTX':<9} {'VIS':<4} {'TOOLS':<6}")
    for r in report["recommendations"]:
        ctx = r["context_length"]
        ctx_s = str(ctx) if ctx else "-"
        lines.append(
            f"  {r['provider']:<12} {str(r['model_id'])[:46]:<46} "
            f"{r['cost_tier']:<10} {ctx_s:<9} "
            f"{'Y' if r['vision'] else '-':<4} {'Y' if r['tools'] else '-':<6}"
        )
    lines.append("")
    lines.append(str(report["disclaimer"]))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Background watcher (UI integration)
# ═══════════════════════════════════════════════════════════════

class ModelScout:
    """Periodic background watcher that alerts when the free-model pool changes.

    Read-only: it never activates or configures anything. When new free
    models appear (or known ones disappear), it emits a human-readable alert
    through `on_alert` -- the UI wires that to a chat message + tray toast.
    """

    def __init__(self, on_alert, interval_seconds: int = 3600):
        self._on_alert = on_alert
        self._interval = max(600, int(interval_seconds))  # >= 10 min
        self._thread = None
        self._stop_flag = threading.Event()
        self._known_free: set = set()

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Model Scout watcher started (interval %ss)", self._interval)

    def stop(self):
        self._stop_flag.set()
        logger.info("Model Scout watcher stopped")

    def _loop(self):
        # First scan after a short grace period so app startup stays fast.
        if self._stop_flag.wait(30):
            return
        while not self._stop_flag.is_set():
            try:
                self._scan_once()
            except Exception as e:
                logger.warning("Model Scout scan failed: %s", e)
            if self._stop_flag.wait(self._interval):
                return

    def _scan_once(self):
        result = scout_openrouter()
        if result.status != "ok":
            return  # offline / blocked -- stay silent, try again next cycle
        free_now = {
            m.model_id for m in result.models if m.cost_tier == "free"
        }
        if not self._known_free:
            self._known_free = free_now
            return  # first successful scan is just the baseline
        added = free_now - self._known_free
        removed = self._known_free - free_now
        if not added and not removed:
            return
        lines = []
        if added:
            lines.append("New free models available:")
            lines += [f"  + {m}" for m in sorted(added)[:8]]
        if removed:
            lines.append("Free models no longer listed:")
            lines += [f"  - {m}" for m in sorted(removed)[:8]]
        lines.append("(Scout is read-only -- activate manually if you want one.)")
        self._known_free = free_now
        if self._on_alert:
            self._on_alert("\n".join(lines))
