"""
VERONIKA AI - AI Provider Manager (Multi-Agent Orchestrator)

Orchestrates multiple free/paid AI endpoints simultaneously:
  - Local OmniRoute   (http://127.0.0.1:20128/v1)   kr/qwen3-coder-next, deepseek, glm
  - Groq Cloud        (https://api.groq.com/openai/v1)  Llama 3.3 70B, ultra-fast
  - Google Gemini     (free tier)                  Vision + Flash
  - OpenRouter / HF   (free tier)
  - OpenAI            (paid fallback)

Dynamic task routing sends code tasks to code-specialist models, voice/chat to
fast free models, and screen analysis to vision-capable models -- with automatic
fallback down the chain when a provider errors or is unconfigured.
"""
import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from enum import Enum
from typing import Optional, List, Generator, Dict, Any, Tuple

from app.config import config
from ai.provider_base import (
    AIProviderBase,
    AIMessage,
    AIResponse,
    ModelConfig,
    ProviderStatus,
    VERONIKA_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Task routing types
# ======================================================================

class TaskType(Enum):
    """Categories of work that get routed to different models."""
    GENERAL = "general"
    CHAT = "chat"
    CODE = "code"
    VOICE = "voice"
    VISION = "vision"


# Default provider chains (ordered by preference, best first).
# set_provider() still pins the manual choice; routing is used when enabled.
DEFAULT_ROUTING: Dict[TaskType, List[str]] = {
    TaskType.CODE: ["omniroute", "groq", "openai", "google"],
    TaskType.CHAT: ["groq", "google", "openai", "omniroute"],
    TaskType.VOICE: ["groq", "google", "openai"],
    TaskType.VISION: ["google", "openai"],
    TaskType.GENERAL: ["google", "groq", "openai", "omniroute"],
}

# Per-task model overrides keyed by provider name.
DEFAULT_TASK_MODELS: Dict[TaskType, Dict[str, str]] = {
    TaskType.CODE: {
        "omniroute": "kr/qwen3-coder-next",
        "groq": "llama-3.3-70b-versatile",
        "openai": "gpt-4o",
        "google": "gemini-flash-latest",
    },
    TaskType.CHAT: {
        "groq": "llama-3.3-70b-versatile",
        "google": "gemini-flash-latest",
        "openai": "gpt-4o-mini",
        "omniroute": "agentrouter/deepseek-v4-flash",
    },
    TaskType.VOICE: {
        "groq": "llama-3.3-70b-versatile",
        "google": "gemini-flash-latest",
    },
    TaskType.VISION: {
        "google": "gemini-flash-latest",
        "openai": "gpt-4o",
    },
    TaskType.GENERAL: {
        "google": "gemini-flash-latest",
        "groq": "llama-3.3-70b-versatile",
        "openai": "gpt-4o",
        "omniroute": "glm-5.3",
    },
}

# Keywords used to auto-classify an incoming user message into a TaskType.
_CODE_HINTS = re.compile(
    r"\b(code|debug|bug|error|traceback|function|class |def |import |compile|"
    r"python|javascript|typescript|java\b|c\+\+|rust|golang|sql|regex|refactor|"
    r"unit test|stack trace|api call|syntax|linter|compiler|git conflict)\b",
    re.IGNORECASE,
)
_VOICE_HINTS = re.compile(
    r"\b(speak|say|tell me|listen|voice|read aloud|repeat after|quick reply)\b",
    re.IGNORECASE,
)


# ======================================================================
# OpenAI-compatible provider (urllib only -- works without openai pkg)
# ======================================================================

class OpenAICompatibleProvider(AIProviderBase):
    """Generic provider speaking the OpenAI /chat/completions protocol.

    Uses only urllib so it functions even when the `openai` package is absent.
    Subclasses just supply base_url, key env, and defaults.
    """

    name: str = "OpenAI Compatible"
    provider_key: str = "generic"
    base_url: str = ""
    default_model: str = ""
    needs_key: bool = True
    supports_images: bool = False
    # Cost classification for the free-first policy: "free" | "local" | "paid"
    cost_tier: str = "paid"
    # Hardcoded candidate models used when live /models discovery fails
    fallback_models: List[str] = []

    # Cached health/model discovery (avoids probing endpoints on every call)
    _STATUS_TTL = 30.0
    _MODELS_TTL = 300.0

    def __init__(self):
        self._cancelled = False
        self._status_cache: Optional[Tuple[ProviderStatus, float]] = None
        self._models_cache: Optional[Tuple[List[str], float]] = None

    def get_name(self) -> str:
        return self.name

    def _get_api_key(self) -> Optional[str]:
        key = config.get_api_key(self.provider_key)
        if key:
            return key
        env_name = self.provider_key.upper() + "_API_KEY"
        return os.environ.get(env_name) or None

    def _probe_endpoint(self, timeout: float = 2.0) -> bool:
        """Cheap reachability probe against GET /models."""
        try:
            url = f"{self.base_url.rstrip('/')}/models"
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=timeout):
                return True
        except Exception:
            return False

    def get_status(self) -> ProviderStatus:
        if not self.needs_key or self._get_api_key():
            now = time.monotonic()
            if self._status_cache and now - self._status_cache[1] < self._STATUS_TTL:
                return self._status_cache[0]
            status = (
                ProviderStatus.AVAILABLE
                if self._probe_endpoint()
                else ProviderStatus.UNAVAILABLE
            )
            self._status_cache = (status, now)
            return status
        return ProviderStatus.NO_API_KEY

    def _fetch_models(self) -> Optional[List[str]]:
        """Live model discovery via GET /models. Returns None on failure."""
        try:
            url = f"{self.base_url.rstrip('/')}/models"
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            items = body.get("data", []) if isinstance(body, dict) else []
            models = [
                m.get("id") for m in items if isinstance(m, dict) and m.get("id")
            ]
            return models or None
        except Exception:
            return None

    def get_available_models(self) -> List[str]:
        if self._models_cache:
            models, ts = self._models_cache
            if time.monotonic() - ts < self._MODELS_TTL:
                return models
        live = self._fetch_models()
        if live:
            self._models_cache = (live, time.monotonic())
            return live
        return list(self.fallback_models)

    def supports_vision(self) -> bool:
        return self.supports_images

    def capabilities(self) -> Dict[str, Any]:
        return {
            "streaming": True,
            "tools": False,
            "vision": self.supports_images,
            "context_limit": None,
        }

    def cancel(self):
        self._cancelled = True

    def _resolve_model(self, model_config: Optional[ModelConfig]) -> str:
        if model_config and model_config.model:
            return model_config.model
        return self.default_model

    def _build_payload(
        self,
        messages: List[AIMessage],
        model: str,
        model_config: Optional[ModelConfig],
        stream: bool,
    ) -> dict:
        cfg = model_config or ModelConfig()
        out_messages: List[dict] = []
        for msg in messages:
            if msg.role == "system":
                out_messages.append({"role": "system", "content": msg.content})
            elif msg.image_data and self.supports_images:
                b64 = base64.b64encode(msg.image_data).decode("utf-8")
                out_messages.append({
                    "role": msg.role,
                    "content": [
                        {"type": "text", "text": msg.content},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{msg.image_mime or 'image/png'};base64,{b64}"
                                )
                            },
                        },
                    ],
                })
            else:
                out_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": model,
            "messages": out_messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        if stream:
            payload["stream"] = True
        return payload

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = self._get_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _post(self, path: str, payload: dict, timeout: int = 60):
        url = f"{self.base_url.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        return urllib.request.urlopen(req, timeout=timeout)

    def send_message(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        model = self._resolve_model(model_config)
        if not model:
            return AIResponse(content="", error=f"{self.name}: no model configured.")

        payload = self._build_payload(messages, model, model_config, stream=False)
        try:
            with self._post("/chat/completions", payload) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            choices = body.get("choices", [])
            if not choices:
                return AIResponse(content="", error=f"{self.name}: empty response.")
            message = choices[0].get("message", {})
            content = message.get("content") or ""
            usage = body.get("usage", {}) or {}
            return AIResponse(
                content=content,
                model=body.get("model", model),
                finish_reason=choices[0].get("finish_reason", ""),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            )
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            logger.error("%s HTTP %s: %s", self.name, e.code, err_msg)
            return AIResponse(content="", error=f"{self.name} ({e.code}): {err_msg}")
        except Exception as e:
            logger.error("%s request failed: %s", self.name, e)
            return AIResponse(content="", error=f"{self.name}: {e}")

    def send_message_stream(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> Generator[str, None, None]:
        model = self._resolve_model(model_config)
        if not model:
            yield f"[Error: {self.name}: no model configured.]"
            return

        self._cancelled = False
        payload = self._build_payload(messages, model, model_config, stream=True)
        try:
            with self._post("/chat/completions", payload, timeout=120) as resp:
                buffer = ""
                while True:
                    if self._cancelled:
                        break
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {}) or {}
                        piece = delta.get("content")
                        if piece:
                            yield piece
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            yield f"\n[Error: {self.name} ({e.code}): {err_msg}]"
        except Exception as e:
            logger.error("%s streaming failed: %s", self.name, e)
            yield f"\n[Error: {self.name}: {e}]"


class OmniRouteProvider(OpenAICompatibleProvider):
    """Local OmniRoute gateway (localhost:20128) -- free models, no key required.

    Model identifiers below are owner-supplied candidates, not verified models;
    live discovery via GET /models takes precedence when the gateway is running.
    """

    name = "OmniRoute (Local)"
    provider_key = "omniroute"
    base_url = "http://127.0.0.1:20128/v1"
    default_model = "kr/qwen3-coder-next"
    needs_key = False
    cost_tier = "local"
    fallback_models = [
        "kr/qwen3-coder-next",
        "agentrouter/deepseek-v4-flash",
        "glm-5.3",
    ]

    def __init__(self):
        super().__init__()
        self.base_url = config.get("ai", "omniroute_base_url", self.base_url)
        self.default_model = config.get("ai", "omniroute_model", self.default_model)


class GroqProvider(OpenAICompatibleProvider):
    """Groq Cloud -- ultra-fast free-tier Llama models."""

    name = "Groq"
    provider_key = "groq"
    base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"
    cost_tier = "free"
    fallback_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
        "mixtral-8x7b-32768",
    ]


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter -- aggregator with a free-tier model pool."""

    name = "OpenRouter"
    provider_key = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"
    cost_tier = "free"  # default model is a :free variant; paid models exist
    fallback_models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ]


class OllamaProvider(OpenAICompatibleProvider):
    """Optional local Ollama server (OpenAI-compatible endpoint).

    Not part of the default routing chains; pin it with set_provider("ollama")
    or add it to a task chain when local inference is desired.
    """

    name = "Ollama (Local)"
    provider_key = "ollama"
    base_url = "http://127.0.0.1:11434/v1"
    default_model = "llama3.2"
    needs_key = False
    cost_tier = "local"
    fallback_models = [
        "llama3.2",
        "llama3.1:8b",
        "qwen2.5-coder:7b",
    ]

    def __init__(self):
        super().__init__()
        self.base_url = config.get("ai", "ollama_base_url", self.base_url)
        self.default_model = config.get("ai", "ollama_model", self.default_model)


# ======================================================================
# Paid / SDK-backed providers
# ======================================================================

class OpenAIProvider(AIProviderBase):
    """OpenAI API provider (GPT-4o, etc.)."""

    cost_tier = "paid"

    def __init__(self):
        self._client = None
        self._cancelled = False

    def _get_client(self):
        if self._client is None:
            api_key = config.get_api_key("openai")
            if not api_key:
                return None
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except ImportError:
                logger.error("openai package not installed")
                return None
            except Exception as e:
                logger.error("Failed to create OpenAI client: %s", e)
                return None
        return self._client

    def get_name(self) -> str:
        return "OpenAI"

    def get_status(self) -> ProviderStatus:
        api_key = config.get_api_key("openai")
        if not api_key:
            return ProviderStatus.NO_API_KEY
        client = self._get_client()
        if client is None:
            return ProviderStatus.ERROR
        return ProviderStatus.AVAILABLE

    def _build_messages(self, messages: List[AIMessage]) -> List[dict]:
        result = []
        for msg in messages:
            if msg.image_data and msg.role == "user":
                b64 = base64.b64encode(msg.image_data).decode("utf-8")
                content = [
                    {"type": "text", "text": msg.content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{msg.image_mime or 'image/png'};base64,{b64}"
                        },
                    },
                ]
                result.append({"role": msg.role, "content": content})
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def send_message(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        client = self._get_client()
        if not client:
            return AIResponse(
                content="",
                error="OpenAI client not available. Please configure your API key in Settings.",
            )

        cfg = model_config or ModelConfig()
        model = cfg.model or config.get("ai", "openai_model", "gpt-4o")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=self._build_messages(messages),
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            choice = response.choices[0]
            return AIResponse(
                content=choice.message.content or "",
                model=response.model,
                finish_reason=choice.finish_reason or "",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            return AIResponse(content="", error=str(e))

    def send_message_stream(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> Generator[str, None, None]:
        client = self._get_client()
        if not client:
            yield "[Error: OpenAI client not available. Please configure your API key in Settings.]"
            return

        cfg = model_config or ModelConfig()
        model = cfg.model or config.get("ai", "openai_model", "gpt-4o")
        self._cancelled = False

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=self._build_messages(messages),
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                stream=True,
            )
            for chunk in stream:
                if self._cancelled:
                    break
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error("OpenAI streaming error: %s", e)
            yield f"\n[Error: {e}]"

    def get_available_models(self) -> List[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    def supports_vision(self) -> bool:
        model = config.get("ai", "openai_model", "gpt-4o")
        return model in ("gpt-4o", "gpt-4o-mini", "gpt-4-turbo")

    def capabilities(self) -> Dict[str, Any]:
        return {
            "streaming": True,
            "tools": True,
            "vision": self.supports_vision(),
            "context_limit": None,
        }

    def cancel(self):
        self._cancelled = True


class GoogleProvider(AIProviderBase):
    """Google Gemini API provider with both SDK and native REST support."""

    cost_tier = "free"  # Gemini free tier; paid tiers exist beyond quota

    def __init__(self):
        self._model_instance = None
        self._cancelled = False

    def _get_api_key(self) -> Optional[str]:
        return config.get_api_key("google")

    def _get_model_name(self, model_name: Optional[str] = None) -> str:
        name = model_name or config.get("ai", "google_model", "gemini-flash-latest")
        if name.startswith("models/"):
            name = name[len("models/"):]
        return name

    def get_name(self) -> str:
        return "Google Gemini"

    def get_status(self) -> ProviderStatus:
        api_key = self._get_api_key()
        if not api_key:
            return ProviderStatus.NO_API_KEY
        return ProviderStatus.AVAILABLE

    def _format_messages_for_rest(self, messages: List[AIMessage]) -> tuple:
        system_text = VERONIKA_SYSTEM_PROMPT
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_text = msg.content
                continue

            role = "user" if msg.role == "user" else "model"
            parts = []

            if msg.content:
                parts.append({"text": msg.content})

            if msg.image_data:
                b64_img = base64.b64encode(msg.image_data).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": msg.image_mime or "image/png",
                        "data": b64_img,
                    }
                })

            if parts:
                contents.append({"role": role, "parts": parts})

        return system_text, contents

    def _call_rest_api(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        api_key = self._get_api_key()
        if not api_key:
            return AIResponse(
                content="",
                error="Google Gemini API key not configured. Set it in Settings or .env.",
            )

        cfg = model_config or ModelConfig()
        model_name = self._get_model_name(cfg.model)
        system_text, contents = self._format_messages_for_rest(messages)

        # Security: pass the API key via header, never the URL query string
        # (keys in URLs leak into proxy/server access logs).
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
            },
        }

        for attempt in range(2):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))

                candidates = resp_json.get("candidates", [])
                if not candidates:
                    return AIResponse(content="", error="No response received from Gemini.")

                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                usage_meta = resp_json.get("usageMetadata", {}) or {}
                return AIResponse(
                    content=text,
                    model=model_name,
                    usage={
                        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                    },
                )

            except urllib.error.HTTPError as e:
                try:
                    err_body = json.loads(e.read().decode("utf-8"))
                    err_msg = err_body.get("error", {}).get("message", str(e))
                except Exception:
                    err_msg = str(e)
                logger.error("Gemini REST API error: %s", err_msg)
                return AIResponse(content="", error=f"Gemini API error ({e.code}): {err_msg}")
            except Exception as e:
                logger.warning("Gemini request attempt %d failed: %s", attempt + 1, e)
                if attempt < 1:
                    import time
                    time.sleep(1.0)
                else:
                    logger.error("Gemini request failed: %s", e)
                    return AIResponse(content="", error=str(e))

    def send_message(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> AIResponse:
        try:
            import google.generativeai as genai
            api_key = self._get_api_key()
            if not api_key:
                return AIResponse(content="", error="Google Gemini API key not configured.")
            genai.configure(api_key=api_key)
            cfg = model_config or ModelConfig()
            model_name = self._get_model_name(cfg.model)
            model = genai.GenerativeModel(model_name)
            parts = []
            for msg in messages:
                if msg.image_data:
                    parts.append({
                        "mime_type": msg.image_mime or "image/png",
                        "data": msg.image_data,
                    })
                if msg.content:
                    parts.append(msg.content)
            response = model.generate_content(
                parts,
                generation_config={
                    "temperature": cfg.temperature,
                    "max_output_tokens": cfg.max_tokens,
                },
            )
            return AIResponse(content=response.text, model=model_name)
        except Exception as e:
            logger.info("Using Gemini native REST endpoint (SDK fallback: %s)", e)
            return self._call_rest_api(messages, model_config)

    def _stream_rest_api(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> Generator[str, None, None]:
        """Stream from the Gemini REST endpoint via server-sent events."""
        api_key = self._get_api_key()
        if not api_key:
            yield "\n[Error: Google Gemini API key not configured.]"
            return

        cfg = model_config or ModelConfig()
        model_name = self._get_model_name(cfg.model)
        system_text, contents = self._format_messages_for_rest(messages)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:streamGenerateContent?alt=sse"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                buffer = ""
                while True:
                    if self._cancelled:
                        break
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        if not data_str:
                            continue
                        try:
                            obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        candidates = obj.get("candidates", [])
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                        if text:
                            yield text
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            logger.error("Gemini REST streaming error: %s", err_msg)
            yield f"\n[Error: Gemini API error ({e.code}): {err_msg}]"
        except Exception as e:
            logger.error("Gemini REST streaming failed: %s", e)
            yield f"\n[Error: Gemini streaming failed: {e}]"

    def send_message_stream(
        self, messages: List[AIMessage], model_config: Optional[ModelConfig] = None
    ) -> Generator[str, None, None]:
        """Real token streaming: SDK stream first, native REST SSE fallback."""
        self._cancelled = False

        try:
            import google.generativeai as genai
        except ImportError:
            genai = None

        if genai is not None and self._get_api_key():
            genai.configure(api_key=self._get_api_key())
            cfg = model_config or ModelConfig()
            model_name = self._get_model_name(cfg.model)
            model = genai.GenerativeModel(model_name)
            parts = []
            for msg in messages:
                if msg.image_data:
                    parts.append({
                        "mime_type": msg.image_mime or "image/png",
                        "data": msg.image_data,
                    })
                if msg.content:
                    parts.append(msg.content)

            produced = False
            try:
                stream = model.generate_content(
                    parts,
                    stream=True,
                    generation_config={
                        "temperature": cfg.temperature,
                        "max_output_tokens": cfg.max_tokens,
                    },
                )
                for chunk in stream:
                    if self._cancelled:
                        break
                    try:
                        text = chunk.text
                    except Exception:
                        text = ""
                    if text:
                        produced = True
                        yield text
                if produced:
                    return
            except Exception as e:
                if produced:
                    yield f"\n[Error: Gemini stream interrupted: {e}]"
                    return
                logger.info(
                    "Gemini SDK streaming unavailable (%s); using REST SSE", e
                )

        yield from self._stream_rest_api(messages, model_config)

    def get_available_models(self) -> List[str]:
        return [
            "gemini-flash-latest",
            "gemini-pro-latest",
            "gemini-2.5-flash-lite",
            "gemini-3.8-flash",
        ]

    def supports_vision(self) -> bool:
        return True

    def capabilities(self) -> Dict[str, Any]:
        return {
            "streaming": True,
            "tools": False,
            "vision": True,
            "context_limit": None,
        }

    def cancel(self):
        self._cancelled = True


# ======================================================================
# Task router -- decides which provider/model handles a request
# ======================================================================

class TaskRouter:
    """Maps a TaskType to the best available (provider, model) pair."""

    def __init__(self, providers: Dict[str, AIProviderBase]):
        self._providers = providers
        self._routing: Dict[TaskType, List[str]] = dict(DEFAULT_ROUTING)
        self._task_models: Dict[TaskType, Dict[str, str]] = {
            t: dict(m) for t, m in DEFAULT_TASK_MODELS.items()
        }

    @staticmethod
    def classify(text: str, has_image: bool = False) -> TaskType:
        """Heuristic classification of a user message into a TaskType."""
        if has_image:
            return TaskType.VISION
        if _CODE_HINTS.search(text or ""):
            return TaskType.CODE
        if _VOICE_HINTS.search(text or ""):
            return TaskType.VOICE
        return TaskType.GENERAL

    def set_chain(self, task: TaskType, providers: List[str]):
        self._routing[task] = [p for p in providers if p in self._providers]

    def get_chain(self, task: TaskType) -> List[str]:
        chain = self._routing.get(task, [])
        return [p for p in chain if p in self._providers]

    def set_model(self, task: TaskType, provider: str, model: str):
        self._task_models.setdefault(task, {})[provider] = model

    def get_model(self, task: TaskType, provider: str) -> Optional[str]:
        return self._task_models.get(task, {}).get(provider)

    def resolve(
        self, task: TaskType, exclude: Optional[set] = None
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Return the first available (provider_name, model) for a task.

        `exclude` lets the orchestrator skip providers that already failed.
        """
        exclude = exclude or set()
        for name in self.get_chain(task):
            if name in exclude:
                continue
            provider = self._providers.get(name)
            if provider is None:
                continue
            # Capability-aware routing: vision tasks require vision support.
            if task == TaskType.VISION and not provider.supports_vision():
                continue
            try:
                status = provider.get_status()
            except Exception:
                continue
            if status != ProviderStatus.AVAILABLE:
                continue
            return name, self.get_model(task, name)
        return None


# ======================================================================
# ProviderManager -- the multi-agent orchestrator
# ======================================================================

class ProviderManager:
    """Multi-agent orchestrator over all registered AI providers."""

    def __init__(self, persona_manager=None, entity_manager=None):
        self._providers: Dict[str, AIProviderBase] = {
            "openai": OpenAIProvider(),
            "google": GoogleProvider(),
            "groq": GroqProvider(),
            "omniroute": OmniRouteProvider(),
            "openrouter": OpenRouterProvider(),
            "ollama": OllamaProvider(),
        }
        self._current_provider_name: str = config.get("ai", "provider", "openai")
        self.routing_enabled: bool = config.get("ai", "dynamic_routing", True)
        # Free-first policy: when enabled, paid providers are never selected
        # silently (directive §4.5).
        self.free_only: bool = config.get("ai", "free_only", False)
        self._usage_totals: Dict[str, Dict[str, int]] = {}

        if persona_manager is None:
            from ai.persona_manager import PersonaManager
            persona_manager = PersonaManager.get_instance()
        self.persona_manager = persona_manager

        if entity_manager is None:
            try:
                from ai.entity_manager import EntityManager
                entity_manager = EntityManager.get_instance()
            except Exception:
                entity_manager = None
        self.entity_manager = entity_manager

        self.router = TaskRouter(self._providers)
        self._last_routed: Dict[str, Any] = {}

    # -- Provider selection ----------------------------------------------

    @property
    def current_provider(self) -> Optional[AIProviderBase]:
        return self._providers.get(self._current_provider_name)

    @property
    def current_provider_name(self) -> str:
        return self._current_provider_name

    def set_provider(self, name: str):
        if name in self._providers:
            self._current_provider_name = name
            config.set("ai", "provider", name)
            config.save()
            logger.info("AI provider set to: %s", name)

    def get_provider_status(self) -> ProviderStatus:
        provider = self.current_provider
        if not provider:
            return ProviderStatus.UNAVAILABLE
        return provider.get_status()

    def get_all_providers(self) -> Dict[str, ProviderStatus]:
        return {name: p.get_status() for name, p in self._providers.items()}

    def get_provider_names(self) -> List[str]:
        return list(self._providers.keys())

    def get_last_routing(self) -> dict:
        return dict(self._last_routed)

    # -- Usage reporting ---------------------------------------------------

    def _record_usage(self, provider_name: str, usage: Optional[Dict[str, int]]):
        """Accumulate per-provider usage totals (in-memory, per session)."""
        totals = self._usage_totals.setdefault(
            provider_name, {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0}
        )
        totals["requests"] += 1
        if usage:
            totals["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
            totals["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)

    def get_usage_summary(self) -> Dict[str, Dict[str, int]]:
        """Return per-provider usage totals for the current session."""
        return {name: dict(totals) for name, totals in self._usage_totals.items()}

    # -- Message assembly ------------------------------------------------

    def _build_message_list(
        self,
        user_message: str,
        context_messages: Optional[List[dict]] = None,
        image_data: Optional[bytes] = None,
        image_mime: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> List[AIMessage]:
        prompt = (
            system_prompt
            or getattr(self.entity_manager, "system_prompt", None)
            or getattr(self.persona_manager, "system_prompt", None)
            or VERONIKA_SYSTEM_PROMPT
        )
        messages = [AIMessage(role="system", content=prompt)]

        if context_messages:
            for m in context_messages[-20:]:
                messages.append(AIMessage(role=m["role"], content=m["content"]))

        messages.append(AIMessage(
            role="user",
            content=user_message,
            image_data=image_data,
            image_mime=image_mime,
        ))
        return messages

    def _build_chain(self, task: TaskType) -> List[str]:
        chain: List[str] = []
        if self.routing_enabled:
            chain = self.router.get_chain(task)
        if self._current_provider_name not in chain:
            chain.append(self._current_provider_name)
        return chain

    # -- Public send API (backward compatible) ----------------------------

    def send_message(
        self,
        user_message: str,
        context_messages: List[dict] = None,
        image_data: Optional[bytes] = None,
        image_mime: Optional[str] = None,
        task: Optional[TaskType] = None,
        model_config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Send a message, routed by task type with automatic fallback."""
        if task is None:
            task = TaskRouter.classify(user_message, has_image=image_data is not None)

        messages = self._build_message_list(
            user_message, context_messages, image_data, image_mime, system_prompt
        )

        chain = self._build_chain(task)
        last_error = "No provider available."
        for name in chain:
            p = self._providers.get(name)
            if p is None:
                continue
            status = p.get_status()
            if status == ProviderStatus.NO_API_KEY:
                last_error = (
                    f"No API key configured for {p.get_name()}. "
                    f"Please enter your API key in Settings -> AI Configuration."
                )
                continue
            if status != ProviderStatus.AVAILABLE:
                last_error = f"{p.get_name()} is not available: {status.value}"
                continue
            if self.free_only and getattr(p, "cost_tier", "paid") == "paid":
                last_error = (
                    f"{p.get_name()} is a paid provider and free-only mode is "
                    f"enabled. Disable free-only mode in Settings to use it."
                )
                continue

            use_cfg = self._config_for(task, name, model_config)
            resp = p.send_message(messages, use_cfg)
            if not resp.is_error:
                self._last_routed = {
                    "task": task.value,
                    "provider": name,
                    "model": resp.model or (use_cfg.model if use_cfg else ""),
                    "cost_tier": getattr(p, "cost_tier", "paid"),
                }
                self._record_usage(name, resp.usage)
                return resp
            last_error = resp.error
            logger.warning("Provider %s failed, trying fallback: %s", name, last_error)

        return AIResponse(content="", error=last_error)

    def send_message_stream(
        self,
        user_message: str,
        context_messages: List[dict] = None,
        image_data: Optional[bytes] = None,
        image_mime: Optional[str] = None,
        task: Optional[TaskType] = None,
        model_config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream a response, routed by task type with automatic fallback."""
        if task is None:
            task = TaskRouter.classify(user_message, has_image=image_data is not None)

        messages = self._build_message_list(
            user_message, context_messages, image_data, image_mime, system_prompt
        )

        chain = self._build_chain(task)
        last_error = "No provider available."
        for name in chain:
            p = self._providers.get(name)
            if p is None:
                continue
            status = p.get_status()
            if status == ProviderStatus.NO_API_KEY:
                last_error = (
                    f"No API key configured for {p.get_name()}. "
                    f"Please enter your API key in Settings -> AI Configuration."
                )
                continue
            if status != ProviderStatus.AVAILABLE:
                last_error = f"{p.get_name()} is not available: {status.value}"
                continue

            if self.free_only and getattr(p, "cost_tier", "paid") == "paid":
                last_error = (
                    f"{p.get_name()} is a paid provider and free-only mode is "
                    f"enabled. Disable free-only mode in Settings to use it."
                )
                continue

            use_cfg = self._config_for(task, name, model_config)
            self._last_routed = {
                "task": task.value,
                "provider": name,
                "model": use_cfg.model if use_cfg else "",
                "cost_tier": getattr(p, "cost_tier", "paid"),
            }

            produced = False
            for chunk in p.send_message_stream(messages, use_cfg):
                produced = True
                yield chunk
            if produced:
                self._record_usage(name, None)
                return
            last_error = f"{p.get_name()} produced no output."

        yield f"\n[Error: {last_error}]"

    def _config_for(
        self, task: TaskType, provider_name: str, model_config: Optional[ModelConfig]
    ) -> Optional[ModelConfig]:
        """Merge the routed model override into an explicit model_config."""
        if model_config and model_config.model:
            return model_config
        routed_model = self.router.get_model(task, provider_name)
        if not routed_model:
            return model_config
        base = model_config or ModelConfig()
        return ModelConfig(
            model=routed_model,
            temperature=base.temperature,
            max_tokens=base.max_tokens,
            stream=base.stream,
        )

    def cancel(self):
        for p in self._providers.values():
            try:
                p.cancel()
            except Exception:
                pass

    # -- Action parsing (unchanged) --------------------------------------

    def parse_action(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract a structured action from the AI response if present."""
        if not response_text:
            return None

        code_blocks = re.findall(
            r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL
        )
        for block in code_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and "action" in data:
                    return data
            except json.JSONDecodeError:
                pass

        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(response_text):
            idx = response_text.find('{', pos)
            if idx == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(response_text[idx:])
                if isinstance(obj, dict) and "action" in obj:
                    return obj
                pos = idx + 1
            except json.JSONDecodeError:
                pos = idx + 1

        return None
