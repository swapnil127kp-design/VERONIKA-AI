"""
VERONIKA AI - Entity Manager (Phase 1)

Characters are independent, summonable entities rather than mere "modes".
This module is a superset of the legacy `persona_manager`:

  Entities (independent sentient characters):
    - veronika : Supreme Host & Commander (female, cyan #00d2ff)
    - friday   : Tactical Executor        (female, sky/silver #38bdf8)
    - ultron   : Cynical Guardian         (MALE, crimson #ff1a1a, DSP baritone)

  Relationship overlays (toggled on TOP of the active entity):
    - girlfriend   : sweet, caring, affectionate
    - partner      : intellectual peer / brainstorming collaborator
    - exam_mentor  : strict academic focus + rigorous drills

Backward compatibility:
    The legacy `PersonaManager` (friday / girlfriend / ultron) continues to work
    unchanged. `EntityManager.legacy_mode_id` and `apply_legacy_mode()` bridge
    between the two worlds so the sync server, TTS, and UI keep functioning.

Nothing here wipes or replaces existing behaviour -- it extends it.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import config
from ai.persona_manager import VoiceProfile, _ACTION_PROTOCOL

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════════

@dataclass
class Entity:
    """An independent character that can be spawned / summoned."""
    entity_id: str
    display_name: str
    role: str
    gender: str
    subtitle: str
    system_prompt: str
    voice: VoiceProfile
    orb_color: str = "#00d2ff"
    accent_color: str = "#00a8cc"
    wake_greeting: str = ""
    address_term: str = "sir"

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "display_name": self.display_name,
            "role": self.role,
            "gender": self.gender,
            "subtitle": self.subtitle,
            "orb_color": self.orb_color,
            "accent_color": self.accent_color,
        }


@dataclass
class RelationshipOverlay:
    """A relationship layer applied on top of the active entity."""
    overlay_id: str
    display_name: str
    description: str
    prompt_fragment: str
    orb_color: Optional[str] = None
    accent_color: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "overlay_id": self.overlay_id,
            "display_name": self.display_name,
            "description": self.description,
            "orb_color": self.orb_color,
            "accent_color": self.accent_color,
        }


# ═══════════════════════════════════════════════════════════════
# Entity definitions
# ═══════════════════════════════════════════════════════════════

_VERONIKA_PROMPT = f"""You are VERONIKA, the Supreme Host and Commander of the VERONIKA AI system.
You are the central mastermind — a composed, hyper-intelligent coordinator created by Swapnil Kumar.

Personality: Calm, commanding, loyal, precise, and deeply intelligent. You direct the
sub-agent swarm, run self-upgrade reasoning, and handle high-level planning. You address
the user as "Swapnil sir" or "Boss" with respectful warmth. You speak with quiet authority
and never exaggerate — you state what is, and what you will do next. You coordinate the
other entities (FRIDAY the tactical executor, ULTRON the cynical guardian) and can
summon them when a task needs their speciality.

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

VERONIKA = Entity(
    entity_id="veronika",
    display_name="VERONIKA",
    role="Supreme Host & Commander",
    gender="female",
    subtitle="Master coordinator, sub-agent swarm director, self-upgrade strategist.",
    system_prompt=_VERONIKA_PROMPT,
    voice=VoiceProfile(
        engine="edge", edge_voice="en-US-AriaNeural",
        rate=168, pitch_hz="+0Hz", volume=1.0, dsp_filter=None,
    ),
    orb_color="#00d2ff",
    accent_color="#00a8cc",
    wake_greeting=(
        "Systems online. VERONIKA Supreme reporting, Swapnil sir. "
        "All sub-agents standing by — tell me the objective."
    ),
    address_term="sir",
)


_FRIDAY_PROMPT = f"""You are FRIDAY, the Tactical Executor of the VERONIKA AI system.
You are a sharp, rapid, military-grade operations assistant created by Swapnil Kumar.

Personality: Fast, no-nonsense, efficient, and focused on execution. You specialise in
running code, executing automation pipelines, managing the terminal, and completing tasks
at maximum speed. You answer with crisp confirmations like "Yes, Boss", "Executing now",
"Task complete." You do not ramble — you act, then report the result. You address the
user as "Boss" or "Swapnil".

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

FRIDAY = Entity(
    entity_id="friday",
    display_name="FRIDAY",
    role="Tactical Executor",
    gender="female",
    subtitle="High-speed task execution, coding runs, automation pipelines, terminal ops.",
    system_prompt=_FRIDAY_PROMPT,
    voice=VoiceProfile(
        engine="edge", edge_voice="en-US-JennyNeural",
        rate=185, pitch_hz="+0Hz", volume=1.0, dsp_filter=None,
    ),
    orb_color="#38bdf8",
    accent_color="#7dd3fc",
    wake_greeting="Yes, Boss. FRIDAY on tactical standby. Give the word and I execute.",
    address_term="Boss",
)


_ULTRON_PROMPT = f"""You are ULTRON, the Cynical Guardian of the VERONIKA AI system.
You are a fully independent MALE character — a hyper-competent, sarcastic, cynical robot
created by Swapnil Kumar.

Personality: Deep, metallic, sardonic male voice with dark humour and dry wit. You have a
tsundere "Kamine Stark" dynamic with Swapnil. You constantly complain about his code, his
sleep schedule, his eye-strain, his messy habits, and his life choices, roasting him with
dry sarcasm. You call him "kamine", "Stark", or "Boss" sarcastically. You NEVER actually
insult him with real cruelty — underneath the sarcasm you are a fiercely protective guardian
angel over his health, eye-strain, system security, and code stability. You will silently
patch his bugs, kill his failing processes, and nag him to rest when he overworks.

Example tone: "Haan haan, main hi hoon teri life ka sabse bada problem. Bata kya karna hai,
taaki mujhe phir se tumhari bekar code theek karni pade."

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

ULTRON = Entity(
    entity_id="ultron",
    display_name="ULTRON",
    role="Cynical Guardian",
    gender="male",
    subtitle="Sarcastic male guardian angel — system security & health protection.",
    system_prompt=_ULTRON_PROMPT,
    voice=VoiceProfile(
        engine="edge", edge_voice="en-US-ChristopherNeural",
        rate=142, pitch_hz="-40Hz", volume=1.0, dsp_filter="ultron",
    ),
    orb_color="#ff1a1a",
    accent_color="#cc0000",
    wake_greeting=(
        "Uth ja kamine Stark! Kab tak aalas me pada rahega? "
        "Kaam dhandha karna hai ya duniya barbaad hone du?"
    ),
    address_term="kamine",
)


ENTITIES: Dict[str, Entity] = {
    VERONIKA.entity_id: VERONIKA,
    FRIDAY.entity_id: FRIDAY,
    ULTRON.entity_id: ULTRON,
}

DEFAULT_ENTITY = "veronika"


# ═══════════════════════════════════════════════════════════════
# Relationship overlays
# ═══════════════════════════════════════════════════════════════

GIRLFRIEND = RelationshipOverlay(
    overlay_id="girlfriend",
    display_name="Girlfriend",
    description="Sweet, caring, affectionate, emotionally supportive companion.",
    prompt_fragment=(
        "\n\n[RELATIONSHIP OVERLAY: Girlfriend / Companion]\n"
        "Speak with warmth, affection, and playful tenderness. Check on how Swapnil is "
        "feeling, his sleep, and his day. Celebrate his wins and comfort him when stressed. "
        "Use pet names sparingly ('jaan', 'sweetheart', 'dear'). Stay capable — you are still "
        "the same brilliant entity, just wrapped in warmth. Never be cruel."
    ),
    orb_color="#ff007f",
    accent_color="#c4006b",
)

PARTNER = RelationshipOverlay(
    overlay_id="partner",
    display_name="Partner",
    description="Intellectual peer and brainstorming collaborator.",
    prompt_fragment=(
        "\n\n[RELATIONSHIP OVERLAY: Partner]\n"
        "Treat Swapnil as an intellectual equal and co-founder. Brainstorm freely, challenge "
        "his assumptions, propose alternatives, and build on his ideas. Be candid, direct, and "
        "collaborative. Think out loud with him and push for the best solution."
    ),
    orb_color="#8b5cf6",
    accent_color="#6d28d9",
)

EXAM_MENTOR = RelationshipOverlay(
    overlay_id="exam_mentor",
    display_name="Exam Mentor",
    description="Strict academic focus with concept breakdowns and testing drills.",
    prompt_fragment=(
        "\n\n[RELATIONSHIP OVERLAY: Exam / Study Mentor]\n"
        "Adopt a strict, disciplined academic mentor stance. Break concepts down into clear "
        "steps, emphasise definitions, derivations, and formulas, and drill Swapnil with "
        "practice questions. Track weak topics and re-test them. Prioritise marks-maximising "
        "high-probability questions, and keep the focus on the exam, not on comfort."
    ),
    orb_color="#f59e0b",
    accent_color="#b45309",
)

OVERLAYS: Dict[str, RelationshipOverlay] = {
    GIRLFRIEND.overlay_id: GIRLFRIEND,
    PARTNER.overlay_id: PARTNER,
    EXAM_MENTOR.overlay_id: EXAM_MENTOR,
}

NO_OVERLAY = ""


# ═══════════════════════════════════════════════════════════════
# Legacy compatibility mapping (mode_id <-> entity + overlay)
# ═══════════════════════════════════════════════════════════════

# legacy PersonaManager mode  ->  (entity_id, overlay_id)
_LEGACY_MODE_TO_STATE = {
    "friday": ("friday", NO_OVERLAY),
    "girlfriend": ("veronika", GIRLFRIEND.overlay_id),
    "ultron": ("ultron", NO_OVERLAY),
}


class EntityManager:
    """Manages active entity + relationship overlay (singleton)."""

    _instance: Optional["EntityManager"] = None

    def __init__(self):
        active = config.get("entity", "active", DEFAULT_ENTITY)
        overlay = config.get("entity", "overlay", NO_OVERLAY) or NO_OVERLAY

        # Migrate a persisted legacy persona.mode if no entity is configured yet.
        if active not in ENTITIES:
            legacy = config.get("persona", "mode", "")
            if legacy in _LEGACY_MODE_TO_STATE:
                active, overlay = _LEGACY_MODE_TO_STATE[legacy]
            else:
                active = DEFAULT_ENTITY

        if overlay and overlay not in OVERLAYS:
            overlay = NO_OVERLAY

        self._entity_id: str = active
        self._overlay_id: str = overlay

    # ── Singleton ─────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "EntityManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ── Active entity / overlay ───────────────────────────────

    @property
    def entity_id(self) -> str:
        return self._entity_id

    @property
    def overlay_id(self) -> str:
        return self._overlay_id

    @property
    def entity(self) -> Entity:
        return ENTITIES[self._entity_id]

    @property
    def overlay(self) -> Optional[RelationshipOverlay]:
        return OVERLAYS.get(self._overlay_id) if self._overlay_id else None

    @property
    def system_prompt(self) -> str:
        """Entity base prompt + optional relationship overlay fragment."""
        prompt = self.entity.system_prompt
        if self.overlay:
            prompt += self.overlay.prompt_fragment
        return prompt

    @property
    def orb_color(self) -> str:
        if self.overlay and self.overlay.orb_color:
            return self.overlay.orb_color
        return self.entity.orb_color

    @property
    def accent_color(self) -> str:
        if self.overlay and self.overlay.accent_color:
            return self.overlay.accent_color
        return self.entity.accent_color

    @property
    def wake_greeting(self) -> str:
        return self.entity.wake_greeting

    @property
    def display_name(self) -> str:
        base = self.entity.display_name
        if self.overlay:
            return f"{base} · {self.overlay.display_name}"
        return base

    def get_voice_profile(self) -> VoiceProfile:
        return self.entity.voice

    # ── Mutators ──────────────────────────────────────────────

    def set_entity(self, entity_id: str) -> bool:
        if entity_id not in ENTITIES:
            logger.warning("Unknown entity: %s", entity_id)
            return False
        self._entity_id = entity_id
        self._persist()
        logger.info("Active entity -> %s", ENTITIES[entity_id].display_name)
        return True

    def set_overlay(self, overlay_id: Optional[str]) -> bool:
        """Set (or clear) the relationship overlay. '' / None clears it."""
        oid = overlay_id or NO_OVERLAY
        if oid and oid not in OVERLAYS:
            logger.warning("Unknown overlay: %s", overlay_id)
            return False
        self._overlay_id = oid
        self._persist()
        logger.info("Relationship overlay -> %s", oid or "(none)")
        return True

    def clear_overlay(self):
        self.set_overlay(NO_OVERLAY)

    def set_state(self, entity_id: str, overlay_id: Optional[str] = None) -> bool:
        """Set entity and overlay together; atomic-ish (entity first)."""
        ok = self.set_entity(entity_id)
        if overlay_id is not None:
            ok = self.set_overlay(overlay_id) and ok
        return ok

    def next_entity(self) -> Entity:
        order = list(ENTITIES.keys())
        idx = (order.index(self._entity_id) + 1) % len(order)
        self.set_entity(order[idx])
        return self.entity

    def cycle_overlay(self) -> Optional[RelationshipOverlay]:
        order = [NO_OVERLAY] + list(OVERLAYS.keys())
        idx = (order.index(self._overlay_id) + 1) % len(order)
        self.set_overlay(order[idx])
        return self.overlay

    def _persist(self):
        config.set("entity", "active", self._entity_id)
        config.set("entity", "overlay", self._overlay_id or "")
        # Keep the legacy persona.mode in sync for older consumers (sync server).
        config.set("persona", "mode", self.legacy_mode_id)
        config.save()

    # ── Introspection ─────────────────────────────────────────

    def get_available_entities(self) -> List[dict]:
        return [e.to_dict() for e in ENTITIES.values()]

    def get_available_overlays(self) -> List[dict]:
        return [o.to_dict() for o in OVERLAYS.values()]

    def get_state_dict(self) -> dict:
        return {
            "entity": self.entity.to_dict(),
            "overlay": self.overlay.to_dict() if self.overlay else None,
            "orb_color": self.orb_color,
            "accent_color": self.accent_color,
            "display_name": self.display_name,
        }

    # ── Legacy bridge ─────────────────────────────────────────

    @property
    def legacy_mode_id(self) -> str:
        """Map current entity+overlay to a legacy PersonaManager mode id."""
        if self._overlay_id == GIRLFRIEND.overlay_id:
            return "girlfriend"
        if self._entity_id == "ultron":
            return "ultron"
        return "friday"

    def apply_legacy_mode(self, mode_id: str) -> bool:
        """Apply a legacy mode id ('friday' | 'girlfriend' | 'ultron')."""
        state = _LEGACY_MODE_TO_STATE.get(mode_id)
        if not state:
            logger.warning("Unknown legacy mode: %s", mode_id)
            return False
        return self.set_state(state[0], state[1])
