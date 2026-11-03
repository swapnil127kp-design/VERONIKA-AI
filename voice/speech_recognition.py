"""
VERONIKA AI - Speech Recognition
Converts speech audio to text using SpeechRecognition library.
"""
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """Speech-to-text using the SpeechRecognition library with Google's free API."""

    def __init__(self):
        self._recognizer = None
        self._is_listening = False
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()
        self._listen_thread: Optional[threading.Thread] = None

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

    def recognize_speech(
        self,
        language: str = "en-US",
        on_result: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_started: Optional[Callable[[], None]] = None,
        on_stopped: Optional[Callable[[], None]] = None,
        timeout: float = 10.0,
        phrase_time_limit: float = 30.0,
    ):
        """
        Start listening for speech in a background thread.
        Calls on_result with recognized text or on_error with error message.
        """
        if self._is_listening:
            if on_error:
                on_error("Already listening. Please wait for current recognition to finish.")
            return

        self._cancel_flag.clear()

        def _listen():
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

                    logger.info("Listening for speech (lang=%s)...", language)
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

        self._listen_thread = threading.Thread(target=_listen, daemon=True)
        self._listen_thread.start()

    def cancel(self):
        """Cancel ongoing recognition."""
        self._cancel_flag.set()
        with self._lock:
            self._is_listening = False

    def get_supported_languages(self) -> list:
        """Return supported language codes."""
        return [
            {"code": "en-US", "name": "English (US)"},
            {"code": "en-IN", "name": "English (India)"},
            {"code": "hi-IN", "name": "Hindi"},
        ]
