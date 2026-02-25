"""Local MLX Whisper engine for Apple Silicon.

Uses mlx-whisper to run Whisper models natively on Apple GPU/ANE.
Model is auto-downloaded from HuggingFace on first use (~1.6 GB).
"""

from __future__ import annotations

import logging
import platform

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


class MLXWhisperEngine:
    """Speech-to-text engine using MLX Whisper on Apple Silicon."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._mlx_whisper = None  # Lazy import to avoid slow startup

    def _ensure_loaded(self) -> None:
        """Lazy-import mlx_whisper on first use."""
        if self._mlx_whisper is None:
            import mlx_whisper

            self._mlx_whisper = mlx_whisper
            logger.info("MLX Whisper loaded, model: %s", self._model)

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe audio using MLX Whisper.

        Args:
            audio: 1D float32 numpy array at 16kHz.
            language: Language code (default "en").

        Returns:
            Transcribed text string.
        """
        self._ensure_loaded()

        result = self._mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._model,
            language=language,
            verbose=False,
            condition_on_previous_text=True,
            hallucination_silence_threshold=1.0,
        )
        return result.get("text", "")

    def is_available(self) -> bool:
        """Check if MLX Whisper can run on this system."""
        if platform.machine() != "arm64":
            return False
        try:
            import mlx_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def get_name(self) -> str:
        return f"MLX Whisper ({self._model.split('/')[-1]})"

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
        # Force re-initialization on next transcribe
        self._mlx_whisper = None
