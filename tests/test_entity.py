"""
Tests for ai.entity_manager (Phase 1 - Entity & Character Architecture).
"""
import pytest

from app.config import config
from ai.entity_manager import (
    EntityManager, ENTITIES, OVERLAYS,
    GIRLFRIEND, EXAM_MENTOR, PARTNER,
)


@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    """Prevent tests from reading or writing real user config file."""
    monkeypatch.setattr(config, "get", lambda sec, opt, default=None: "veronika" if sec == "entity" and opt == "active" else ("" if sec == "entity" and opt == "overlay" else default))
    monkeypatch.setattr(config, "set", lambda *a, **k: None)
    monkeypatch.setattr(config, "save", lambda *a, **k: None)
    EntityManager.reset_instance()
    yield
    EntityManager.reset_instance()


class TestEntities:
    def test_three_core_entities_exist(self):
        assert set(ENTITIES.keys()) == {"veronika", "friday", "ultron"}

    def test_default_entity_is_veronika(self):
        em = EntityManager.get_instance()
        assert em.entity_id == "veronika"
        assert em.entity.role.startswith("Supreme")

    def test_ultron_is_male_with_dsp_voice(self):
        em = EntityManager.get_instance()
        em.set_entity("ultron")
        vp = em.get_voice_profile()
        assert em.entity.gender == "male"
        assert vp.dsp_filter == "ultron"
        assert vp.pitch_hz.startswith("-")

    def test_ultron_wake_greeting_is_kamine_stark(self):
        em = EntityManager.get_instance()
        em.set_entity("ultron")
        assert "kamine Stark" in em.wake_greeting

    def test_friday_is_tactical_female(self):
        em = EntityManager.get_instance()
        em.set_entity("friday")
        assert em.entity.role == "Tactical Executor"
        assert em.entity.gender == "female"

    def test_veronika_is_supreme_host_female(self):
        em = EntityManager.get_instance()
        em.set_entity("veronika")
        assert em.entity.gender == "female"
        assert em.entity.orb_color == "#00d2ff"

    def test_set_unknown_entity_fails(self):
        em = EntityManager.get_instance()
        assert em.set_entity("nonexistent") is False

    def test_next_entity_cycles(self):
        em = EntityManager.get_instance()
        em.set_entity("veronika")
        order = []
        for _ in range(3):
            order.append(em.next_entity().entity_id)
        assert set(order) == {"friday", "ultron", "veronika"}


class TestOverlays:
    def test_overlays_exist(self):
        assert set(OVERLAYS.keys()) == {"girlfriend", "partner", "exam_mentor"}

    def test_girlfriend_overlay_changes_color_and_prompt(self):
        em = EntityManager.get_instance()
        em.set_entity("veronika")
        base_prompt = em.system_prompt
        assert em.set_overlay("girlfriend") is True
        assert em.overlay_id == "girlfriend"
        assert em.orb_color == GIRLFRIEND.orb_color == "#ff007f"
        assert "Girlfriend" in em.system_prompt
        assert em.system_prompt != base_prompt

    def test_exam_mentor_overlay(self):
        em = EntityManager.get_instance()
        em.set_overlay("exam_mentor")
        assert em.overlay_id == "exam_mentor"
        assert "Exam" in em.system_prompt or "exam" in em.system_prompt

    def test_partner_overlay(self):
        em = EntityManager.get_instance()
        em.set_overlay("partner")
        assert em.overlay_id == "partner"

    def test_clear_overlay_restores_entity_color(self):
        em = EntityManager.get_instance()
        em.set_entity("ultron")
        em.set_overlay("girlfriend")
        assert em.orb_color == "#ff007f"
        em.clear_overlay()
        assert em.overlay_id == ""
        assert em.orb_color == "#ff1a1a"

    def test_unknown_overlay_fails(self):
        em = EntityManager.get_instance()
        assert em.set_overlay("bogus") is False

    def test_cycle_overlay(self):
        em = EntityManager.get_instance()
        em.clear_overlay()
        seen = {em.overlay_id}
        for _ in range(3):
            em.cycle_overlay()
            seen.add(em.overlay_id)
        assert {"", "girlfriend", "partner", "exam_mentor"} == seen


class TestLegacyBridge:
    def test_ultron_maps_to_legacy_ultron(self):
        em = EntityManager.get_instance()
        em.set_entity("ultron")
        assert em.legacy_mode_id == "ultron"

    def test_girlfriend_overlay_maps_to_girlfriend(self):
        em = EntityManager.get_instance()
        em.set_state("veronika", "girlfriend")
        assert em.legacy_mode_id == "girlfriend"

    def test_friday_maps_to_friday(self):
        em = EntityManager.get_instance()
        em.set_entity("friday")
        assert em.legacy_mode_id == "friday"

    def test_apply_legacy_mode(self):
        em = EntityManager.get_instance()
        assert em.apply_legacy_mode("ultron") is True
        assert em.entity_id == "ultron"
        assert em.apply_legacy_mode("girlfriend") is True
        assert em.overlay_id == "girlfriend"
        assert em.apply_legacy_mode("nope") is False


class TestStateIntrospection:
    def test_get_state_dict(self):
        em = EntityManager.get_instance()
        em.set_state("friday", "partner")
        d = em.get_state_dict()
        assert d["entity"]["entity_id"] == "friday"
        assert d["overlay"]["overlay_id"] == "partner"
        assert "orb_color" in d and "accent_color" in d

    def test_get_available_entities_and_overlays(self):
        em = EntityManager.get_instance()
        assert len(em.get_available_entities()) == 3
        assert len(em.get_available_overlays()) == 3

    def test_display_name_combines_entity_and_overlay(self):
        em = EntityManager.get_instance()
        em.set_state("veronika", "exam_mentor")
        assert "VERONIKA" in em.display_name
        assert "Exam Mentor" in em.display_name
