"""
Tests for AI provider manager.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from ai.provider_base import AIMessage, AIResponse, ModelConfig, ProviderStatus
from ai.provider_manager import ProviderManager


class TestAIMessage:
    def test_basic_message(self):
        msg = AIMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.image_data is None

    def test_message_with_image(self):
        msg = AIMessage(role="user", content="What's this?", image_data=b"\x89PNG", image_mime="image/png")
        assert msg.image_data == b"\x89PNG"
        assert msg.image_mime == "image/png"


class TestAIResponse:
    def test_success_response(self):
        resp = AIResponse(content="Hello!", model="gpt-4o")
        assert not resp.is_error
        assert resp.content == "Hello!"

    def test_error_response(self):
        resp = AIResponse(content="", error="API key invalid")
        assert resp.is_error
        assert resp.error == "API key invalid"


class TestModelConfig:
    def test_defaults(self):
        cfg = ModelConfig()
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048
        assert cfg.stream is True

    def test_custom(self):
        cfg = ModelConfig(model="gpt-4o-mini", temperature=0.3, max_tokens=1024, stream=False)
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.3


class TestProviderManager:
    def test_parse_action_valid(self):
        pm = ProviderManager()
        text = 'Sure! Let me open that for you. {"action": "launch_app", "args": {"name": "notepad"}}'
        result = pm.parse_action(text)
        assert result is not None
        assert result["action"] == "launch_app"
        assert result["args"]["name"] == "notepad"

    def test_parse_action_no_action(self):
        pm = ProviderManager()
        result = pm.parse_action("Just a regular response with no action.")
        assert result is None

    def test_parse_action_invalid_json(self):
        pm = ProviderManager()
        result = pm.parse_action('{"action": broken json}')
        assert result is None

    def test_parse_action_browser_search(self):
        pm = ProviderManager()
        text = '{"action": "browser_search", "args": {"query": "weather today"}}'
        result = pm.parse_action(text)
        assert result["action"] == "browser_search"
        assert result["args"]["query"] == "weather today"

    def test_get_all_providers(self):
        pm = ProviderManager()
        providers = pm.get_all_providers()
        assert "openai" in providers
        assert "google" in providers

    def test_set_provider(self):
        pm = ProviderManager()
        pm.set_provider("google")
        assert pm.current_provider_name == "google"

    def test_set_invalid_provider(self):
        pm = ProviderManager()
        pm.set_provider("nonexistent")
        # Should not change
        assert pm.current_provider_name != "nonexistent"
