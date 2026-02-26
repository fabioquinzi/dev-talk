"""Microphone management and audio recording.

Supports both full-recording and chunked-streaming capture modes.
All audio is captured at 16kHz mono (Whisper's expected format).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Generator

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "float32"


@dataclass
class AudioDevice:
    """Represents an available audio input device."""

    device_id: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool = False


class AudioManager:
    """Manages microphone enumeration and audio recording."""

    def __init__(self, device_id: int | None = None) -> None:
        self._device_id = device_id
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    @staticmethod
    def list_devices() -> list[AudioDevice]:
        """Return all available audio input devices."""
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        result = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                result.append(
                    AudioDevice(
                        device_id=i,
                        name=dev["name"],
                        channels=dev["max_input_channels"],
                        sample_rate=dev["default_samplerate"],
                        is_default=(i == default_input),
                    )
                )
        return result

    @property
    def device_id(self) -> int | None:
        return self._device_id

    @device_id.setter
    def device_id(self, value: int | None) -> None:
        if self._recording:
            raise RuntimeError("Cannot change device while recording")
        self._device_id = value

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        """Begin capturing audio from the selected microphone."""
        if self._recording:
            return

        with self._lock:
            self._frames = []
            self._recording = True

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            if status:
                pass  # Optionally log xruns
            with self._lock:
                if self._recording:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=self._device_id,
            callback=callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the full audio buffer as a 1D float32 array."""
        if not self._recording:
            return np.array([], dtype=np.float32)

        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._frames:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []
            return audio

    def get_peak_level(self) -> float:
        """Return the current peak audio level (0.0 to 1.0).

        Uses only the most recent frames for responsiveness.
        """
        with self._lock:
            if not self._frames:
                return 0.0
            # Check only the last few blocks for snappy response
            recent = self._frames[-5:] if len(self._frames) > 5 else self._frames
            audio = np.concatenate(recent, axis=0).flatten()
            return min(float(np.max(np.abs(audio))), 1.0)

    def get_chunk(self, clear: bool = True) -> np.ndarray:
        """Return currently buffered audio and optionally clear the buffer.

        Used for streaming mode: call periodically to drain buffered audio.
        """
        with self._lock:
            if not self._frames:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0).flatten()
            if clear:
                self._frames = []
            return audio

    def stream_chunks(self, chunk_duration_s: float = 3.0) -> Generator[np.ndarray, None, None]:
        """Yield audio chunks of the specified duration while recording.

        This is a blocking generator — call from a separate thread.
        Yields chunks until recording is stopped.
        """
        samples_per_chunk = int(SAMPLE_RATE * chunk_duration_s)

        buffer = np.array([], dtype=np.float32)
        while self._recording:
            chunk = self.get_chunk(clear=True)
            if chunk.size > 0:
                buffer = np.concatenate([buffer, chunk])

            if buffer.size >= samples_per_chunk:
                yield buffer[:samples_per_chunk]
                buffer = buffer[samples_per_chunk:]

            # Brief sleep to avoid busy-waiting
            import time

            time.sleep(0.1)

        # Yield any remaining audio
        remaining = self.get_chunk(clear=True)
        if remaining.size > 0:
            buffer = np.concatenate([buffer, remaining])
        if buffer.size > 0:
            yield buffer
