"""Tests for MLX Whisper engine."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dev_talk.engines.local_mlx import DEFAULT_MODEL, MLXWhisperEngine
from dev_talk.transcriber import TranscriberEngine


class TestMLXWhisperEngine:
    def test_satisfies_protocol(self):
        engine = MLXWhisperEngine()
        assert isinstance(engine, TranscriberEngine)

    def test_default_model(self):
        engine = MLXWhisperEngine()
        assert engine.model == DEFAULT_MODEL

    def test_custom_model(self):
        engine = MLXWhisperEngine(model="mlx-community/whisper-tiny")
        assert engine.model == "mlx-community/whisper-tiny"

    def test_get_name(self):
        engine = MLXWhisperEngine()
        assert "whisper-large-v3-turbo" in engine.get_name()

    def test_model_setter_resets_lazy_import(self):
        engine = MLXWhisperEngine()
        engine._mlx_whisper = MagicMock()  # Simulate loaded state
        engine.model = "mlx-community/whisper-tiny"
        assert engine._mlx_whisper is None  # Should reset

    @patch("dev_talk.engines.local_mlx.platform")
    def test_is_available_non_arm(self, mock_platform):
        mock_platform.machine.return_value = "x86_64"
        engine = MLXWhisperEngine()
        assert engine.is_available() is False

    @patch("dev_talk.engines.local_mlx.platform")
    def test_is_available_arm64_with_mlx(self, mock_platform):
        mock_platform.machine.return_value = "arm64"
        engine = MLXWhisperEngine()
        # mlx_whisper is installed in our test env, so this should be True
        assert engine.is_available() is True

    def test_transcribe_calls_mlx_whisper(self):
        engine = MLXWhisperEngine()
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "hello world"}
        engine._mlx_whisper = mock_mlx

        audio = np.ones(16000, dtype=np.float32)
        result = engine.transcribe(audio)

        assert result == "hello world"
        mock_mlx.transcribe.assert_called_once()

        # Verify key kwargs
        call_kwargs = mock_mlx.transcribe.call_args
        assert call_kwargs.kwargs["path_or_hf_repo"] == DEFAULT_MODEL
        assert call_kwargs.kwargs["language"] == "en"
        assert call_kwargs.kwargs["verbose"] is False
        assert call_kwargs.kwargs["condition_on_previous_text"] is False
        assert call_kwargs.kwargs["word_timestamps"] is True
        assert call_kwargs.kwargs["hallucination_silence_threshold"] == 1.0
        assert call_kwargs.kwargs["no_speech_threshold"] == 0.3
        assert call_kwargs.kwargs["temperature"] == (0.0,)

    def test_transcribe_with_language(self):
        engine = MLXWhisperEngine()
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "bonjour"}
        engine._mlx_whisper = mock_mlx

        audio = np.ones(16000, dtype=np.float32)
        engine.transcribe(audio, language="fr")

        call_kwargs = mock_mlx.transcribe.call_args
        assert call_kwargs.kwargs["language"] == "fr"

    def test_transcribe_empty_result(self):
        engine = MLXWhisperEngine()
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {}
        engine._mlx_whisper = mock_mlx

        audio = np.ones(16000, dtype=np.float32)
        result = engine.transcribe(audio)
        assert result == ""

    def test_lazy_import_called_once(self):
        engine = MLXWhisperEngine()
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "test"}

        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            engine._ensure_loaded()
            first_ref = engine._mlx_whisper
            engine._ensure_loaded()  # Should not re-import
            assert engine._mlx_whisper is first_ref

    def test_warmup_loads_and_transcribes(self):
        engine = MLXWhisperEngine()
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": ""}
        engine._mlx_whisper = mock_mlx

        engine.warmup()

        assert engine._warmed_up is True
        mock_mlx.transcribe.assert_called_once()
        # Verify it used a 1-second silent array
        call_args = mock_mlx.transcribe.call_args
        audio_arg = call_args.args[0]
        assert audio_arg.shape == (16000,)
        assert float(audio_arg.max()) == 0.0

    def test_warmup_sets_flag(self):
        engine = MLXWhisperEngine()
        assert engine._warmed_up is False
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": ""}
        engine._mlx_whisper = mock_mlx

        engine.warmup()
        assert engine._warmed_up is True

    def test_model_setter_resets_warmup(self):
        engine = MLXWhisperEngine()
        engine._warmed_up = True
        engine._mlx_whisper = MagicMock()

        engine.model = "mlx-community/whisper-tiny"
        assert engine._warmed_up is False
