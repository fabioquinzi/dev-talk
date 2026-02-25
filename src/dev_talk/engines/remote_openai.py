"""OpenAI Whisper API engine for remote transcription.

Uses the OpenAI Python SDK to send audio to the Whisper API.
Requires an API key configured in settings.
"""

from __future__ import annotations

import io
import logging
import struct
import wave

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "whisper-1"


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16_000) -> bytes:
    """Convert a float32 numpy array to WAV bytes for API upload."""
    # Convert float32 [-1.0, 1.0] to int16
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    return buf.getvalue()


class OpenAIWhisperEngine:
    """Speech-to-text engine using OpenAI's Whisper API."""

    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # Lazy initialization

    def _ensure_client(self) -> None:
        """Lazy-create the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
            logger.info("OpenAI client initialized, model: %s", self._model)

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe audio via OpenAI Whisper API.

        Args:
            audio: 1D float32 numpy array at 16kHz.
            language: Language code.

        Returns:
            Transcribed text string.
        """
        self._ensure_client()

        wav_bytes = _audio_to_wav_bytes(audio)

        # Create a file-like object for the API
        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "recording.wav"

        response = self._client.audio.transcriptions.create(
            model=self._model,
            file=audio_file,
            language=language,
        )

        return response.text

    def is_available(self) -> bool:
        """Check if the API key is configured."""
        return bool(self._api_key)

    def get_name(self) -> str:
        return f"OpenAI Whisper ({self._model})"

    @property
    def api_key(self) -> str:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key = value
        self._client = None  # Force re-initialization

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value
