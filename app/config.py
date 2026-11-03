"""
VERONIKA AI Desktop - Configuration Module
Handles loading, saving, and managing application configuration.
"""
import os
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Application metadata
APP_NAME = "VERONIKA AI"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Swapnil Kumar"

# Directories
APP_DATA_DIR = Path(os.environ.get(
    "APPDATA", Path.home() / "AppData" / "Roaming"
)) / "Veronika AI"
CONFIG_DIR = APP_DATA_DIR / "config"
DATA_DIR = APP_DATA_DIR / "data"
LOG_DIR = APP_DATA_DIR / "logs"
CACHE_DIR = APP_DATA_DIR / "cache"
SCREENSHOTS_DIR = APP_DATA_DIR / "screenshots"

# Ensure directories exist
for d in [APP_DATA_DIR, CONFIG_DIR, DATA_DIR, LOG_DIR, CACHE_DIR, SCREENSHOTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = DATA_DIR / "veronika.db"

# Config file
CONFIG_FILE = CONFIG_DIR / "settings.json"


# Default configuration
DEFAULT_CONFIG = {
    "ai": {
        "provider": "openai",
        "openai_model": "gpt-4o",
        "google_model": "gemini-flash-latest",
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream_responses": True,
        "dynamic_routing": True,
        "omniroute_base_url": "http://127.0.0.1:20128/v1",
        "omniroute_model": "kr/qwen3-coder-next",
    },
    "voice": {
        "tts_enabled": True,
        "tts_voice": "default",
        "tts_speed": 150,
        "stt_language": "en-US",
        "push_to_talk_key": "ctrl+shift+v",
    },
    "wake_word": {
        "enabled": False,
        "sensitivity": 0.5,
    },
    "ui": {
        "theme": "dark",
        "floating_window": False,
        "compact_mode": False,
        "window_width": 1100,
        "window_height": 750,
        "always_on_top": False,
        "opacity": 1.0,
    },
    "general": {
        "language": "en",
        "startup_with_windows": False,
        "screenshot_confirm": True,
        "log_level": "INFO",
    },
    "automation": {
        "allowed_directories": [],
        "confirm_destructive": True,
        "max_workflow_steps": 20,
        "step_timeout_seconds": 30,
    },
    "memory": {
        "auto_save_conversations": True,
        "max_conversation_history": 100,
    },
    "persona": {
        "mode": "friday",
    },
    "entity": {
        "active": "veronika",
        "overlay": "",
    },
    "sync": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8765,
        "master_token": "",
    },
    "orb": {
        "enabled": True,
        "http_host": "127.0.0.1",
        "http_port": 3000,
        "ws_host": "127.0.0.1",
        "ws_port": 8766,
        "audio_reactive": True,
        "open_browser_on_start": False,
    },
    "scout": {
        "enabled": True,
        "interval_seconds": 3600,
    },
    "github_scout": {
        "enabled": False,
        "interval_seconds": 3600,
        "min_stars": 50,
    },
    "mcp": {
        "enabled": False,
        # Each server: {"transport": "stdio"|"http", "command"/"url", "args", "env", "enabled"}
        "servers": {},
    },
    "rea": {
        "enabled": True,
        "max_iterations": 8,
        "max_sub_agent_depth": 3,
    },
    "swarm": {
        "max_workers": 4,
        "max_iterations": 6,
        "max_depth": 2,
    },
    "exam": {
        "num_topics": 8,
        "num_questions": 10,
    },
    "gesture": {
        "enabled": False,
        "show_landmarks": True,
        "max_fps": 20,
        "model_asset_url": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "tasks_vision_url": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm",
        "tasks_vision_wasm_url": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm",
    },
}


class AppConfig:
    """Application configuration manager with file persistence."""

    def __init__(self):
        self._config: dict = {}
        self._env_overrides: dict = {}
        self.load()

    def load(self):
        """Load configuration from file, falling back to defaults."""
        self._config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_merge(self._config, saved)
                logger.info("Configuration loaded from %s", CONFIG_FILE)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config file: %s. Using defaults.", e)

        # Load .env overrides
        self._load_env_overrides()

    def _load_env_overrides(self):
        """Load overrides from environment variables and .env file."""
        try:
            from dotenv import load_dotenv
            # Look for .env in project root and app data dir
            project_env = Path(__file__).parent.parent / ".env"
            if project_env.exists():
                load_dotenv(project_env)
            app_env = APP_DATA_DIR / ".env"
            if app_env.exists():
                load_dotenv(app_env, override=True)
        except ImportError:
            logger.debug("python-dotenv not installed; loading .env manually")
            for env_path in [Path(__file__).parent.parent / ".env", APP_DATA_DIR / ".env"]:
                if env_path.exists():
                    try:
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, v = line.split("=", 1)
                                    k, v = k.strip(), v.strip().strip("'\"")
                                    if k and k not in os.environ:
                                        os.environ[k] = v
                    except Exception as e:
                        logger.warning("Failed to parse %s: %s", env_path, e)

        env_map = {
            "AI_PROVIDER": ("ai", "provider"),
            "OPENAI_MODEL": ("ai", "openai_model"),
            "GOOGLE_MODEL": ("ai", "google_model"),
            "TTS_ENABLED": ("voice", "tts_enabled"),
            "TTS_SPEED": ("voice", "tts_speed"),
            "STT_LANGUAGE": ("voice", "stt_language"),
            "WAKE_WORD_ENABLED": ("wake_word", "enabled"),
            "LANGUAGE": ("general", "language"),
            "STARTUP_WITH_WINDOWS": ("general", "startup_with_windows"),
            "FLOATING_WINDOW": ("ui", "floating_window"),
        }
        for env_key, config_path in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                section, key = config_path
                converted = self._convert_env_value(val)
                self._config[section][key] = converted

    @staticmethod
    def _convert_env_value(val: str) -> Any:
        """Convert environment string to appropriate Python type."""
        if val.lower() in ("true", "1", "yes"):
            return True
        if val.lower() in ("false", "0", "no"):
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def save(self):
        """Persist current configuration to file."""
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved to %s", CONFIG_FILE)
        except OSError as e:
            logger.error("Failed to save configuration: %s", e)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        """Set a configuration value."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value

    def get_section(self, section: str) -> dict:
        """Get an entire configuration section."""
        return dict(self._config.get(section, {}))

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                AppConfig._deep_merge(base[key], value)
            else:
                base[key] = value

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a provider. Tries keyring first, then env vars.
        Never stores keys in the config file.
        """
        # Try keyring (secure storage)
        try:
            import keyring
            key = keyring.get_password("veronika_ai", f"{provider}_api_key")
            if key:
                return key
        except Exception:
            pass

        # Fall back to environment variables
        env_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_var = env_map.get(provider, "")
        return os.environ.get(env_var) or None

    def set_api_key(self, provider: str, key: str):
        """Store API key securely using keyring."""
        try:
            import keyring
            keyring.set_password("veronika_ai", f"{provider}_api_key", key)
            logger.info("API key for %s stored securely in system keyring", provider)
        except Exception as e:
            logger.warning(
                "Could not store key in keyring: %s. "
                "Set the key as an environment variable instead. "
                "Note: Storing API keys on a personal computer carries inherent risk. "
                "Ensure your system is secured.", e
            )

    def delete_api_key(self, provider: str):
        """Delete a stored API key."""
        try:
            import keyring
            keyring.delete_password("veronika_ai", f"{provider}_api_key")
        except Exception:
            pass


# Singleton config instance
config = AppConfig()
