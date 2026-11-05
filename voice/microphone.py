"""
VERONIKA AI - Microphone Manager
Handles microphone input with proper resource management.

Phase 5: complete recording pipeline on top of the original device listing:
  - start_recording() / stop_recording(): live capture into WAV bytes with an
    optional level callback (RMS) for UI metering and future barge-in.
  - record_seconds(): blocking convenience capture.
  - Explicit user-controlled lifecycle only: nothing here starts the mic on
    its own (directive rule: no silent microphone activation).
"""
import io
import logging
import threading
import wave
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# 16 kHz mono 16-bit -- the format Vosk models and SpeechRecognition expect.
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (16-bit PCM)
FRAMES_PER_BUFFER = 1024


def frames_to_wav(frames: bytes) -> bytes:
    """Wrap raw PCM frames in a WAV container (in memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)
    return buf.getvalue()


class MicrophoneManager:
    """Manages microphone access with proper lifecycle control."""

    def __init__(self):
        self._is_recording = False
        self._lock = threading.Lock()
        self._audio = None
        self._stream = None
        self._frames: list = []
        self._record_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def _ensure_pyaudio(self):
        """Lazily initialize PyAudio."""
        if self._audio is None:
            try:
                import pyaudio
                self._audio = pyaudio.PyAudio()
            except ImportError:
                logger.error("PyAudio not installed. Install it with: pip install pyaudio")
                raise RuntimeError(
                    "PyAudio is not installed. Voice input requires PyAudio. "
                    "Install it with: pip install pyaudio"
                )
            except Exception as e:
                logger.error("Failed to initialize audio: %s", e)
                raise RuntimeError(f"Failed to initialize audio system: {e}")

    def list_input_devices(self) -> list:
        """List available microphone input devices."""
        try:
            self._ensure_pyaudio()
            devices = []
            for i in range(self._audio.get_device_count()):
                info = self._audio.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append({
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxInputChannels"],
                    })
            return devices
        except Exception as e:
            logger.error("Failed to list audio devices: %s", e)
            return []

    def has_microphone(self) -> bool:
        """Check if any microphone input device is available."""
        return len(self.list_input_devices()) > 0

    # ------------------------------------------------------------------
    # Recording pipeline (Phase 5)
    # ------------------------------------------------------------------

    def start_recording(
        self,
        on_level: Optional[Callable[[float], None]] = None,
        device_index: Optional[int] = None,
    ):
        """Start capturing microphone audio in a background thread.

        Only call this from an explicit user action (voice button, wake word
        already active, etc.) -- the mic is never started silently.

        on_level: optional callback receiving the RMS level (0.0-1.0-ish) of
        each chunk, usable for a live mic meter / barge-in detection.
        """
        with self._lock:
            if self._is_recording:
                logger.warning("start_recording called while already recording")
                return False
            self._is_recording = True
        self._stop_flag.clear()
        self._frames = []

        def _record():
            stream = None
            try:
                self._ensure_pyaudio()
                import pyaudio
                stream = self._audio.open(
                    format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=FRAMES_PER_BUFFER,
                )
                self._stream = stream
                logger.info("Recording started (%d Hz, mono, 16-bit)", SAMPLE_RATE)
                while not self._stop_flag.is_set():
                    try:
                        data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    except Exception as e:
                        logger.error("Stream read failed: %s", e)
                        break
                    self._frames.append(data)
                    if on_level is not None:
                        try:
                            on_level(_rms_level(data))
                        except Exception:
                            pass
            except Exception as e:
                logger.error("Recording error: %s", e)
            finally:
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                with self._lock:
                    self._stream = None
                    self._is_recording = False
                logger.info(
                    "Recording stopped (%d chunks captured)", len(self._frames)
                )

        self._record_thread = threading.Thread(target=_record, daemon=True)
        self._record_thread.start()
        return True

    def stop_recording(self) -> Optional[bytes]:
        """Stop capture and return the recording as WAV bytes (or None)."""
        self._stop_flag.set()
        thread = self._record_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        self._record_thread = None
        with self._lock:
            frames = b"".join(self._frames)
            self._frames = []
        if not frames:
            return None
        return frames_to_wav(frames)

    def record_seconds(
        self,
        duration: float,
        on_level: Optional[Callable[[float], None]] = None,
        device_index: Optional[int] = None,
    ) -> Optional[bytes]:
        """Blocking capture for a fixed duration. Returns WAV bytes."""
        if not self.start_recording(on_level=on_level, device_index=device_index):
            return None
        self._stop_flag.wait(duration)
        return self.stop_recording()

    def cancel_recording(self):
        """Signal the recording loop to stop (without returning audio)."""
        self._stop_flag.set()

    def release(self):
        """Release all audio resources."""
        self._stop_flag.set()
        thread = self._record_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        self._record_thread = None
        with self._lock:
            self._is_recording = False
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._audio:
                try:
                    self._audio.terminate()
                except Exception:
                    pass
                self._audio = None

    def __del__(self):
        self.release()


def _rms_level(pcm_bytes: bytes) -> float:
    """RMS level of a 16-bit mono PCM chunk, normalized to roughly 0..1.

    Pure-python implementation: the stdlib `audioop` module was removed in
    Python 3.13 (PEP 594).
    """
    import struct
    n = len(pcm_bytes) // SAMPLE_WIDTH
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm_bytes[: n * SAMPLE_WIDTH])
    sum_sq = 0
    for s in samples:
        sum_sq += s * s
    rms = (sum_sq / n) ** 0.5
    return min(1.0, rms / 10000.0)
