"""
Tests for the Model Scout (Phase 4).

All network access is mocked. The scout must be read-only: it must never
write configuration (approval-before-activation rule).
"""
import json
from unittest.mock import patch

import pytest

from app.config import config
from ai import model_scout
from ai.model_scout import (
    ScoutedModel, ScoutResult, scout_openrouter, scout_groq, scout_gemini,
    scout_local, generate_report, format_report,
)


@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    monkeypatch.setattr(config, "get", lambda sec, opt, default=None: default)
    monkeypatch.setattr(config, "get_api_key", lambda name: None)
    monkeypatch.setattr(config, "set", lambda *a, **k: None)
    monkeypatch.setattr(config, "save", lambda *a, **k: None)
    yield


def _openrouter_payload():
    """Two models: one free multimodal with tools, one paid text-only."""
    return {
        "data": [
            {
                "id": "vendor/free-model:free",
                "name": "Free Model",
                "context_length": 131072,
                "architecture": {"input_modalities": ["text", "image"]},
                "supported_parameters": ["tools", "temperature"],
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "vendor/paid-model",
                "name": "Paid Model",
                "context_length": 8192,
                "architecture": {"input_modalities": ["text"]},
                "supported_parameters": ["temperature"],
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
            },
        ]
    }


class TestOpenRouterScout:
    def test_classifies_free_and_paid(self):
        resp = json.dumps(_openrouter_payload()).encode()
        with patch.object(model_scout, "_fetch_json", return_value=json.loads(resp)):
            result = scout_openrouter()
        assert result.status == "ok"
        assert len(result.models) == 2
        free = next(m for m in result.models if m.model_id.endswith(":free"))
        paid = next(m for m in result.models if ":free" not in m.model_id)
        assert free.cost_tier == "free" and free.vision and free.tools
        assert paid.cost_tier == "paid" and not paid.vision

    def test_source_and_date_recorded(self):
        resp = json.dumps(_openrouter_payload()).encode()
        with patch.object(model_scout, "_fetch_json", return_value=json.loads(resp)):
            result = scout_openrouter()
        assert result.models[0].source == model_scout._OPENROUTER_MODELS_URL
        assert result.models[0].verified_at  # non-empty ISO date

    def test_unreachable_is_honest(self):
        with patch.object(model_scout, "_fetch_json", side_effect=Exception("down")):
            result = scout_openrouter()
        assert result.status == "unreachable"
        assert result.models == []


class TestKeyedScouts:
    def test_groq_no_key_is_honest(self):
        result = scout_groq()
        assert result.status == "no_key"
        assert result.models == []

    def test_gemini_no_key_is_honest(self):
        result = scout_gemini()
        assert result.status == "no_key"
        assert result.models == []

    def test_groq_with_key_parses_models(self):
        payload = {"data": [{"id": "llama-3.3-70b-versatile", "context_window": 131072}]}
        with patch.object(model_scout.config, "get_api_key", return_value="k"):
            with patch.object(model_scout, "_fetch_json", return_value=payload):
                result = scout_groq()
        assert result.status == "ok"
        assert result.models[0].model_id == "llama-3.3-70b-versatile"
        assert result.models[0].cost_tier == "free_tier"


class TestLocalScout:
    def test_offline_gateways_reported_honestly(self):
        with patch.object(model_scout, "_fetch_json", side_effect=Exception("refused")):
            result = scout_local()
        assert result.status == "ok"
        assert all(m.model_id == "(unreachable)" for m in result.models)
        assert all("offline" in m.notes for m in result.models)

    def test_online_gateway_lists_models(self):
        payload = {"data": [{"id": "kr/qwen3-coder-next"}]}
        with patch.object(model_scout, "_fetch_json", return_value=payload):
            result = scout_local()
        ids = [m.model_id for m in result.models]
        assert "kr/qwen3-coder-next" in ids


class TestReport:
    def test_report_structure_and_free_first_ordering(self):
        ok = ScoutResult("openrouter", "ok", "2", [
            ScoutedModel(provider="openrouter", model_id="paid/x", cost_tier="paid",
                         context_length=8192, verified_at="2026-11-04",
                         source="https://x"),
            ScoutedModel(provider="openrouter", model_id="free/y:free",
                         cost_tier="free", context_length=131072,
                         verified_at="2026-11-04", source="https://x"),
        ])
        with patch.object(model_scout, "scout_openrouter", return_value=ok), \
             patch.object(model_scout, "scout_groq",
                          return_value=ScoutResult("groq", "no_key", "none")), \
             patch.object(model_scout, "scout_gemini",
                          return_value=ScoutResult("google", "no_key", "none")), \
             patch.object(model_scout, "scout_local",
                          return_value=ScoutResult("local", "ok", "", [])):
            report = generate_report()

        assert report["providers"][0]["status"] == "ok"
        recs = report["recommendations"]
        assert recs[0]["model_id"] == "free/y:free"  # free first
        assert "owner approval" in report["disclaimer"]

    def test_format_report_is_readable(self):
        ok = ScoutResult("openrouter", "ok", "1", [
            ScoutedModel(provider="openrouter", model_id="free/y:free",
                         cost_tier="free", context_length=131072, vision=True,
                         tools=True, verified_at="2026-11-04", source="https://x"),
        ])
        with patch.object(model_scout, "scout_openrouter", return_value=ok), \
             patch.object(model_scout, "scout_groq",
                          return_value=ScoutResult("groq", "no_key", "none")), \
             patch.object(model_scout, "scout_gemini",
                          return_value=ScoutResult("google", "no_key", "none")), \
             patch.object(model_scout, "scout_local",
                          return_value=ScoutResult("local", "ok", "", [])):
            text = format_report(generate_report())
        assert "free/y:free" in text
        assert "free-first" in text


class TestReadOnly:
    def test_scout_never_writes_config(self):
        """The scout is read-only: no config.set/save calls ever happen."""
        called = {"set": 0, "save": 0}
        with patch.object(config, "set", side_effect=lambda *a, **k: called.__setitem__("set", called["set"] + 1)):
            with patch.object(config, "save", side_effect=lambda *a, **k: called.__setitem__("save", called["save"] + 1)):
                with patch.object(model_scout, "_fetch_json", return_value={"data": []}):
                    scout_openrouter()
                    scout_groq()
                    scout_gemini()
                    scout_local()
        assert called["set"] == 0 and called["save"] == 0
