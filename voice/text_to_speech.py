"""
VERONIKA AI - Text-to-Speech
Multi-engine TTS with persona-aware voices and the ULTRON DSP filter.

Engines:
  - edge     : Microsoft Edge neural voices (edge-tts) -- preferred, high quality
  - pyttsx3  : Windows SAPI5 -- offline fallback

DSP (ULTRON mode):
  - pitch shift down + reverberation + slight distortion via pydub (needs ffmpeg).
  - Applied automatically when the active persona's VoiceProfile.dsp_filter == "ultron".

Playback degrades gracefully: simpleaudio -> ffplay (pydub) -> winsound ->
PowerShell MediaPlayer -> pyttsx3. If nothing can play audio, falls back to pyttsx3.
"""
import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


class TextToSpeech:
    """Text-to-speech engine with persona-aware voice selection."""

    def __init__(self):
        self._engine = None
        self._is_speaking = False
        self._lock = threading.Lock()
        self._speak_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._persona_manager = None
        self._entity_manager = None
        self._temp_dir = os.path.join(tempfile.gettempdir(), "veronika_tts")
        os.makedirs(self._temp_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Persona / entity wiring
    # ------------------------------------------------------------------

    @property
    def persona_manager(self):
        if self._persona_manager is None:
            from ai.persona_manager import PersonaManager
            self._persona_manager = PersonaManager.get_instance()
        return self._persona_manager

    @property
    def entity_manager(self):
        if self._entity_manager is None:
            try:
                from ai.entity_manager import EntityManager
                self._entity_manager = EntityManager.get_instance()
            except Exception:
                self._entity_manager = None
        return self._entity_manager

    def _voice_profile(self):
        # Prefer the active entity's voice (Veronika / FRIDAY / ULTRON-male);
        # fall back to the legacy persona profile.
        try:
            em = self.entity_manager
            if em is not None:
                return em.get_voice_profile()
        except Exception:
            pass
        try:
            return self.persona_manager.get_voice_profile()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # pyttsx3 engine (offline fallback)
    # ------------------------------------------------------------------

    def _ensure_engine(self):
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init("sapi5")
            except ImportError:
                raise RuntimeError("pyttsx3 not installed. Install with: pip install pyttsx3")
            except Exception as e:
                logger.error("Failed to initialize TTS engine: %s", e)
                raise RuntimeError(f"TTS initialization failed: {e}")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def get_voices(self) -> list:
        try:
            self._ensure_engine()
            voices = self._engine.getProperty("voices")
            return [
                {"id": v.id, "name": v.name, "languages": getattr(v, "languages", [])}
                for v in voices
            ]
        except Exception as e:
            logger.error("Failed to get voices: %s", e)
            return []

    def set_voice(self, voice_id: str):
        try:
            self._ensure_engine()
            self._engine.setProperty("voice", voice_id)
        except Exception as e:
            logger.error("Failed to set voice: %s", e)

    def set_speed(self, rate: int):
        try:
            self._ensure_engine()
            self._engine.setProperty("rate", max(50, min(400, rate)))
        except Exception as e:
            logger.error("Failed to set speed: %s", e)

    # ------------------------------------------------------------------
    # Public speak API
    # ------------------------------------------------------------------

    def speak(
        self,
        text: str,
        on_started: Optional[Callable[[], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ):
        """Speak text in a background thread. Non-blocking."""
        if not text.strip():
            return

        self._stop_flag.clear()
        self._speak_thread = threading.Thread(
            target=self._speak_worker, args=(text, on_started, on_finished),
            daemon=True,
        )
        self._speak_thread.start()

    def _speak_worker(self, text, on_started, on_finished):
        with self._lock:
            self._is_speaking = True
        try:
            if on_started:
                on_started()

            logger.info("TTS speaking: %s", text[:80] + "..." if len(text) > 80 else text)

            profile = self._voice_profile()
            ok = False
            if profile is not None and profile.engine == "edge":
                ok = self._speak_edge(text, profile)
            if not ok:
                self._speak_pyttsx3(text)

        except Exception as e:
            logger.error("TTS error: %s", e)
        finally:
            with self._lock:
                self._is_speaking = False
            if on_finished:
                on_finished()

    def stop(self):
        self._stop_flag.set()
        with self._lock:
            self._is_speaking = False

    def release(self):
        self.stop()
        self._engine = None

    # ------------------------------------------------------------------
    # Edge neural voice
    # ------------------------------------------------------------------

    def _speak_edge(self, text: str, profile) -> bool:
        """Generate speech with edge-tts, apply DSP, and play it."""
        try:
            import asyncio
            import edge_tts
        except ImportError:
            logger.debug("edge-tts not installed; falling back to pyttsx3")
            return False

        mp3_path = os.path.join(self._temp_dir, f"{uuid.uuid4().hex}.mp3")

        try:
            rate_str = f"{profile.rate - 150:+d}%"
            communicate = edge_tts.Communicate(
                text=text,
                voice=profile.edge_voice,
                rate=rate_str,
                pitch=profile.pitch_hz or "+0Hz",
                volume=f"+{int(profile.volume * 100)}%" if profile.volume < 1.0 else "+0%",
            )
            asyncio.run(communicate.save(mp3_path))

            if self._stop_flag.is_set():
                return True

            play_path = mp3_path
            if profile.dsp_filter == "ultron":
                processed = self._apply_ultron_dsp(mp3_path)
                if processed:
                    play_path = processed

            played = self._play_audio(play_path)
            if not played:
                logger.debug("Edge audio playback unavailable; falling back to pyttsx3")
            return played

        except Exception as e:
            logger.warning("Edge TTS failed (%s); falling back to pyttsx3", e)
            return False
        finally:
            # Clean up temp files shortly after playback.
            threading.Timer(2.0, self._cleanup_files, args=([mp3_path],)).start()

    def _apply_ultron_dsp(self, mp3_path: str) -> Optional[str]:
        """Pitch-shift down + reverb + grit for the ULTRON persona."""
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.debug("pydub not installed; skipping ULTRON DSP")
            return None

        if not _has_ffmpeg():
            logger.debug("ffmpeg not found; skipping ULTRON DSP")
            return None

        try:
            seg = AudioSegment.from_mp3(mp3_path)

            # 1) Pitch down ~3 semitones via frame rate manipulation.
            #    Lowering playback rate lowers pitch (and slows slightly,
            #    which adds to the heavy ULTRON feel).
            pitch_factor = 2 ** (-3.0 / 12.0)          # ~0.84
            slowed = seg._spawn(
                seg.raw_data, overrides={"frame_rate": int(seg.frame_rate * pitch_factor)}
            ).set_frame_rate(seg.frame_rate)

            # 2) Gentle distortion / saturation for metallic grit.
            target_dbfs = slowed.max_dBFS - 6
            gain = target_dbfs - slowed.max_dBFS
            loud = slowed.apply_gain(gain) if math.isfinite(gain) else slowed
            distorted = loud.distortion(threshold=1.2, gain=25, range_=20, offset=10)

            # 3) Reverb via layered decaying echoes.
            reverbed = distorted + distorted.overlay(
                distorted.shift(sample_offset=int(distorted.frame_rate * 0.03)), gain=-8
            ).overlay(
                distorted.shift(sample_offset=int(distorted.frame_rate * 0.06)), gain=-14
            ).overlay(
                distorted.shift(sample_offset=int(distorted.frame_rate * 0.10)), gain=-20
            )

            # 4) Normalize and return to the original level.
            final = reverbed.normalize(headroom=1.0)

            out_path = mp3_path.replace(".mp3", "_ultron.mp3")
            final.export(out_path, format="mp3")
            return out_path
        except Exception as e:
            logger.warning("ULTRON DSP failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # pyttsx3 fallback
    # ------------------------------------------------------------------

    def _speak_pyttsx3(self, text: str):
        import re
        try:
            import pyttsx3
            engine = pyttsx3.init("sapi5")

            from app.config import config
            speed = config.get("voice", "tts_speed", 150)
            engine.setProperty("rate", speed)

            voice_id = config.get("voice", "tts_voice", "default")
            if voice_id and voice_id != "default":
                engine.setProperty("voice", voice_id)

            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                if self._stop_flag.is_set():
                    break
                if sentence.strip():
                    engine.say(sentence.strip())
                    engine.runAndWait()
        except Exception as e:
            logger.error("pyttsx3 error: %s", e)
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Playback backends
    # ------------------------------------------------------------------

    def _play_audio(self, path: str) -> bool:
        """Try available playback backends in order. Returns True on success."""
        if not os.path.exists(path):
            return False

        # 1) simpleaudio (pure-python WAV only)
        if path.lower().endswith(".wav"):
            try:
                import simpleaudio as sa
                wave_obj = sa.WaveObject.from_wave_file(path)
                wave_obj.play().wait_done()
                return True
            except Exception:
                pass

        # 2) ffplay (ships with ffmpeg)
        if shutil.which("ffplay"):
            try:
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    check=True, timeout=300,
                )
                return True
            except Exception:
                pass

        # 3) pydub playback (uses ffplay/simpleaudio underneath)
        try:
            from pydub.playback import play as pydub_play
            from pydub import AudioSegment
            if _has_ffmpeg():
                pydub_play(AudioSegment.from_file(path))
                return True
        except Exception:
            pass

        # 4) winsound (WAV only, Windows built-in)
        if path.lower().endswith(".wav"):
            try:
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
                return True
            except Exception:
                pass

        # 5) PowerShell MediaPlayer (WAV only)
        if path.lower().endswith(".wav"):
            try:
                ps = (
                    "Add-Type -AssemblyName PresentationCore; "
                    "$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open([Uri]'{path}'); $p.Play(); "
                    "Start-Sleep -Seconds 2; $p.Close()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    check=True, timeout=60,
                )
                return True
            except Exception:
                pass

        return False

    @staticmethod
    def _cleanup_files(paths):
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
