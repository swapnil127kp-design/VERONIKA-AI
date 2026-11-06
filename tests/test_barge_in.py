"""
VERONIKA AI - Barge-In Detection Tests (Phase 5, Day 2)

Covers the BargeInDecider decision core (pure logic) and the
BargeInMonitor lifecycle without requiring real audio hardware.
"""
import pytest

from voice.barge_in import BargeInDecider, BargeInMonitor
from voice.microphone import MicrophoneManager


class TestBargeInDecider:
    """Decision-core behavior with synthetic, timestamped level samples."""

    def _make(self):
        return BargeInDecider(
            threshold=0.30, sustain_seconds=0.35, cooldown_seconds=2.0
        )

    def test_silence_never_triggers(self):
        d = self._make()
        assert not any(
            d.feed(ts=i * 0.05, level=0.02) for i in range(40)
        )

    def test_first_trigger_requires_sustain(self):
        d = self._make()
        results = [d.feed(ts=i * 0.05, level=0.60) for i in range(30)]
        # First trigger exactly when the sustained window is reached.
        assert results[:7] == [False] * 7
        assert results[7] is True          # ts = 0.35
        assert not any(results[8:])        # cooldown suppresses the rest

    def test_short_blips_reset_window(self):
        """Speech bursts shorter than the sustain window never trigger."""
        d = self._make()
        ts = 0.0
        for _ in range(5):
            for _i in range(4):        # 0.20s burst < 0.35s sustain
                assert not d.feed(ts=ts, level=0.80)
                ts += 0.05
            for _i in range(4):        # pause below threshold resets window
                assert not d.feed(ts=ts, level=0.01)
                ts += 0.05
        # And trailing silence stays quiet.
        assert not any(
            d.feed(ts=ts + i * 0.05, level=0.01) for i in range(10)
        )

    def test_pause_splits_two_short_bursts(self):
        """Two sub-sustain bursts separated by silence must not add up."""
        d = self._make()
        ts = 0.0
        for _i in range(5):   # loud 0.25s
            assert not d.feed(ts=ts, level=0.80)
            ts += 0.05
        for _i in range(3):   # quiet gap
            assert not d.feed(ts=ts, level=0.0)
            ts += 0.05
        for _i in range(5):   # loud 0.25s again
            assert not d.feed(ts=ts, level=0.80)
            ts += 0.05
        assert not d.feed(ts=ts, level=0.0)

    def test_cooldown_does_not_reset_sustained_timer(self):
        """Continuous speech: first trigger, then next no earlier than cooldown."""
        d = self._make()
        triggers = []
        ts = 0.0
        for _i in range(100):   # 5s of continuous speech
            if d.feed(ts=ts, level=0.60):
                triggers.append(ts)
            ts += 0.05
        assert triggers and abs(triggers[0] - 0.35) < 0.051
        # No trigger may occur sooner than first + cooldown (2.0s).
        for prev, nxt in zip(triggers, triggers[1:]):
            assert nxt - prev >= 1.999
        # With continuous speech the second trigger lands right after cooldown.
        assert abs(triggers[1] - 2.35) < 0.051

    def test_boundary_level_counts_as_high(self):
        d = self._make()
        assert any(
            d.feed(ts=i * 0.05, level=0.30) for i in range(12)
        )


class TestBargeInMonitor:
    """Lifecycle safety without needing actual audio hardware."""

    def test_stop_when_never_started_is_safe(self):
        monitor = BargeInMonitor(mic_manager=MicrophoneManager())
        assert not monitor.is_active
        monitor.stop()  # must not raise
        assert not monitor.is_active

    def test_level_feed_via_monitor_does_not_crash(self):
        """The mic callback path stays safe with no interrupt callback set."""
        monitor = BargeInMonitor(mic_manager=MicrophoneManager())
        monitor._on_level(0.99)   # no decider configured -> no-op
        assert not monitor.is_active
