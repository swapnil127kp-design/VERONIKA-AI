"""
VERONIKA AI - Local Vosk Speech-to-Text (Phase 5)

Fully OFFLINE speech recognition using the Vosk model bundled with the
original Part 7 Android project (TAMCL-attributed asset, salvaged per the
resource integration map). No audio ever leaves the machine in this mode.

Model layout expected: <model_dir>/{am, conf, graph, ivector}
Default path points at the Part 7 asset; override via config
(voice.vosk_model_path) if you place a different Vosk model elsewhere.

Install: pip install vosk  (pure wheels; no compiler needed)
"""
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Model bundled in VERONIKA (copied from Part 7, TAMCL attribution preserved).
# Fallback to Part 7 location if local copy doesn't exist.
_HERE = os.path.dirname(os.path.abspath(__file__))
_MODELS_ROOT = os.path.join(_HERE, "models")
_LOCAL_MODEL = os.path.join(_HERE, "models", "vosk-model-en-us-0.22")
_DEFAULT_PART7_MODEL = os.path.join(
    r"C:\Users\Swapnil\OneDrive\Desktop\claude code\jarvis",
    "Playlist-main", "Playlist-main", "Part 7",
    "app", "src", "main", "assets", "model-en-us",
)
_DEFAULT_MODEL = _LOCAL_MODEL if os.path.isdir(_LOCAL_MODEL) else _DEFAULT_PART7_MODEL

# Process-wide cache: model files are 45-70 MB, so they are loaded once
# per path and shared by every VoskSTT instance (same as loading is heavy
# per-recognition otherwise).
_MODEL_CACHE: Dict[str, object] = {}

# Language -> model folder-name prefixes (see voice/models/README.md).
_LANGUAGE_MODEL_PREFIXES = {
    "hi": ("vosk-model-small-hi", "vosk-model-hi", "vosk-model-hin"),
    "en": ("vosk-model-en", "vosk-model-small-en"),
}


def _usable_model_dirs(root: str) -> List[str]:
    """Model directory names under `root` that actually contain am/."""
    try:
        names = os.listdir(root)
    except OSError:
        return []
    usable = []
    for name in sorted(names):
        if name.startswith("vosk-model") and os.path.isdir(os.path.join(root, name, "am")):
            usable.append(name)
    return usable


def resolve_model_for_language(
    language: str, models_root: Optional[str] = None
) -> Optional[str]:
    """
    Find an installed Vosk model directory able to hear `language`.

    Returns the model path, or None when no local model can serve that
    language (the caller then decides between cloud fallback and an error -
    audio must not be silently Uploaded to a cloud engine).

    English additionally falls back to the unpackaged Part 7 asset when no
    model directory exists under `models_root` (development setups).
    """
    root = models_root if models_root is not None else _MODELS_ROOT
    lang = (language or "en-US").lower()
    key = next((k for k in _LANGUAGE_MODEL_PREFIXES if lang.startswith(k)), None)
    if key is None:
        return None
    prefixes = _LANGUAGE_MODEL_PREFIXES[key]
    for name in _usable_model_dirs(root):
        if name.startswith(prefixes):
            return os.path.join(root, name)
    if key == "en" and os.path.isdir(os.path.join(_DEFAULT_PART7_MODEL, "am")):
        return _DEFAULT_PART7_MODEL
    return None


class VoskSTT:
    """Offline speech-to-text using a Vosk model (US-English + optional Hindi)."""

    def __init__(self, model_path: Optional[str] = None):
        if model_path:
            self._model_path = model_path
        else:
            from app.config import config
            configured = config.get("voice", "vosk_model_path", "")
            self._model_path = configured if configured else _DEFAULT_MODEL
        self._load_failed = False

    @property
    def is_available(self) -> bool:
        """True when the vosk package AND the default (English) model are usable."""
        if self._load_failed:
            return False
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False
        return os.path.isdir(self._model_path) and \
            os.path.isdir(os.path.join(self._model_path, "am"))

    def _path_for_language(self, language: str) -> Tuple[str, Optional[str]]:
        """
        Resolve the model path for a language. Returns (path, warning).

        Warnings are returned (not logged here) when language != en-US has no
        dedicated model and the English model will be used as a best effort.
        """
        lang = (language or "en-US").lower()
        if lang.startswith("en"):
            return self._model_path, None
        resolved = resolve_model_for_language(language)
        if resolved:
            return resolved, None
        return self._model_path, (
            f"No local Vosk model for '{language}'; transcribing with the "
            "US-English model instead. Install a model for this language "
            "(see voice/models/README.md)."
        )

    def _ensure_model(self, model_path: Optional[str] = None):
        """Load (and cache process-wide) the Vosk model for `model_path`."""
        path = model_path or self._model_path
        cached = _MODEL_CACHE.get(path)
        if cached is not None:
            return cached
        try:
            from vosk import Model
        except ImportError:
            self._load_failed = True
            raise RuntimeError(
                "Vosk STT unavailable: install the 'vosk' package "
                "(pip install vosk)."
            )
        import vosk
        if not os.path.isdir(path) or not os.path.isdir(os.path.join(path, "am")):
            self._load_failed = True
            raise RuntimeError(
                "Vosk model directory is not usable: "
                f"{path} (expected Vosk layout with am/ - see voice/models/README.md)."
            )
        vosk.SetLogLevel(-1)
        model = Model(path)
        _MODEL_CACHE[path] = model
        logger.info("Vosk model loaded from %s", path)
        return model

    def transcribe_wav(self, wav_bytes: bytes, language: str = "en-US") -> str:
        """Transcribe a complete in-memory WAV recording. Fully offline."""
        model_path, warning = self._path_for_language(language)
        if warning:
            logger.warning(warning)
        model = self._ensure_model(model_path)
        import wave
        import io
        from vosk import KaldiRecognizer

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(False)
            result_text = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    part = _extract_text(rec.Result())
                    if part:
                        result_text.append(part)
            final = _extract_text(rec.FinalResult())
            if final:
                result_text.append(final)
        return " ".join(result_text).strip()


def _extract_text(json_str: str) -> str:
    """Pull the 'text' field out of a Vosk result JSON string."""
    import json
    try:
        return (json.loads(json_str) or {}).get("text", "")
    except Exception:
        return ""
