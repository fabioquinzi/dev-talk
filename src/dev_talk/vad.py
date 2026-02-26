"""Voice activity detection and audio energy gating.

Provides pre-engine filtering to prevent Whisper from hallucinating
text on silent or noise-only audio. Two layers:

1. Energy gate — skip audio below an RMS dB threshold (essentially free)
2. Silero VAD — neural speech detector, <1ms per 32ms window
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
VAD_WINDOW_SAMPLES = 512  # 32ms at 16kHz — required by Silero VAD


def compute_rms_db(audio: np.ndarray) -> float:
    """Compute RMS energy in decibels for a float32 audio buffer.

    Returns -inf for digital silence (all zeros).
    """
    if audio.size == 0:
        return -math.inf
    rms = float(np.sqrt(np.mean(audio**2)))
    if rms == 0.0:
        return -math.inf
    return 20.0 * math.log10(rms)


def is_silent(audio: np.ndarray, threshold_db: float = -40.0) -> bool:
    """Return True if audio RMS energy is below the threshold."""
    return compute_rms_db(audio) < threshold_db


class VoiceActivityDetector:
    """Wraps silero-vad-lite for speech detection.

    Processes audio in 32ms (512-sample) windows and checks whether
    any window contains speech above the probability threshold.
    """

    def __init__(self, threshold: float = 0.35) -> None:
        self._threshold = threshold
        self._vad = None
        self._available = True

    def _ensure_loaded(self) -> None:
        """Import and initialize silero-vad-lite on first call."""
        if self._vad is not None or not self._available:
            return
        try:
            from silero_vad_lite import SileroVAD

            self._vad = SileroVAD(SAMPLE_RATE)
            logger.info("Silero VAD loaded")
        except ImportError:
            self._available = False
            logger.warning(
                "silero-vad-lite not installed — VAD disabled. "
                "Install with: pip install silero-vad-lite"
            )

    def contains_speech(self, audio: np.ndarray) -> bool:
        """Return True if audio likely contains speech.

        Processes the buffer in 512-sample (32ms) windows. Returns True
        if any window exceeds the speech probability threshold.

        Falls back to True (pass-through) if silero-vad-lite is not installed.
        """
        self._ensure_loaded()
        if self._vad is None:
            return True  # Graceful degradation

        audio = np.ascontiguousarray(audio, dtype=np.float32)
        n_samples = audio.size

        for start in range(0, n_samples - VAD_WINDOW_SAMPLES + 1, VAD_WINDOW_SAMPLES):
            window = audio[start : start + VAD_WINDOW_SAMPLES]
            prob = self._vad.process(memoryview(window.data))
            if prob >= self._threshold:
                return True

        return False
