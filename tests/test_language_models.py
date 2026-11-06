"""
Tests for Phase 5 Day 3: multi-language Vosk model resolution and the
STT engine gate (no silent cloud fallback).
"""
import pytest

from voice.microphone import SAMPLE_RATE, frames_to_wav


def _silence_wav(seconds: float = 1.0) -> bytes:
    return frames_to_wav(b"\x00\x00" * int(SAMPLE_RATE * seconds))


class TestResolveModelForLanguage:
    def test_english_resolves_bundled_model(self):
        from voice.stt_vosk import resolve_model_for_language

        path = resolve_model_for_language("en-US")
        assert path is not None
        assert "en" in path.lower()

    def test_hindi_resolves_when_installed(self):
        from voice.stt_vosk import resolve_model_for_language

        path = resolve_model_for_language("hi-IN")
        if path is None:
            pytest.skip("Hindi Vosk model not installed")
        assert "hi" in path.lower()

    def test_unknown_language_returns_none(self):
        from voice.stt_vosk import resolve_model_for_language

        assert resolve_model_for_language("fr-FR") is None

    def test_hindi_found_in_custom_root(self, tmp_path):
        from voice.stt_vosk import resolve_model_for_language

        (tmp_path / "vosk-model-small-hi-0.22" / "am").mkdir(parents=True)
        resolved = resolve_model_for_language("hi-IN", models_root=str(tmp_path))
        assert resolved is not None
        assert resolved.endswith("vosk-model-small-hi-0.22")

    def test_broken_model_dir_is_skipped(self, tmp_path):
        from voice.stt_vosk import resolve_model_for_language

        # Alphabetically first dir matches the hi prefix but lacks am/
        (tmp_path / "vosk-model-small-hi-0.1").mkdir()
        (tmp_path / "vosk-model-small-hi-0.22" / "am").mkdir(parents=True)
        resolved = resolve_model_for_language("hi-IN", models_root=str(tmp_path))
        assert resolved is not None
        assert resolved.endswith("vosk-model-small-hi-0.22")

    def test_english_found_in_custom_root(self, tmp_path):
        from voice.stt_vosk import resolve_model_for_language

        (tmp_path / "vosk-model-en-us-0.22" / "am").mkdir(parents=True)
        resolved = resolve_model_for_language("en-US", models_root=str(tmp_path))
        assert resolved is not None
        assert resolved.endswith("vosk-model-en-us-0.22")


class TestVoskSTTLanguages:
    def test_hindi_transcription_uses_hindi_model(self):
        import voice.stt_vosk as stt_vosk
        from voice.stt_vosk import VoskSTT, resolve_model_for_language

        hi_path = resolve_model_for_language("hi-IN")
        if not hi_path:
            pytest.skip("Hindi Vosk model not installed")

        en_path = resolve_model_for_language("en-US")
        stt = VoskSTT(model_path=en_path)
        text = stt.transcribe_wav(_silence_wav(1.0), language="hi-IN")
        assert isinstance(text, str)
        # Hindi model was loaded into the process-wide cache (transcription
        # did not silently run the English model on Hindi audio).
        assert hi_path in stt_vosk._MODEL_CACHE

    def test_unsupported_language_falls_back_to_english_model(self):
        import voice.stt_vosk as stt_vosk
        from voice.stt_vosk import VoskSTT, resolve_model_for_language

        en_path = resolve_model_for_language("en-US")
        stt = VoskSTT(model_path=en_path)
        text = stt.transcribe_wav(_silence_wav(0.5), language="fr-FR")
        assert isinstance(text, str)
        assert en_path in stt_vosk._MODEL_CACHE

    def test_english_transcription_still_works(self):
        from voice.stt_vosk import VoskSTT, resolve_model_for_language

        stt = VoskSTT(model_path=resolve_model_for_language("en-US"))
        text = stt.transcribe_wav(_silence_wav(0.5), language="en-US")
        assert isinstance(text, str)


class TestEngineGate:
    """voice.allow_cloud_fallback must gate requests, never silently flip them."""

    @pytest.fixture()
    def recognizer(self):
        from voice.speech_recognition import SpeechRecognizer

        return SpeechRecognizer()

    @staticmethod
    def _with_engine(vosk_mode: bool, cloud_fallback: bool):
        from app.config import config

        saved_engine = config.get("voice", "stt_engine", "google_free")
        saved_fallback = config.get("voice", "allow_cloud_fallback", False)
        config.set("voice", "stt_engine", "vosk_local" if vosk_mode else "google_free")
        config.set("voice", "allow_cloud_fallback", cloud_fallback)
        return saved_engine, saved_fallback

    @staticmethod
    def _restore(saved_engine, saved_fallback):
        from app.config import config

        config.set("voice", "stt_engine", saved_engine)
        config.set("voice", "allow_cloud_fallback", saved_fallback)

    def test_english_never_gated(self, recognizer):
        saved = self._with_engine(vosk_mode=True, cloud_fallback=False)
        try:
            engine, error = recognizer._decide_engine("en-US")
            assert (engine, error) == ("vosk_local", None)
        finally:
            self._restore(*saved)

    def test_unsupported_language_blocked_without_consent(self, recognizer):
        saved = self._with_engine(vosk_mode=True, cloud_fallback=False)
        try:
            engine, error = recognizer._decide_engine("fr-FR")
            assert engine == "vosk_local"
            assert error is not None and "Vosk model" in error
        finally:
            self._restore(*saved)

    def test_unsupported_language_falls_back_with_consent(self, recognizer):
        saved = self._with_engine(vosk_mode=True, cloud_fallback=True)
        try:
            engine, error = recognizer._decide_engine("fr-FR")
            assert (engine, error) == ("google_free", None)
        finally:
            self._restore(*saved)

    def test_google_engine_never_gated(self, recognizer):
        saved = self._with_engine(vosk_mode=False, cloud_fallback=False)
        try:
            engine, error = recognizer._decide_engine("fr-FR")
            assert (engine, error) == ("google_free", None)
        finally:
            self._restore(*saved)

    def test_hindi_allowed_when_model_installed(self, recognizer):
        from voice.stt_vosk import resolve_model_for_language

        saved = self._with_engine(vosk_mode=True, cloud_fallback=False)
        try:
            engine, error = recognizer._decide_engine("hi-IN")
            if resolve_model_for_language("hi-IN"):
                assert (engine, error) == ("vosk_local", None)
            else:
                assert error is not None
        finally:
            self._restore(*saved)
