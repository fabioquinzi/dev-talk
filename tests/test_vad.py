"""Tests for voice activity detection and energy gating."""

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dev_talk.vad import (
    VoiceActivityDetector,
    compute_rms_db,
    is_silent,
)


class TestComputeRmsDb:
    def test_silence_returns_negative_infinity(self):
        audio = np.zeros(16000, dtype=np.float32)
        assert compute_rms_db(audio) == -math.inf

    def test_empty_returns_negative_infinity(self):
        audio = np.array([], dtype=np.float32)
        assert compute_rms_db(audio) == -math.inf

    def test_full_scale_returns_zero_db(self):
        audio = np.ones(16000, dtype=np.float32)
        assert abs(compute_rms_db(audio) - 0.0) < 0.1

    def test_half_amplitude(self):
        audio = np.full(16000, 0.5, dtype=np.float32)
        db = compute_rms_db(audio)
        # 20 * log10(0.5) ≈ -6.02 dB
        assert abs(db - (-6.02)) < 0.1

    def test_quiet_noise(self):
        rng = np.random.default_rng(42)
        audio = rng.standard_normal(16000).astype(np.float32) * 0.0001
        db = compute_rms_db(audio)
        assert db < -70.0  # Very quiet


class TestIsSilent:
    def test_zeros_are_silent(self):
        assert is_silent(np.zeros(16000, dtype=np.float32)) is True

    def test_loud_audio_is_not_silent(self):
        assert is_silent(np.ones(16000, dtype=np.float32)) is False

    def test_default_threshold(self):
        # Audio at -50 dB should be silent at default -40 dB threshold
        audio = np.full(16000, 0.003, dtype=np.float32)
        assert is_silent(audio) is True

    def test_custom_threshold(self):
        audio = np.full(16000, 0.1, dtype=np.float32)
        # -20 dB audio, silent at -10 dB threshold, not at -30 dB
        assert is_silent(audio, threshold_db=-10.0) is True
        assert is_silent(audio, threshold_db=-30.0) is False


class TestVoiceActivityDetector:
    @patch("dev_talk.vad.SileroVAD", create=True)
    def test_contains_speech_returns_true(self, MockSileroVAD):
        mock_vad = MockSileroVAD.return_value
        mock_vad.process.return_value = 0.9

        with patch.dict("sys.modules", {"silero_vad_lite": MagicMock(SileroVAD=MockSileroVAD)}):
            detector = VoiceActivityDetector(threshold=0.5)
            audio = np.ones(1024, dtype=np.float32)
            assert detector.contains_speech(audio) is True

    @patch("dev_talk.vad.SileroVAD", create=True)
    def test_contains_speech_returns_false_for_silence(self, MockSileroVAD):
        mock_vad = MockSileroVAD.return_value
        mock_vad.process.return_value = 0.1

        with patch.dict("sys.modules", {"silero_vad_lite": MagicMock(SileroVAD=MockSileroVAD)}):
            detector = VoiceActivityDetector(threshold=0.5)
            audio = np.zeros(1024, dtype=np.float32)
            assert detector.contains_speech(audio) is False

    @patch("dev_talk.vad.SileroVAD", create=True)
    def test_one_speech_window_is_enough(self, MockSileroVAD):
        mock_vad = MockSileroVAD.return_value
        # First window has speech, rest don't
        mock_vad.process.side_effect = [0.8, 0.1, 0.1, 0.1]

        with patch.dict("sys.modules", {"silero_vad_lite": MagicMock(SileroVAD=MockSileroVAD)}):
            detector = VoiceActivityDetector(threshold=0.5)
            audio = np.ones(2048, dtype=np.float32)
            assert detector.contains_speech(audio) is True
            # Should have stopped after finding the first speech window
            assert mock_vad.process.call_count == 1

    def test_lazy_loading(self):
        detector = VoiceActivityDetector()
        assert detector._vad is None  # Not loaded until first use

    def test_graceful_degradation_when_not_installed(self):
        detector = VoiceActivityDetector()
        detector._available = True
        detector._vad = None

        # Simulate ImportError
        with patch.dict("sys.modules", {"silero_vad_lite": None}):
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                detector._ensure_loaded()

        assert detector._available is False
        # Should return True (pass-through) when VAD unavailable
        audio = np.zeros(1024, dtype=np.float32)
        assert detector.contains_speech(audio) is True

    @patch("dev_talk.vad.SileroVAD", create=True)
    def test_audio_shorter_than_window_returns_false(self, MockSileroVAD):
        """Audio shorter than 512 samples can't fill one VAD window."""
        mock_vad = MockSileroVAD.return_value

        with patch.dict("sys.modules", {"silero_vad_lite": MagicMock(SileroVAD=MockSileroVAD)}):
            detector = VoiceActivityDetector(threshold=0.5)
            audio = np.ones(100, dtype=np.float32)
            assert detector.contains_speech(audio) is False
            mock_vad.process.assert_not_called()
