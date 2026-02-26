"""Local MLX Whisper engine for Apple Silicon.

Uses mlx-whisper to run Whisper models natively on Apple GPU/ANE.
Model is auto-downloaded from HuggingFace on first use (~1.6 GB).
"""

from __future__ import annotations

import logging
import platform
import threading

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


class MLXWhisperEngine:
    """Speech-to-text engine using MLX Whisper on Apple Silicon."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._mlx_whisper = None  # Lazy import to avoid slow startup
        self._warmed_up = False
        self._gpu_lock = threading.Lock()  # Metal can't handle concurrent transcriptions

    def _ensure_loaded(self) -> None:
        """Import mlx_whisper module."""
        if self._mlx_whisper is None:
            import mlx_whisper

            self._mlx_whisper = mlx_whisper
            logger.info("MLX Whisper loaded, model: %s", self._model)

    def warmup(self) -> None:
        """Download (if needed) and load the model into memory.

        Runs a tiny silent transcription to force huggingface_hub to
        download the model and MLX to load weights onto the GPU.
        Call this at startup so the first real transcription is fast.
        """
        self._ensure_loaded()
        logger.info("Warming up model: %s", self._model)
        dummy_audio = np.zeros(16000, dtype=np.float32)  # 1s silence
        with self._gpu_lock:
            self._mlx_whisper.transcribe(
                dummy_audio,
                path_or_hf_repo=self._model,
                language="en",
                verbose=False,
            )
        self._warmed_up = True
        logger.info("Model ready: %s", self._model)

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe audio using MLX Whisper.

        Args:
            audio: 1D float32 numpy array at 16kHz.
            language: Language code (default "en").

        Returns:
            Transcribed text string.
        """
        self._ensure_loaded()

        with self._gpu_lock:
            result = self._mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=self._model,
                language=language,
                verbose=False,
                condition_on_previous_text=False,
                word_timestamps=True,
                hallucination_silence_threshold=1.0,
                no_speech_threshold=0.3,
                temperature=(0.0,),
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
        self._warmed_up = False
