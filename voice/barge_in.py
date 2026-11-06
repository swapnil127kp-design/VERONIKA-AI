"""
VERONIKA AI - Barge-In Detection (Phase 5, Day 2)

Lets the owner interrupt VERONIKA's voice output simply by speaking.

A light monitor keeps microphone RMS metering running while the assistant
speaks. If the level stays above a configurable threshold for a sustained
window, the monitor fires an interrupt callback (the UI stops the current
TTS playback).

Privacy: only the locally-computed RMS level callback is consumed here.
No transcription of these chunks happens and no audio leaves the machine
through this module. Transcription of spoken commands remains under the
existing STT engine's privacy settings (google_free uploads audio to
Google; vosk_local is fully offline).

Self-hearing guard: the assistant's own loudspeaker playback also raises
the mic level, so the gate is config-opt-in (voice.barge_in_enabled,
default off), the threshold is configurable, and the UI Stop button
remains available as a guaranteed manual fallback.
"""
import logging
import threading
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.30         # normalized RMS level (see microphone._rms_level)
DEFAULT_SUSTAIN_SECONDS = 0.35   # sustained speech required before interrupting
DEFAULT_COOLDOWN_SECONDS = 2.0   # ignore re-triggers shortly after an interrupt


class BargeInDecider:
    """Pure decision logic over (timestamp, level) samples. Unit-testable."""

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        sustain_seconds: float = DEFAULT_SUSTAIN_SECONDS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.threshold = threshold
        self.sustain_seconds = sustain_seconds
        self.cooldown_seconds = cooldown_seconds
        self._first_high_ts: Optional[float] = None
        self._last_interrupt_ts = float("-inf")

    def feed(self, ts: float, level: float) -> bool:
        """Consume one level sample. Returns True exactly when to interrupt."""
        if level >= self.threshold:
            if self._first_high_ts is None:
                self._first_high_ts = ts
            if ts - self._first_high_ts >= self.sustain_seconds:
                if ts - self._last_interrupt_ts >= self.cooldown_seconds:
                    self._last_interrupt_ts = ts
                    self._first_high_ts = None
                    return True
                # Still sustained, but inside the cooldown window: keep the
                # sustained timer running so the next trigger lands as soon
                # as the cooldown expires (resetting here would re-arm the
                # build-up every sample and defeat the cooldown entirely).
                return False
            return False
        # Below threshold: reset the sustained window.
        self._first_high_ts = None
        return False


class BargeInMonitor:
    """Watches mic levels while the assistant speaks and fires interrupts.

    Uses MicrophoneManager background metering (single owner stream; the
    recorder thread owns the PyAudio stream, consistent with the mic fix).
    """

    def __init__(self, mic_manager=None):
        from voice.microphone import MicrophoneManager
        self._mic = mic_manager if mic_manager is not None else MicrophoneManager()
        self._decider: Optional[BargeInDecider] = None
        self._on_interrupt: Optional[Callable[[], None]] = None
        self._active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self, on_interrupt: Callable[[], None]) -> bool:
        """Start monitoring while the assistant speaks. Not thread-safe."""
        from app.config import config

        threshold = float(config.get("voice", "barge_in_threshold", DEFAULT_THRESHOLD))
        sustain = float(config.get("voice", "barge_in_sustain_ms", DEFAULT_SUSTAIN_SECONDS * 1000)) / 1000.0
        cooldown = float(config.get("voice", "barge_in_cooldown_ms", DEFAULT_COOLDOWN_SECONDS * 1000)) / 1000.0

        with self._lock:
            if self._active:
                logger.warning("Barge-in monitor already active")
                return False
            self._decider = BargeInDecider(threshold, sustain, cooldown)
            self._on_interrupt = on_interrupt
            started = self._mic.start_recording(on_level=self._on_level)
            if not started:
                logger.warning("Barge-in: mic metering unavailable (engine busy?)")
                self._decider = None
                self._on_interrupt = None
                return False
            self._active = True
            logger.info(
                "Barge-in monitoring started (threshold=%.2f sustain=%.2fs cooldown=%.2fs)",
                threshold, sustain, cooldown,
            )
            return True

    def _on_level(self, level: float):
        """Mic RMS callback (recorder thread)."""
        decider = self._decider
        cb = self._on_interrupt
        if decider is None or cb is None:
            return
        if decider.feed(time.monotonic(), level):
            logger.info("Barge-in: sustained speech detected -> interrupt")
            try:
                cb()
            except Exception:
                logger.exception("Barge-in interrupt callback failed")

    def stop(self):
        """Stop monitoring. Safe to call even if never started."""
        with self._lock:
            if not self._active and self._decider is None:
                # Never started: nothing to tear down.
                self._decider = None
                self._on_interrupt = None
                return
            self._active = False
            self._decider = None
            self._on_interrupt = None
        try:
            self._mic.stop_recording()
        except Exception:
            logger.exception("Barge-in: mic metering teardown failed")
