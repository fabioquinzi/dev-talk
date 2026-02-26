"""STT engine abstraction.

Defines the TranscriberEngine protocol and Transcriber coordinator
that supports both full-recording and chunked-streaming transcription.

Audio is filtered before reaching the engine:
1. Energy gate — skip audio below an RMS dB threshold
2. Silero VAD — skip audio with no detected speech
"""

from __future__ import annotations

import logging
from typing import Generator, Protocol, runtime_checkable

import numpy as np

from dev_talk.vad import VoiceActivityDetector, is_silent

logger = logging.getLogger(__name__)


@runtime_checkable
class TranscriberEngine(Protocol):
    """Protocol that all STT engines must implement."""

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe a numpy audio array (16kHz float32 mono) to text."""
        ...

    def is_available(self) -> bool:
        """Check if the engine is ready (model loaded, API key set, etc.)."""
        ...

    def get_name(self) -> str:
        """Return a human-readable engine name."""
        ...


class Transcriber:
    """Coordinates transcription using a pluggable engine.

    Supports two modes:
    - transcribe_full: transcribe an entire audio buffer at once
    - transcribe_streaming: transcribe an iterator of audio chunks, yielding text incrementally

    Both modes apply energy gating and VAD before sending audio to the engine.
    """

    def __init__(
        self,
        engine: TranscriberEngine,
        language: str = "en",
        vad_enabled: bool = True,
        energy_threshold_db: float = -40.0,
    ) -> None:
        self._engine = engine
        self._language = language
        self._energy_threshold_db = energy_threshold_db
        self._vad: VoiceActivityDetector | None = None
        if vad_enabled:
            self._vad = VoiceActivityDetector()

    @property
    def engine(self) -> TranscriberEngine:
        return self._engine

    @engine.setter
    def engine(self, value: TranscriberEngine) -> None:
        self._engine = value

    @property
    def engine_name(self) -> str:
        return self._engine.get_name()

    def is_available(self) -> bool:
        return self._engine.is_available()

    def _should_skip(self, audio: np.ndarray) -> bool:
        """Return True if audio should be skipped (silence or no speech)."""
        if is_silent(audio, self._energy_threshold_db):
            logger.debug("Skipping silent audio (energy gate)")
            return True
        if self._vad is not None and not self._vad.contains_speech(audio):
            logger.debug("Skipping audio with no detected speech (VAD)")
            return True
        return False

    def transcribe_full(self, audio: np.ndarray) -> str:
        """Transcribe a complete audio buffer.

        Args:
            audio: 1D float32 numpy array at 16kHz.

        Returns:
            Transcribed text string.
        """
        if audio.size == 0:
            return ""

        if self._should_skip(audio):
            return ""

        logger.debug(
            "Transcribing %.1f seconds of audio with %s",
            audio.size / 16_000,
            self.engine_name,
        )
        text = self._engine.transcribe(audio, language=self._language)
        return text.strip()

    def transcribe_streaming(
        self, audio_chunks: Generator[np.ndarray, None, None] | list[np.ndarray]
    ) -> Generator[str, None, None]:
        """Transcribe audio chunks incrementally, yielding text as it becomes available.

        Args:
            audio_chunks: Iterator of 1D float32 numpy arrays at 16kHz.

        Yields:
            Transcribed text for each chunk.
        """
        for chunk in audio_chunks:
            if chunk.size == 0:
                continue

            if self._should_skip(chunk):
                continue

            logger.debug(
                "Transcribing chunk: %.1f seconds with %s",
                chunk.size / 16_000,
                self.engine_name,
            )
            text = self._engine.transcribe(chunk, language=self._language)
            text = text.strip()
            if text:
                yield text
