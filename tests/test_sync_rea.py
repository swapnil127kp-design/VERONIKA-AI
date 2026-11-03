"""
Tests for the sync-server REA remote-execution hook (route registration).
"""
import pytest

pytest.importorskip("fastapi")


class _FakePersona:
    mode_id = "friday"


def test_rea_route_is_registered(monkeypatch):
    from server import sync_server

    services = sync_server._Services()
    # Pre-populate so resolve() doesn't build real subsystems.
    services.memory = object()
    services.provider_manager = object()
    services.action_registry = object()
    services.persona_manager = _FakePersona()
    services.bridge = None
    services.mcp_manager = None

    app = sync_server.create_app(services)

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/rea" in paths
    assert "/api/actions" in paths
    assert "/api/chat" in paths
