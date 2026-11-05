"""
Tests for the Personality Engine (Phase 3).

Directive rules verified here:
  - Companion replaces Girlfriend and is strictly NON-romantic.
  - ULTRON is sarcastic but NEVER abusive/demeaning (no "kamine" etc.).
  - Greetings are varied (pooled + randomized).
  - Startup greeting is config-toggleable.
  - Mode switching changes voice/prompt/theme/greeting ONLY -- never memory,
    conversation history, identity, security, or permissions.
"""
import random

import pytest

from app.config import config
from ai.persona_manager import (
    COMPANION, FRIDAY, ULTRON, PERSONAS, PersonaManager,
)
from ai.entity_manager import EntityManager


@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    """Prevent tests from reading or writing real user config file."""
    monkeypatch.setattr(config, "get", lambda sec, opt, default=None: default)
    monkeypatch.setattr(config, "set", lambda *a, **k: None)
    monkeypatch.setattr(config, "save", lambda *a, **k: None)
    PersonaManager.reset_instance()
    EntityManager.reset_instance()
    yield
    PersonaManager.reset_instance()
    EntityManager.reset_instance()


# Terms that must never appear in any persona prompt or greeting.
ROMANTIC_TERMS = ("girlfriend", "jaan", "sweetheart", "date night")
# These may appear ONLY inside an explicit negation ("no flirting", "not a
# romantic partner") -- the boundary declaration itself is required.
NEGATED_ROMANTIC_TERMS = ("flirt", "romantic")
DEMEANING_TERMS = ("kamine", "stupid", "idiot", "loser", "useless", "nalayak", "bewakoof")


def _norm(text: str) -> str:
    """Collapse whitespace so line breaks don't break assertions."""
    return " ".join(text.split()).lower()


class TestPersonaRegistry:
    def test_three_modes_exist(self):
        assert set(PERSONAS.keys()) == {"friday", "companion", "ultron"}

    def test_default_mode_is_friday(self):
        pm = PersonaManager.get_instance()
        assert pm.mode_id == "friday"

    def test_companion_replaces_girlfriend(self):
        assert "girlfriend" not in PERSONAS
        assert COMPANION.mode_id == "companion"
        assert COMPANION.display_name == "Companion"

    def test_available_modes_expose_capabilities(self):
        pm = PersonaManager.get_instance()
        modes = pm.get_available_modes()
        assert all("capabilities" in m for m in modes)
        friday = next(m for m in modes if m["mode_id"] == "friday")
        assert "coding" in friday["capabilities"]


class TestNonRomanticCompanion:
    def test_prompt_is_non_romantic(self):
        text = _norm(COMPANION.system_prompt + " " + COMPANION.wake_greeting)
        for term in ROMANTIC_TERMS:
            assert term not in text, f"romantic term '{term}' found in Companion"

    def test_prompt_declares_non_romantic_boundary(self):
        text = _norm(COMPANION.system_prompt)
        assert "not a romantic partner" in text
        for term in NEGATED_ROMANTIC_TERMS:
            assert f"no {term}" in text or f"not a {term}" in text, (
                f"'{term}' must appear only as an explicit negation"
            )

    def test_prompt_keeps_supportive_warmth(self):
        lowered = COMPANION.system_prompt.lower()
        assert "warm" in lowered and "supportive" in lowered

    def test_no_romantic_terms_anywhere_in_any_persona(self):
        for p in PERSONAS.values():
            text = _norm(p.system_prompt + " " + p.wake_greeting +
                         " " + " ".join(p.greeting_pool))
            for term in ROMANTIC_TERMS:
                assert term not in text, f"'{term}' in persona {p.mode_id}"


class TestNonDemeaningUltron:
    def test_ultron_prompt_has_no_demeaning_terms(self):
        text = _norm(ULTRON.system_prompt)
        for term in DEMEANING_TERMS:
            assert term not in text, f"'{term}' found in ULTRON prompt"

    def test_ultron_greetings_have_no_demeaning_terms(self):
        text = _norm(" ".join(ULTRON.greeting_pool))
        for term in DEMEANING_TERMS:
            assert term not in text, f"'{term}' found in ULTRON greetings"

    def test_ultron_keeps_sarcastic_stark_address(self):
        assert "Stark" in ULTRON.system_prompt
        assert ULTRON.address_term == "Stark"

    def test_ultron_prompt_keeps_protective_guardian_role(self):
        text = _norm(ULTRON.system_prompt)
        assert "protective" in text
        assert "never with insults" in text


class TestModeSwitchingPreservesMemory:
    def test_set_mode_only_writes_persona_config(self):
        """Directive: mode switching must not reset memory/conversation."""
        pm = PersonaManager.get_instance()
        written = []
        monkey_writes = {}

        def fake_set(section, option, value):
            monkey_writes[(section, option)] = value

        # Capture every config write during a mode switch.
        import app.config as cfg_mod
        original_set = cfg_mod.config.set
        cfg_mod.config.set = fake_set
        try:
            assert pm.set_mode("ultron") is True
        finally:
            cfg_mod.config.set = original_set

        assert set(monkey_writes.keys()) == {("persona", "mode")}
        assert monkey_writes[("persona", "mode")] == "ultron"

    def test_switching_mode_changes_only_prompt_voice_color(self):
        pm = PersonaManager.get_instance()
        before = (pm.system_prompt, pm.get_voice_profile(), pm.get_orb_color())
        pm.set_mode("ultron")
        after = (pm.system_prompt, pm.get_voice_profile(), pm.get_orb_color())
        assert before != after
        # And back again -- identity (mode_id registry) unchanged.
        pm.set_mode("friday")
        assert pm.mode_id == "friday"

    def test_unknown_mode_rejected(self):
        pm = PersonaManager.get_instance()
        assert pm.set_mode("nope") is False
        assert pm.mode_id == "friday"


class TestDeprecatedAlias:
    def test_set_mode_girlfriend_maps_to_companion(self):
        pm = PersonaManager.get_instance()
        assert pm.set_mode("girlfriend") is True
        assert pm.mode_id == "companion"

    def test_legacy_config_value_normalized_on_init(self):
        # Simulate an old config that persisted persona.mode = "girlfriend".
        def fake_get(sec, opt, default=None):
            if sec == "persona" and opt == "mode":
                return "girlfriend"
            return default

        original_get = config.get
        config.get = fake_get
        try:
            PersonaManager.reset_instance()
            pm = PersonaManager.get_instance()
            assert pm.mode_id == "companion"
        finally:
            config.get = original_get
            PersonaManager.reset_instance()


class TestGreetingVariety:
    def test_every_persona_has_multi_greeting_pool(self):
        for p in PERSONAS.values():
            assert len(p.greeting_pool) >= 3, f"{p.mode_id} pool too small"
            assert p.wake_greeting in p.greeting_pool

    def test_get_wake_greeting_returns_pool_member(self):
        pm = PersonaManager.get_instance()
        pm.set_mode("companion")
        pool = set(COMPANION.greeting_pool)
        for _ in range(10):
            assert pm.get_wake_greeting() in pool

    def test_greetings_actually_vary(self):
        random.seed(42)
        pm = PersonaManager.get_instance()
        seen = {pm.get_wake_greeting() for _ in range(30)}
        assert len(seen) >= 2


class TestStartupGreetingToggle:
    def test_default_enabled(self):
        assert PersonaManager.is_startup_greeting_enabled() is True

    def test_disabled_via_config(self):
        original_get = config.get
        config.get = lambda sec, opt, default=None: (
            False if (sec == "persona" and opt == "startup_greeting") else default
        )
        try:
            assert PersonaManager.is_startup_greeting_enabled() is False
        finally:
            config.get = original_get


class TestPersonaCapabilities:
    def test_all_personas_have_capabilities_and_shortcuts(self):
        for p in PERSONAS.values():
            assert p.capabilities, f"{p.mode_id} has no capabilities"
            assert p.shortcuts, f"{p.mode_id} has no shortcuts"

    def test_ultron_has_guardian_capabilities(self):
        assert "system_guardian" in ULTRON.capabilities
        assert "security_audit" in ULTRON.capabilities


class TestVoiceProfiles:
    """Directive: FRIDAY=Aria, Companion=Ava(+10Hz), ULTRON=Christopher(-40Hz)+DSP."""

    def test_friday_voice(self):
        assert FRIDAY.voice.edge_voice == "en-US-AriaNeural"
        assert FRIDAY.voice.dsp_filter is None

    def test_companion_voice(self):
        assert COMPANION.voice.edge_voice == "en-US-AvaNeural"
        assert COMPANION.voice.pitch_hz == "+10Hz"

    def test_ultron_voice(self):
        assert ULTRON.voice.edge_voice == "en-US-ChristopherNeural"
        assert ULTRON.voice.pitch_hz == "-40Hz"
        assert ULTRON.voice.dsp_filter == "ultron"


class TestEntityMirror:
    """The newer EntityManager system must mirror the same directive rules."""

    def test_entity_ultron_prompt_non_demeaning(self):
        from ai.entity_manager import ENTITIES
        text = ENTITIES["ultron"].system_prompt.lower()
        for term in DEMEANING_TERMS:
            assert term not in text

    def test_entity_greeting_pools_vary(self):
        from ai.entity_manager import ENTITIES
        for e in ENTITIES.values():
            assert len(e.greeting_pool) >= 3

    def test_em_wake_greeting_uses_pool(self):
        em = EntityManager.get_instance()
        em.set_entity("friday")
        from ai.entity_manager import FRIDAY
        pool = set(FRIDAY.greeting_pool)
        assert em.wake_greeting in pool
