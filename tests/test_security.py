"""
Security-focused tests: sync token handling and provider key resolution.

Covers the Phase 1 hardening items from docs/SECURITY.md:
- H-1: master token is never persisted in plaintext config
- H-3: empty/missing master token is never accepted
- config.get_api_key env fallback covers all supported providers
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

from server.auth import SyncAuth


class _FakeKeyring:
    """In-memory stand-in for the real keyring module."""

    def __init__(self, store=None, fail=False):
        self.store = store if store is not None else {}
        self.fail = fail

    def get_password(self, service, account):
        if self.fail:
            raise RuntimeError("keyring unavailable")
        return self.store.get(account)

    def set_password(self, service, account, value):
        if self.fail:
            raise RuntimeError("keyring unavailable")
        self.store[account] = value

    def delete_password(self, service, account):
        self.store.pop(account, None)


class TestSyncTokenSecurity:
    """Sync master token handling (SECURITY.md H-1, H-3)."""

    def _install(self, monkeypatch, keyring, config_token=""):
        mock_config = MagicMock()
        mock_config.get.return_value = config_token
        monkeypatch.setitem(sys.modules, "keyring", keyring)
        monkeypatch.setattr("server.auth.config", mock_config)
        return mock_config

    def test_verify_master_token_rejects_empty(self, monkeypatch):
        auth = SyncAuth()
        self._install(monkeypatch, _FakeKeyring({"sync_master_token": "secret-token"}))

        assert auth.verify_master_token("") is False
        assert auth.verify_master_token("secret-token") is True
        assert auth.verify_master_token("wrong-token") is False

    def test_verify_rejects_when_no_token_configured(self, monkeypatch):
        auth = SyncAuth()
        # Keyring fails and config holds an empty token: master_token must be
        # generated fresh, never empty, and verification must still be strict.
        self._install(monkeypatch, _FakeKeyring(fail=True), config_token="")

        token = auth.master_token
        assert token  # a token always exists
        assert auth.verify_master_token("") is False
        assert auth.verify_master_token(token) is True

    def test_token_never_persisted_to_config_plaintext(self, monkeypatch):
        auth = SyncAuth()
        keyring = _FakeKeyring(fail=True)  # keyring unavailable
        mock_config = self._install(monkeypatch, keyring, config_token="")

        token = auth.master_token
        assert token

        # No plaintext token write into the config file (H-1).
        plaintext_writes = [
            c for c in mock_config.set.call_args_list
            if c.args[:2] == ("sync", "master_token") and c.args[2]
        ]
        assert plaintext_writes == []

    def test_legacy_plaintext_token_migrated_and_scrubbed(self, monkeypatch):
        auth = SyncAuth()
        keyring = _FakeKeyring()  # keyring works
        mock_config = self._install(
            monkeypatch, keyring, config_token="legacy-plaintext-token"
        )

        assert auth.master_token == "legacy-plaintext-token"
        # Token moved into the keyring...
        assert keyring.store.get("sync_master_token") == "legacy-plaintext-token"
        # ...and scrubbed from the config file.
        scrub_calls = [
            c for c in mock_config.set.call_args_list
            if c.args[:2] == ("sync", "master_token")
        ]
        assert scrub_calls and scrub_calls[0].args[2] == ""

    def test_rotate_token_issues_new_secret(self, monkeypatch):
        auth = SyncAuth()
        keyring = _FakeKeyring({"sync_master_token": "old-token"})
        self._install(monkeypatch, keyring, config_token="")

        new_token = auth.rotate_token()
        assert new_token and new_token != "old-token"
        assert auth.verify_master_token("old-token") is False
        assert auth.verify_master_token(new_token) is True


class TestProviderKeyEnvFallback:
    """config.get_api_key must resolve env vars for every provider (H-12)."""

    @pytest.mark.parametrize(
        "provider,env_name",
        [
            ("openai", "OPENAI_API_KEY"),
            ("google", "GOOGLE_API_KEY"),
            ("groq", "GROQ_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
            ("omniroute", "OMNIROUTE_API_KEY"),
        ],
    )
    def test_env_fallback_per_provider(self, monkeypatch, tmp_path, provider, env_name):
        monkeypatch.setitem(sys.modules, "keyring", _FakeKeyring({}))
        monkeypatch.setenv(env_name, f"test-key-for-{provider}")

        from app.config import AppConfig
        with patch("app.config.CONFIG_FILE", tmp_path / "settings.json"), \
                patch.object(AppConfig, "_load_env_overrides", lambda self: None):
            cfg = AppConfig()

        assert cfg.get_api_key(provider) == f"test-key-for-{provider}"

    def test_no_env_var_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "keyring", _FakeKeyring({}))
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
                     "OPENROUTER_API_KEY", "OMNIROUTE_API_KEY"):
            monkeypatch.delenv(name, raising=False)

        from app.config import AppConfig
        with patch("app.config.CONFIG_FILE", tmp_path / "settings.json"), \
                patch.object(AppConfig, "_load_env_overrides", lambda self: None):
            cfg = AppConfig()

        assert cfg.get_api_key("groq") is None
