"""
Tests for the multi-provider AI system (Phase 2).

Covers: real SSE streaming (OpenAI-compatible + Gemini REST), live model
discovery with fallback, provider health checks, free-only routing policy,
capability-aware vision routing, and usage reporting.
All network access is mocked -- no real API calls are made.
"""
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from ai.provider_base import AIMessage, AIResponse, ProviderStatus
from ai.provider_manager import (
    GoogleProvider,
    GroqProvider,
    OmniRouteProvider,
    ProviderManager,
    TaskRouter,
    TaskType,
)


class FakeSSE:
    """Minimal file-like SSE response body for urllib mocking."""

    def __init__(self, chunks):
        self._buf = "".join(chunks).encode("utf-8")

    def read(self, n=-1):
        if self._buf:
            out, self._buf = self._buf[:n], self._buf[n:]
            return out
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sse_openai(chunks, done=True):
    """Build OpenAI-compatible SSE data lines."""
    lines = []
    for c in chunks:
        lines.append(
            "data: " + json.dumps({"choices": [{"delta": {"content": c}}]}) + "\n\n"
        )
    if done:
        lines.append("data: [DONE]\n\n")
    return lines


def sse_gemini(chunks):
    """Build Gemini streamGenerateContent SSE data lines."""
    lines = []
    for c in chunks:
        obj = {"candidates": [{"content": {"parts": [{"text": c}]}}]}
        lines.append("data: " + json.dumps(obj) + "\n\n")
    return lines


class TestOpenAICompatibleStreaming:
    """Real token streaming over the OpenAI-compatible SSE protocol."""

    def test_sse_streaming_yields_tokens_in_order(self):
        p = GroqProvider()
        p._get_api_key = lambda: "test-key"
        with patch(
            "urllib.request.urlopen",
            return_value=FakeSSE(sse_openai(["Hello", ", ", "world"])),
        ):
            out = list(p.send_message_stream([AIMessage(role="user", content="hi")]))
        assert "".join(out) == "Hello, world"

    def test_stream_done_terminates(self):
        p = GroqProvider()
        p._get_api_key = lambda: "test-key"
        chunks = sse_openai(["a"]) + [
            "data: " + json.dumps({"choices": [{"delta": {"content": "IGNORED"}}]}) + "\n\n"
        ]
        with patch("urllib.request.urlopen", return_value=FakeSSE(chunks)):
            out = list(p.send_message_stream([AIMessage(role="user", content="hi")]))
        assert "".join(out) == "a"


class TestModelDiscovery:
    """Live /models discovery with hardcoded fallback."""

    def test_live_models_preferred_over_fallback(self):
        p = GroqProvider()
        body = {"data": [{"id": "llama-3.3-70b-versatile"}, {"id": "brand-new-model"}]}
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = json.dumps(body).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=resp):
            models = p.get_available_models()
        assert "brand-new-model" in models

    def test_fallback_when_discovery_fails(self):
        p = GroqProvider()
        with patch("urllib.request.urlopen", side_effect=Exception("offline")):
            models = p.get_available_models()
        assert "llama-3.3-70b-versatile" in models
        assert models[0] == "llama-3.3-70b-versatile"

    def test_models_cached(self):
        p = GroqProvider()
        body = {"data": [{"id": "m1"}]}
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = json.dumps(body).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=resp) as mock_urlopen:
            p.get_available_models()
            p.get_available_models()
        assert mock_urlopen.call_count == 1


class TestProviderHealth:
    """Endpoint health checks with TTL caching."""

    def test_omniroute_offline_when_unreachable(self):
        p = OmniRouteProvider()
        with patch("urllib.request.urlopen", side_effect=Exception("refused")):
            assert p.get_status() == ProviderStatus.UNAVAILABLE

    def test_omniroute_available_when_reachable(self):
        p = OmniRouteProvider()
        resp = MagicMock()
        resp.read.return_value = b"{}"
        with patch("urllib.request.urlopen", return_value=resp):
            assert p.get_status() == ProviderStatus.AVAILABLE

    def test_status_cached_within_ttl(self):
        p = OmniRouteProvider()
        with patch("urllib.request.urlopen", side_effect=Exception("refused")):
            p.get_status()
            p.get_status()
        # Only one probe within the TTL window
        assert p._status_cache is not None

    def test_no_key_means_no_probe(self):
        p = GroqProvider()
        p._get_api_key = lambda: None
        with patch("urllib.request.urlopen") as mock_urlopen:
            assert p.get_status() == ProviderStatus.NO_API_KEY
        mock_urlopen.assert_not_called()


class TestGeminiStreaming:
    """Gemini real streaming: SDK first, native REST SSE fallback."""

    def test_sdk_streaming(self, monkeypatch):
        fake_genai = MagicMock()
        model_inst = fake_genai.GenerativeModel.return_value
        chunk1, chunk2 = MagicMock(), MagicMock()
        chunk1.text, chunk2.text = "Hello", " world"
        model_inst.generate_content.return_value = iter([chunk1, chunk2])
        # Both the parent package and the submodule must be faked: the parent
        # is imported first and `import a.b as c` binds via getattr(a, "b").
        fake_google = MagicMock()
        fake_google.generativeai = fake_genai
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

        g = GoogleProvider()
        g._get_api_key = lambda: "test-key"
        out = list(g.send_message_stream([AIMessage(role="user", content="hi")]))
        assert "".join(out) == "Hello world"

    def test_rest_sse_stream_when_sdk_missing(self, monkeypatch):
        # None in sys.modules makes `import google.generativeai` raise ImportError
        monkeypatch.setitem(sys.modules, "google.generativeai", None)
        g = GoogleProvider()
        g._get_api_key = lambda: "test-key"
        with patch(
            "urllib.request.urlopen", return_value=FakeSSE(sse_gemini(["Hello", " there"]))
        ):
            out = list(g.send_message_stream([AIMessage(role="user", content="hi")]))
        assert "".join(out) == "Hello there"

    def test_no_key_yields_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "google.generativeai", None)
        g = GoogleProvider()
        g._get_api_key = lambda: None
        out = list(g.send_message_stream([AIMessage(role="user", content="hi")]))
        assert any("not configured" in c for c in out)


class TestFreeOnlyPolicy:
    """Free-first: paid providers are never silently selected."""

    def _make_pm(self, free_only):
        pm = ProviderManager()
        pm.free_only = free_only

        paid = MagicMock()
        paid.get_name.return_value = "PaidCo"
        paid.get_status.return_value = ProviderStatus.AVAILABLE
        paid.cost_tier = "paid"
        paid.send_message.return_value = AIResponse(content="paid answer", model="m1")

        free = MagicMock()
        free.get_name.return_value = "FreeCo"
        free.get_status.return_value = ProviderStatus.AVAILABLE
        free.cost_tier = "free"
        free.send_message.return_value = AIResponse(content="free answer", model="m2")

        pm._providers = {"paid": paid, "free": free}
        pm._current_provider_name = "free"
        pm.router = TaskRouter(pm._providers)
        pm.router.set_chain(TaskType.GENERAL, ["paid", "free"])
        return pm

    def test_paid_skipped_when_free_only_enabled(self):
        pm = self._make_pm(free_only=True)
        resp = pm.send_message("hello")
        assert resp.content == "free answer"

    def test_paid_used_when_free_only_disabled(self):
        pm = self._make_pm(free_only=False)
        resp = pm.send_message("hello")
        assert resp.content == "paid answer"

    def test_error_when_only_paid_available(self):
        pm = self._make_pm(free_only=True)
        pm.router.set_chain(TaskType.GENERAL, ["paid"])
        pm._current_provider_name = "paid"
        resp = pm.send_message("hello")
        assert resp.is_error
        assert "free-only" in resp.error.lower()

    def test_routing_reports_cost_tier(self):
        pm = self._make_pm(free_only=True)
        pm.send_message("hello")
        assert pm.get_last_routing().get("cost_tier") == "free"


class TestCapabilityRouting:
    """Vision tasks must only go to vision-capable providers."""

    def test_vision_task_skips_non_vision_provider(self):
        no_vision = MagicMock()
        no_vision.get_name.return_value = "TextOnly"
        no_vision.get_status.return_value = ProviderStatus.AVAILABLE
        no_vision.supports_vision.return_value = False
        no_vision.send_message.return_value = AIResponse(content="wrong", model="m")

        vision = MagicMock()
        vision.get_name.return_value = "Eye"
        vision.get_status.return_value = ProviderStatus.AVAILABLE
        vision.supports_vision.return_value = True
        vision.send_message.return_value = AIResponse(content="right", model="m")

        router = TaskRouter({"novision": no_vision, "vision": vision})
        router.set_chain(TaskType.VISION, ["novision", "vision"])
        name, _model = router.resolve(TaskType.VISION)
        assert name == "vision"


class TestUsageReporting:
    def test_usage_recorded_and_reported(self):
        pm = ProviderManager()
        p = MagicMock()
        p.get_name.return_value = "Prov"
        p.get_status.return_value = ProviderStatus.AVAILABLE
        p.cost_tier = "free"
        p.send_message.return_value = AIResponse(
            content="ok", model="m",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        pm._providers = {"prov": p}
        pm._current_provider_name = "prov"
        pm.router = TaskRouter(pm._providers)

        resp = pm.send_message("hello")
        assert not resp.is_error
        summary = pm.get_usage_summary()
        assert summary["prov"]["prompt_tokens"] == 10
        assert summary["prov"]["completion_tokens"] == 5
        assert summary["prov"]["requests"] == 1


class TestProviderRegistry:
    def test_ollama_registered(self):
        pm = ProviderManager()
        assert "ollama" in pm.get_provider_names()

    def test_cost_tiers_declared(self):
        pm = ProviderManager()
        assert pm._providers["openai"].cost_tier == "paid"
        assert pm._providers["google"].cost_tier == "free"
        assert pm._providers["groq"].cost_tier == "free"
        assert pm._providers["omniroute"].cost_tier == "local"
        assert pm._providers["ollama"].cost_tier == "local"

    def test_capabilities_declared(self):
        pm = ProviderManager()
        caps = pm._providers["google"].capabilities()
        assert caps["streaming"] is True
        assert caps["vision"] is True
