"""Tests for OpenAI Whisper API engine."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dev_talk.engines.remote_openai import (
    DEFAULT_MODEL,
    OpenAIWhisperEngine,
    _audio_to_wav_bytes,
)
from dev_talk.transcriber import TranscriberEngine


class TestAudioToWavBytes:
    def test_produces_valid_wav(self):
        audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        wav_bytes = _audio_to_wav_bytes(audio)

        # WAV files start with "RIFF"
        assert wav_bytes[:4] == b"RIFF"
        # Should contain "WAVE" format marker
        assert wav_bytes[8:12] == b"WAVE"

    def test_correct_length(self):
        audio = np.zeros(16000, dtype=np.float32)  # 1 second
        wav_bytes = _audio_to_wav_bytes(audio)

        # WAV header is 44 bytes, data is 16000 * 2 bytes (int16)
        expected_size = 44 + 16000 * 2
        assert len(wav_bytes) == expected_size

    def test_clipping(self):
        # Values outside [-1, 1] should be clipped
        audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)
        wav_bytes = _audio_to_wav_bytes(audio)
        assert wav_bytes[:4] == b"RIFF"  # Should still produce valid WAV


class TestOpenAIWhisperEngine:
    def test_satisfies_protocol(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")
        assert isinstance(engine, TranscriberEngine)

    def test_default_model(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")
        assert engine.model == DEFAULT_MODEL

    def test_custom_model(self):
        engine = OpenAIWhisperEngine(api_key="sk-test", model="gpt-4o-mini-transcribe")
        assert engine.model == "gpt-4o-mini-transcribe"

    def test_get_name(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")
        assert "whisper-1" in engine.get_name()
        assert "OpenAI" in engine.get_name()

    def test_is_available_with_key(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")
        assert engine.is_available() is True

    def test_is_not_available_without_key(self):
        engine = OpenAIWhisperEngine(api_key="")
        assert engine.is_available() is False

    def test_api_key_setter_resets_client(self):
        engine = OpenAIWhisperEngine(api_key="sk-old")
        engine._client = MagicMock()  # Simulate initialized client

        engine.api_key = "sk-new"
        assert engine._client is None  # Should reset
        assert engine.api_key == "sk-new"

    def test_transcribe_calls_api(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "hello world"
        mock_client.audio.transcriptions.create.return_value = mock_response
        engine._client = mock_client

        audio = np.ones(16000, dtype=np.float32)
        result = engine.transcribe(audio)

        assert result == "hello world"
        mock_client.audio.transcriptions.create.assert_called_once()

        # Verify model and language were passed
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs["model"] == "whisper-1"
        assert call_kwargs.kwargs["language"] == "en"

    def test_transcribe_with_language(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "bonjour"
        mock_client.audio.transcriptions.create.return_value = mock_response
        engine._client = mock_client

        engine.transcribe(np.ones(16000, dtype=np.float32), language="fr")

        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs["language"] == "fr"

    def test_lazy_client_creation(self):
        engine = OpenAIWhisperEngine(api_key="sk-test")
        assert engine._client is None

        mock_client = MagicMock()
        with patch.dict("sys.modules", {"openai": MagicMock()}):
            import sys
            sys.modules["openai"].OpenAI.return_value = mock_client
            engine._ensure_client()
            assert engine._client is mock_client

            # Second call should not re-create
            old_client = engine._client
            engine._ensure_client()
            assert engine._client is old_client
