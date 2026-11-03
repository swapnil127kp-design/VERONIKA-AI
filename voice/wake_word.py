"""
VERONIKA AI - Wake Word Detection
Optional "Hey Veronika" wake word using Porcupine or simple keyword detection.
"""
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Wake word detection for "Hey Veronika".

    Uses Picovoice Porcupine if available and configured with an access key.
    Falls back to a simple speech-recognition-based keyword detection.

    Note: Porcupine requires a free access key from https://picovoice.ai/
    and a custom keyword model trained on their platform for "Hey Veronika".
    Without a custom model, we use the built-in "computer" keyword as a demo,
    or fall back to periodic speech recognition checks.
    """

    def __init__(self):
        self._is_active = False
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_wake: Optional[Callable[[], None]] = None
        self._porcupine = None

    @property
    def is_active(self) -> bool:
        return self._is_active

    def start(self, on_wake: Callable[[], None]):
        """Start listening for wake word in the background."""
        if self._is_active:
            return

        self._on_wake = on_wake
        self._stop_flag.clear()

        # Try Porcupine first
        if self._try_porcupine():
            self._thread = threading.Thread(target=self._porcupine_loop, daemon=True)
        else:
            # Fallback: periodic speech recognition keyword check
            self._thread = threading.Thread(target=self._fallback_loop, daemon=True)

        self._is_active = True
        self._thread.start()
        logger.info("Wake word detection started")

    def _try_porcupine(self) -> bool:
        """Attempt to initialize Porcupine wake word engine."""
        try:
            from app.config import config
            access_key = config.get_api_key("picovoice") or ""
            if not access_key:
                import os
                access_key = os.environ.get("PICOVOICE_ACCESS_KEY", "")

            if not access_key:
                logger.info(
                    "Picovoice access key not configured. "
                    "Wake word will use fallback detection. "
                    "Get a free key at https://picovoice.ai/"
                )
                return False

            import pvporcupine
            # Use built-in "computer" keyword as demo
            # For "Hey Veronika", train a custom keyword at https://picovoice.ai/
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=["computer"],  # Replace with custom model path
            )
            logger.info("Porcupine wake word engine initialized (using 'computer' keyword as demo)")
            return True
        except ImportError:
            logger.info("pvporcupine not installed. Using fallback wake word detection.")
            return False
        except Exception as e:
            logger.warning("Porcupine initialization failed: %s", e)
            return False

    def _porcupine_loop(self):
        """Porcupine-based wake word detection loop."""
        try:
            import pyaudio
            import struct

            pa = pyaudio.PyAudio()
            stream = pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )

            logger.info("Porcupine listening for wake word...")
            while not self._stop_flag.is_set():
                pcm = stream.read(self._porcupine.frame_length, exception_on_overflow=False)
                pcm_unpacked = struct.unpack_from(
                    "h" * self._porcupine.frame_length, pcm
                )
                keyword_index = self._porcupine.process(pcm_unpacked)
                if keyword_index >= 0:
                    logger.info("Wake word detected!")
                    if self._on_wake:
                        self._on_wake()

            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception as e:
            logger.error("Porcupine loop error: %s", e)
        finally:
            if self._porcupine:
                self._porcupine.delete()
                self._porcupine = None
            self._is_active = False

    def _fallback_loop(self):
        """Fallback: periodic speech recognition to detect 'Hey Veronika'."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8

            logger.info("Fallback wake word detection active (listening for 'hey veronika')")

            while not self._stop_flag.is_set():
                try:
                    with sr.Microphone() as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.3)
                        audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)

                    text = recognizer.recognize_google(audio, language="en-US").lower()
                    if "hey veronika" in text or "hey veronica" in text:
                        logger.info("Wake phrase detected: '%s'", text)
                        if self._on_wake:
                            self._on_wake()

                except Exception:
                    # Timeouts and recognition failures are expected
                    pass

                # Brief pause between attempts
                self._stop_flag.wait(0.5)

        except Exception as e:
            logger.error("Fallback wake word error: %s", e)
        finally:
            self._is_active = False

    def stop(self):
        """Stop wake word detection."""
        self._stop_flag.set()
        self._is_active = False
        if self._porcupine:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None
        logger.info("Wake word detection stopped")
