"""
VERONIKA AI - Speech Recognition
Converts speech audio to text.

Engines (config: voice.stt_engine):
  - "google_free" (default): SpeechRecognition lib + Google's free web API.
    Audio leaves the machine (cloud). Free, no key, decent accuracy.
  - "vosk_local": fully OFFLINE Vosk STT using the Part 7 bundled US-English
    model. Audio never leaves the machine (privacy-first option).

Hindi/Hinglish: google_free supports hi-IN natively. The bundled Vosk model
is en-US only -- Hindi via local STT needs a separate hi-IN Vosk model.
"""
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """Speech-to-text with selectable engine (cloud-free-tier or local)."""

    def __init__(self):
        self._recognizer = None
        self._is_listening = False
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()
        self._listen_thread: Optional[threading.Thread] = None
        self._mic = None       # MicrophoneManager (vosk_local path)
        self._vosk = None      # VoskSTT (vosk_local path)

    def _ensure_recognizer(self):
        if self._recognizer is None:
            try:
                import speech_recognition as sr
                self._recognizer = sr.Recognizer()
                self._recognizer.dynamic_energy_threshold = True
                self._recognizer.pause_threshold = 1.0
            except ImportError:
                raise RuntimeError(
                    "SpeechRecognition not installed. Install with: pip install SpeechRecognition"
                )

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    def _active_engine(self) -> str:
        from app.config import config
        return config.get("voice", "stt_engine", "google_free")

    def _decide_engine(self, language: str):
        """
        Resolve the STT engine for a request. Returns (engine, gate_error).

        gate_error is set (and engine stays vosk_local) when no local Vosk
        model can hear the requested language and voice.allow_cloud_fallback
        is off: the audio must NOT silently go to the Google cloud engine.
        The caller shows the gate_error and stops listening instead.
        """
        engine = self._active_engine()
        if engine != "vosk_local":
            return engine, None
        lang = (language or "en-US").lower()
        from voice.stt_vosk import resolve_model_for_language
        if lang.startswith("en") or resolve_model_for_language(language):
            return engine, None
        from app.config import config
        if config.get("voice", "allow_cloud_fallback", False):
            logger.info(
                "No local Vosk model for %s; using Google STT "
                "(voice.allow_cloud_fallback is enabled).", language,
            )
            return "google_free", None
        return engine, (
            f"No local Vosk model for {language}. Choose the Google engine in "
            "Settings > Voice, enable cloud fallback in settings, or install a "
            "Vosk model for this language (voice/models/README.md)."
        )

    def recognize_speech(
        self,
        language: str = "en-US",
        on_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_started: Optional[Callable[[], None]] = None,
        on_stopped: Optional[Callable[[], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
        timeout: float = 10.0,
        phrase_time_limit: float = 30.0,
    ):
        """
        Start listening for speech in a background thread.
        Calls on_result with recognized text or on_error with error message.
        The engine is chosen by config (voice.stt_engine); when vosk_local has
        no model for `language`, the request is gated (see _decide_engine).
        on_level callback receives RMS level (0.0 to 1.0) during recording.
        """
        if self._is_listening:
            if on_error:
                on_error("Already listening. Please wait for current recognition to finish.")
            return

        self._cancel_flag.clear()
        engine, gate_error = self._decide_engine(language)
        if gate_error:
            logger.warning("STT request gated: %s", gate_error)
            if on_error:
                on_error(gate_error)
            return
        worker = self._listen_vosk if engine == "vosk_local" else self._listen_google
        self._listen_thread = threading.Thread(
            target=worker,
            args=(language, on_result, on_error, on_started, on_stopped,
                  on_level, timeout, phrase_time_limit),
            daemon=True,
        )
        self._listen_thread.start()

    # ------------------------------------------------------------------
    # Engine: Google free web API (cloud)
    # ------------------------------------------------------------------

    def _listen_google(self, language, on_result, on_error, on_started,
                       on_stopped, on_level, timeout, phrase_time_limit):
        try:
            import speech_recognition as sr
            self._ensure_recognizer()

            with self._lock:
                self._is_listening = True

            if on_started:
                on_started()

            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

                if self._cancel_flag.is_set():
                    return

                logger.info("Listening for speech (lang=%s, engine=google_free)...", language)
                try:
                    audio = self._recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    if on_error:
                        on_error("No speech detected. Please try again.")
                    return

            if self._cancel_flag.is_set():
                return

            logger.info("Recognizing speech...")
            try:
                text = self._recognizer.recognize_google(audio, language=language)
                logger.info("Recognized: %s", text[:50] + "..." if len(text) > 50 else text)
                if on_result:
                    on_result(text)
            except sr.UnknownValueError:
                if on_error:
                    on_error("Could not understand the audio. Please speak clearly and try again.")
            except sr.RequestError as e:
                if on_error:
                    on_error(f"Speech recognition service error: {e}")

        except Exception as e:
            logger.error("Speech recognition error: %s", e)
            if on_error:
                on_error(f"Microphone error: {e}")
        finally:
            with self._lock:
                self._is_listening = False
            if on_stopped:
                on_stopped()

    # ------------------------------------------------------------------
    # Engine: Vosk (fully offline)
    # ------------------------------------------------------------------

    def _listen_vosk(self, language, on_result, on_error, on_started,
                     on_stopped, on_level, timeout, phrase_time_limit):
        try:
            from voice.microphone import MicrophoneManager
            from voice.stt_vosk import VoskSTT

            if self._mic is None:
                self._mic = MicrophoneManager()
            if self._vosk is None:
                self._vosk = VoskSTT()

            if not self._vosk.is_available:
                if on_error:
                    on_error(
                        "Local STT unavailable: install 'vosk' (pip install vosk) "
                        "and ensure the Vosk model path is valid. "
                        "Falling back is not automatic -- switch voice.stt_engine "
                        "to google_free for cloud recognition."
                    )
                return

            with self._lock:
                self._is_listening = True
            if on_started:
                on_started()

            logger.info("Listening for speech (engine=vosk_local, offline)...")

            # Record with level callback for UI meter
            wav = self._mic.record_seconds(
                duration=phrase_time_limit,
                on_level=on_level
            )

            if self._cancel_flag.is_set():
                return
            if not wav:
                if on_error:
                    on_error("No speech captured. Please try again.")
                return

            text = self._vosk.transcribe_wav(wav, language=language)
            if text:
                if on_result:
                    on_result(text)
            elif on_error:
                on_error("Could not understand the audio (local model).")

        except Exception as e:
            logger.error("Vosk recognition error: %s", e)
            if on_error:
                on_error(f"Local recognition error: {e}")
        finally:
            with self._lock:
                self._is_listening = False
            if on_stopped:
                on_stopped()

    def cancel(self):
        """Cancel ongoing recognition."""
        self._cancel_flag.set()
        if self._mic is not None:
            self._mic.cancel_recording()
        with self._lock:
            self._is_listening = False

    def get_supported_languages(self) -> list:
        """Return supported language codes for the active engine."""
        base = [
            {"code": "en-US", "name": "English (US)"},
            {"code": "en-IN", "name": "English (India)"},
            {"code": "hi-IN", "name": "Hindi"},
        ]
        if self._active_engine() == "vosk_local":
            for item in base:
                if item["code"].startswith("hi"):
                    item["name"] += " (needs separate Vosk hi-IN model)"
        return base
