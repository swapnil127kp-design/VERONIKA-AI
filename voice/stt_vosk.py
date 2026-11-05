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
from typing import Optional

logger = logging.getLogger(__name__)

# Model bundled in VERONIKA (copied from Part 7, TAMCL attribution preserved).
# Fallback to Part 7 location if local copy doesn't exist.
_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL_MODEL = os.path.join(_HERE, "models", "vosk-model-en-us-0.22")
_DEFAULT_PART7_MODEL = os.path.join(
    r"C:\Users\Swapnil\OneDrive\Desktop\claude code\jarvis",
    "Playlist-main", "Playlist-main", "Part 7",
    "app", "src", "main", "assets", "model-en-us",
)
_DEFAULT_MODEL = _LOCAL_MODEL if os.path.isdir(_LOCAL_MODEL) else _DEFAULT_PART7_MODEL


class VoskSTT:
    """Offline speech-to-text with the bundled US-English Vosk model."""

    def __init__(self, model_path: Optional[str] = None):
        if model_path:
            self._model_path = model_path
        else:
            from app.config import config
            configured = config.get("voice", "vosk_model_path", "")
            self._model_path = configured if configured else _DEFAULT_MODEL
        self._model = None
        self._load_failed = False

    @property
    def is_available(self) -> bool:
        """True when the vosk package AND the model directory are usable."""
        if self._load_failed:
            return False
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False
        return os.path.isdir(self._model_path) and \
            os.path.isdir(os.path.join(self._model_path, "am"))

    def _ensure_model(self):
        if self._model is not None:
            return
        if not self.is_available:
            self._load_failed = True
            raise RuntimeError(
                "Vosk STT unavailable: install the 'vosk' package and ensure the "
                f"model directory exists ({self._model_path})."
            )
        from vosk import Model
        import vosk
        vosk.SetLogLevel(-1)
        self._model = Model(self._model_path)
        logger.info("Vosk model loaded from %s", self._model_path)

    def transcribe_wav(self, wav_bytes: bytes, language: str = "en-US") -> str:
        """Transcribe a complete in-memory WAV recording. Fully offline."""
        if language.startswith("hi"):
            # The bundled model is US-English only; Hindi needs a hi-IN model.
            logger.warning(
                "Vosk bundled model is en-US only; Hindi audio may transcribe poorly."
            )
        self._ensure_model()
        import wave
        import io
        from vosk import KaldiRecognizer

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            rec = KaldiRecognizer(self._model, wf.getframerate())
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
