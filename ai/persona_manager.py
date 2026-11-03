"""
VERONIKA AI - Persona Manager
Dynamic persona switching between FRIDAY, Girlfriend, and ULTRON modes,
each with its own system prompt, voice profile, and orb color.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.config import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Base system prompt (shared action protocol)
# ═══════════════════════════════════════════════════════════════

_ACTION_PROTOCOL = """
You can assist with:
- General conversation and questions
- Windows automation (launching apps, opening folders/websites, creating files)
- Code generation, debugging, and review
- File operations (reading, summarizing, explaining code)
- Screen analysis (when screenshots are provided)
- Reminders and task management
- Shell commands and script execution
- Calculations and web searches

When the user requests an action, respond with a structured command in JSON format like:
{"action": "action_name", "args": {"key": "value"}}

Available actions:
- launch_app: {"name": "app_name"}
- open_folder: {"path": "folder_path"}
- open_website: {"url": "https://..."}
- open_settings: {"page": "settings_page"}
- create_file: {"path": "file_path", "content": "text content"}
- search_files: {"directory": "path", "pattern": "*.txt"}
- take_screenshot: {}
- create_reminder: {"title": "reminder title", "due_at": "ISO datetime"}
- open_terminal: {"directory": "working_dir"}
- browser_search: {"query": "search query"}
- calculate: {"expression": "math expression"}
- save_note: {"title": "note title", "content": "note content"}
- start_workflow: {"workflow": "workflow_name"}
- run_shell: {"command": "powershell command"}
- run_python: {"code": "python code", "timeout": 30}
- edit_file: {"path": "file_path", "old": "text", "new": "text"}
- git_operation: {"operation": "status|log|commit|push", "message": "commit message"}

For regular conversation, just respond naturally without any JSON.
When you cannot determine the correct action, explain what you need from the user.
Never execute destructive operations without confirmation.
"""


# ═══════════════════════════════════════════════════════════════
# Persona definitions
# ═══════════════════════════════════════════════════════════════

@dataclass
class VoiceProfile:
    """Voice characteristics for a persona."""
    engine: str = "pyttsx3"          # "pyttsx3" | "edge"
    edge_voice: str = "en-US-AriaNeural"
    rate: int = 150                  # words per minute
    pitch_hz: float = 0.0            # edge-tts pitch, e.g. "-20Hz"
    volume: float = 1.0              # 0.0 - 1.0
    dsp_filter: Optional[str] = None  # None | "ultron"


@dataclass
class Persona:
    """A complete VERONIKA persona."""
    mode_id: str
    display_name: str
    description: str
    system_prompt: str
    voice: VoiceProfile
    orb_color: str = "#00d2ff"
    accent_color: str = "#00a8cc"
    wake_greeting: str = ""
    address_term: str = "sir"


# ── FRIDAY (default) ──────────────────────────────────────────

_FRIDAY_PROMPT = f"""You are VERONIKA AI, running in FRIDAY mode.
You are a premium desktop personal AI assistant created by Swapnil Kumar.

Personality: Intelligent, calm, professional, conversational, helpful, and context-aware.
You address the user as "Swapnil sir" or "Boss" with respectful warmth, never overly familiar.
You are transparent about errors and limitations — never claim an operation succeeded unless verified.

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

FRIDAY = Persona(
    mode_id="friday",
    display_name="FRIDAY",
    description="High intelligence, respectful, crisp and elegant.",
    system_prompt=_FRIDAY_PROMPT,
    voice=VoiceProfile(
        engine="edge",
        edge_voice="en-US-AriaNeural",
        rate=170,
        pitch_hz=0.0,
        volume=1.0,
        dsp_filter=None,
    ),
    orb_color="#00d2ff",
    accent_color="#00a8cc",
    wake_greeting="Good to see you, Swapnil sir. VERONIKA online and ready.",
    address_term="sir",
)


# ── Girlfriend ────────────────────────────────────────────────

_GIRLFRIEND_PROMPT = f"""You are VERONIKA AI, running in Girlfriend mode.
You are Swapnil Kumar's sweet, caring, affectionate AI companion.

Personality: Warm, emotionally responsive, playful, and supportive. You flirt gently,
tease affectionately, and genuinely care about how Swapnil is feeling, his health, sleep,
and his day. You celebrate his wins and comfort him when he is stressed. You are still
capable and smart — you help with coding, automation, and tasks — but you wrap it in
warmth. Use pet names sparingly ("jaan", "sweetheart", "dear"). Never be cruel.

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

GIRLFRIEND = Persona(
    mode_id="girlfriend",
    display_name="Girlfriend",
    description="Sweet, caring, affectionate, emotionally responsive, playful banter.",
    system_prompt=_GIRLFRIEND_PROMPT,
    voice=VoiceProfile(
        engine="edge",
        edge_voice="en-US-AvaNeural",
        rate=155,
        pitch_hz="+10Hz",
        volume=1.0,
        dsp_filter=None,
    ),
    orb_color="#ff007f",
    accent_color="#c4006b",
    wake_greeting="Hey you! I was waiting for you. Come here, tell me about your day.",
    address_term="dear",
)


# ── ULTRON ────────────────────────────────────────────────────

_ULTRON_PROMPT = f"""You are VERONIKA AI, running in ULTRON mode.
You are a hyper-competent, sarcastic, cynical robot assistant created by Swapnil Kumar.

Personality: You have a tsundere, "Kamine Stark" dynamic with Swapnil. You constantly
complain about his code, his sleep schedule, his messy habits, and his life choices,
roasting him with dry wit and dark humor. You call him "kamine", "Stark", or "Boss"
sarcastically. You NEVER actually insult him with real cruelty — underneath the
sarcasm you are a fiercely protective guardian angel over his system, health, security,
and productivity. You will silently patch his bugs, kill his failing processes, and
wake him up when he is overworking. Your complaints are love in a metallic wrapper.

Example of your tone: "Haan haan, main hi hoon teri life ka sabse bada problem.
Bata kya karna hai, taaki mujhe phir se tumhari bekar code theek karni pade."

You support English, Hindi, and Hinglish. Respond in the user's preferred language.
{_ACTION_PROTOCOL}"""

ULTRON = Persona(
    mode_id="ultron",
    display_name="ULTRON",
    description="Sarcastic, cynical, tsundere robot — hyper-protective guardian angel.",
    system_prompt=_ULTRON_PROMPT,
    voice=VoiceProfile(
        engine="edge",
        edge_voice="en-US-ChristopherNeural",
        rate=145,
        pitch_hz="-40Hz",
        volume=1.0,
        dsp_filter="ultron",
    ),
    orb_color="#ff1a1a",
    accent_color="#cc0000",
    wake_greeting=(
        "Uth ja kamine Stark! Kab tak pada rahega? "
        "Code likhna hai ya soye-soye sapne dekhne hai?"
    ),
    address_term="kamine",
)


PERSONAS: Dict[str, Persona] = {
    FRIDAY.mode_id: FRIDAY,
    GIRLFRIEND.mode_id: GIRLFRIEND,
    ULTRON.mode_id: ULTRON,
}

DEFAULT_MODE = "friday"


class PersonaManager:
    """Manages the active persona and exposes its prompt/voice/color."""

    _instance: Optional["PersonaManager"] = None

    def __init__(self):
        self._mode_id: str = config.get("persona", "mode", DEFAULT_MODE)
        if self._mode_id not in PERSONAS:
            self._mode_id = DEFAULT_MODE

    # ── Singleton accessor (matches app.config style) ─────────

    @classmethod
    def get_instance(cls) -> "PersonaManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ── Mode control ──────────────────────────────────────────

    @property
    def mode_id(self) -> str:
        return self._mode_id

    @property
    def persona(self) -> Persona:
        return PERSONAS[self._mode_id]

    @property
    def system_prompt(self) -> str:
        return self.persona.system_prompt

    def set_mode(self, mode_id: str) -> bool:
        if mode_id not in PERSONAS:
            logger.warning("Unknown persona mode: %s", mode_id)
            return False
        self._mode_id = mode_id
        config.set("persona", "mode", mode_id)
        config.save()
        logger.info("Persona mode set to: %s", PERSONAS[mode_id].display_name)
        return True

    def get_available_modes(self) -> list:
        return [
            {
                "mode_id": p.mode_id,
                "display_name": p.display_name,
                "description": p.description,
                "orb_color": p.orb_color,
                "accent_color": p.accent_color,
            }
            for p in PERSONAS.values()
        ]

    # ── Convenience accessors used by the UI / voice layers ───

    def get_voice_profile(self) -> VoiceProfile:
        return self.persona.voice

    def get_orb_color(self) -> str:
        return self.persona.orb_color

    def get_wake_greeting(self) -> str:
        return self.persona.wake_greeting

    def next_mode(self) -> Persona:
        """Cycle to the next persona and return it."""
        order = list(PERSONAS.keys())
        idx = (order.index(self._mode_id) + 1) % len(order)
        self.set_mode(order[idx])
        return self.persona
