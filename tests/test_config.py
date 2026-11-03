"""
Tests for app.config module.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Patch dirs before importing config to avoid polluting real app data
_test_dir = tempfile.mkdtemp()

with patch.dict(os.environ, {"APPDATA": _test_dir}):
    from app.config import AppConfig, DEFAULT_CONFIG


class TestAppConfig:
    """Tests for the AppConfig configuration manager."""

    def _make_config(self, saved: dict | None = None, clean_env: bool = True):
        """Create a config instance with optional saved data."""
        cfg_dir = Path(tempfile.mkdtemp()) / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "settings.json"

        if saved is not None:
            cfg_file.write_text(json.dumps(saved), encoding="utf-8")

        with patch("app.config.CONFIG_FILE", cfg_file):
            if clean_env:
                with patch.object(AppConfig, "_load_env_overrides", lambda self: None):
                    c = AppConfig()
            else:
                c = AppConfig()
        return c

    def test_default_values(self):
        c = self._make_config()
        assert c.get("ai", "provider") == "openai"
        assert c.get("ui", "theme") == "dark"
        assert c.get("general", "language") == "en"

    def test_get_missing_returns_default(self):
        c = self._make_config()
        assert c.get("nonexistent", "key", "fallback") == "fallback"

    def test_set_and_get(self):
        c = self._make_config()
        c.set("ai", "provider", "google")
        assert c.get("ai", "provider") == "google"

    def test_set_new_section(self):
        c = self._make_config()
        c.set("custom", "foo", "bar")
        assert c.get("custom", "foo") == "bar"

    def test_get_section(self):
        c = self._make_config()
        section = c.get_section("ai")
        assert isinstance(section, dict)
        assert "provider" in section

    def test_merge_saved_over_defaults(self):
        c = self._make_config(saved={"ai": {"provider": "google"}})
        assert c.get("ai", "provider") == "google"
        # Other defaults should still be present
        assert c.get("ai", "openai_model") == "gpt-4o"

    def test_save_persists(self, tmp_path):
        cfg_file = tmp_path / "settings.json"
        with patch("app.config.CONFIG_FILE", cfg_file):
            c = AppConfig()
            c.set("ai", "provider", "google")
            c.save()

        assert cfg_file.exists()
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["ai"]["provider"] == "google"

    def test_convert_env_value_bool(self):
        assert AppConfig._convert_env_value("true") is True
        assert AppConfig._convert_env_value("false") is False
        assert AppConfig._convert_env_value("1") == 1
        assert AppConfig._convert_env_value("0") == 0
        assert AppConfig._convert_env_value("yes") is True
        assert AppConfig._convert_env_value("no") is False

    def test_convert_env_value_numbers(self):
        assert AppConfig._convert_env_value("42") == 42
        assert AppConfig._convert_env_value("3.14") == 3.14

    def test_convert_env_value_string(self):
        assert AppConfig._convert_env_value("hello") == "hello"
