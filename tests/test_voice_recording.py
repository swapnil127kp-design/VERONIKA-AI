"""
VERONIKA AI - Voice Recording Tests (Phase 5)

Tests the microphone recording pipeline, Vosk STT integration, and
privacy-aware speech recognition orchestration.
"""
import os
import pytest
from voice.microphone import MicrophoneManager, frames_to_wav, SAMPLE_RATE


class TestMicrophoneManager:
    """Test microphone device management and recording lifecycle."""

    def test_device_listing(self):
        """Should list available input devices without crashing."""
        mic = MicrophoneManager()
        try:
            devices = mic.list_input_devices()
            # Passes if returns a list (empty is OK on CI/headless systems)
            assert isinstance(devices, list)
            for dev in devices:
                assert "index" in dev
                assert "name" in dev
                assert "channels" in dev
        finally:
            mic.release()

    def test_has_microphone_property(self):
        """Should report microphone availability correctly."""
        mic = MicrophoneManager()
        try:
            # Returns bool, doesn't crash
            result = mic.has_microphone()
            assert isinstance(result, bool)
        finally:
            mic.release()

    def test_recording_state_property(self):
        """Should track recording state correctly."""
        mic = MicrophoneManager()
        try:
            assert not mic.is_recording  # starts False
            # Start recording in background
            mic.start_recording()
            # Give thread time to initialize
            import time
            time.sleep(0.1)
            # Should now report True (or False if device unavailable)
            assert isinstance(mic.is_recording, bool)
            mic.stop_recording()
            # Should return to False
            assert not mic.is_recording
        finally:
            mic.release()

    def test_frames_to_wav_format(self):
        """Generated WAV should have correct headers."""
        import wave
        import io
        # Fake 0.5s of silence
        fake_pcm = b"\x00\x00" * (SAMPLE_RATE // 2)
        wav_bytes = frames_to_wav(fake_pcm)

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1  # mono
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnframes() == SAMPLE_RATE // 2


class TestVoskSTT:
    """Test local Vosk speech recognition (when available)."""

    def test_availability_check(self):
        """Should correctly report vosk + model availability."""
        from voice.stt_vosk import VoskSTT
        vosk_stt = VoskSTT()
        # Returns bool, doesn't crash
        result = vosk_stt.is_available
        assert isinstance(result, bool)

    def test_transcribe_with_fake_wav(self):
        """Should handle a well-formed WAV without crashing."""
        from voice.stt_vosk import VoskSTT
        vosk_stt = VoskSTT()
        if not vosk_stt.is_available:
            pytest.skip("Vosk unavailable (missing package or model)")

        # Generate 1 second of silence as WAV
        fake_pcm = b"\x00\x00" * SAMPLE_RATE
        wav_bytes = frames_to_wav(fake_pcm)

        # Should transcribe (result will be empty for silence, but shouldn't crash)
        text = vosk_stt.transcribe_wav(wav_bytes)
        assert isinstance(text, str)


class TestSpeechRecognizer:
    """Test the speech recognition orchestrator (google_free and vosk_local)."""

    def test_initialization(self):
        """Should initialize without crashing."""
        from voice.speech_recognition import SpeechRecognizer
        sr = SpeechRecognizer()
        assert not sr.is_listening

    def test_supported_languages(self):
        """Should return language list."""
        from voice.speech_recognition import SpeechRecognizer
        sr = SpeechRecognizer()
        langs = sr.get_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) > 0
        # Should have en-US at minimum
        codes = [lang["code"] for lang in langs]
        assert "en-US" in codes

    def test_cancel_while_not_listening(self):
        """Should handle cancel when not listening."""
        from voice.speech_recognition import SpeechRecognizer
        sr = SpeechRecognizer()
        sr.cancel()  # should not crash
        assert not sr.is_listening


@pytest.mark.integration
class TestVoiceIntegration:
    """Integration tests for complete voice pipeline (manual/slow tests)."""

    def test_record_and_transcribe_vosk(self):
        """
        Record 2 seconds of audio and attempt Vosk transcription.

        NOTE: This is a manual integration test -- requires a working
        microphone and someone to speak during the recording window.
        Skipped in automated CI (no real microphone/speech).
        """
        pytest.skip("Manual integration test (requires human speech)")

        from voice.microphone import MicrophoneManager
        from voice.stt_vosk import VoskSTT

        mic = MicrophoneManager()
        vosk = VoskSTT()

        if not vosk.is_available:
            pytest.skip("Vosk unavailable")
        if not mic.has_microphone():
            pytest.skip("No microphone detected")

        try:
            print("Recording 2 seconds... please speak!")
            wav = mic.record_seconds(2.0)
            assert wav is not None

            print("Transcribing with Vosk...")
            text = vosk.transcribe_wav(wav)
            print(f"Result: {text}")

            # Text might be empty (silence/unclear), but should be string
            assert isinstance(text, str)
        finally:
            mic.release()

    def test_speech_recognizer_vosk_mode(self):
        """
        Test SpeechRecognizer with vosk_local engine.

        Manual test -- requires voice input.
        """
        pytest.skip("Manual integration test (requires human speech)")

        from voice.speech_recognition import SpeechRecognizer
        from app.config import config
        import time

        # Force vosk mode
        config.set("voice", "stt_engine", "vosk_local")

        sr = SpeechRecognizer()
        result_text = []
        error_text = []

        def on_result(text):
            result_text.append(text)
            print(f"Recognized: {text}")

        def on_error(err):
            error_text.append(err)
            print(f"Error: {err}")

        print("Starting recognition (10s timeout)... please speak!")
        sr.recognize_speech(
            language="en-US",
            on_result=on_result,
            on_error=on_error,
            timeout=10.0,
            phrase_time_limit=5.0,
        )

        # Wait for completion
        time.sleep(6.0)

        # Should have gotten either result or error
        assert len(result_text) > 0 or len(error_text) > 0
