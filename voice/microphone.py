"""
VERONIKA AI - Microphone Manager
Handles microphone input with proper resource management.
"""
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MicrophoneManager:
    """Manages microphone access with proper lifecycle control."""

    def __init__(self):
        self._is_recording = False
        self._lock = threading.Lock()
        self._audio = None
        self._stream = None

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

    def release(self):
        """Release all audio resources."""
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
