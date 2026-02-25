"""Tests for transcriber abstraction."""

import numpy as np
import pytest

from dev_talk.transcriber import Transcriber, TranscriberEngine


class FakeEngine:
    """A fake STT engine for testing."""

    def __init__(self, responses: list[str] | None = None, available: bool = True):
        self._responses = responses or ["hello world"]
        self._call_count = 0
        self._available = available

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "FakeEngine"


class TestTranscriberEngineProtocol:
    def test_fake_engine_satisfies_protocol(self):
        engine = FakeEngine()
        assert isinstance(engine, TranscriberEngine)

    def test_object_does_not_satisfy_protocol(self):
        assert not isinstance(object(), TranscriberEngine)


class TestTranscriber:
    def test_engine_name(self):
        t = Transcriber(engine=FakeEngine())
        assert t.engine_name == "FakeEngine"

    def test_is_available(self):
        t = Transcriber(engine=FakeEngine(available=True))
        assert t.is_available() is True

        t2 = Transcriber(engine=FakeEngine(available=False))
        assert t2.is_available() is False

    def test_swap_engine(self):
        e1 = FakeEngine()
        e2 = FakeEngine(responses=["swapped"])
        t = Transcriber(engine=e1)
        assert t.engine_name == "FakeEngine"

        t.engine = e2
        result = t.transcribe_full(np.ones(16000, dtype=np.float32))
        assert result == "swapped"

    def test_transcribe_full_returns_text(self):
        t = Transcriber(engine=FakeEngine(responses=["  hello world  "]))
        audio = np.ones(16000, dtype=np.float32)
        result = t.transcribe_full(audio)
        assert result == "hello world"  # Stripped

    def test_transcribe_full_empty_audio(self):
        t = Transcriber(engine=FakeEngine())
        result = t.transcribe_full(np.array([], dtype=np.float32))
        assert result == ""

    def test_transcribe_streaming_yields_chunks(self):
        responses = ["first chunk", "second chunk", "third chunk"]
        t = Transcriber(engine=FakeEngine(responses=responses))

        chunks = [
            np.ones(16000, dtype=np.float32),
            np.ones(16000, dtype=np.float32),
            np.ones(16000, dtype=np.float32),
        ]

        results = list(t.transcribe_streaming(chunks))
        assert results == ["first chunk", "second chunk", "third chunk"]

    def test_transcribe_streaming_skips_empty_chunks(self):
        t = Transcriber(engine=FakeEngine(responses=["only chunk"]))

        chunks = [
            np.array([], dtype=np.float32),  # Empty — skipped
            np.ones(16000, dtype=np.float32),
            np.array([], dtype=np.float32),  # Empty — skipped
        ]

        results = list(t.transcribe_streaming(chunks))
        assert results == ["only chunk"]

    def test_transcribe_streaming_skips_whitespace_results(self):
        t = Transcriber(engine=FakeEngine(responses=["  ", "real text"]))

        chunks = [
            np.ones(16000, dtype=np.float32),
            np.ones(16000, dtype=np.float32),
        ]

        results = list(t.transcribe_streaming(chunks))
        assert results == ["real text"]

    def test_transcribe_streaming_generator_input(self):
        t = Transcriber(engine=FakeEngine(responses=["gen chunk 1", "gen chunk 2"]))

        def gen():
            yield np.ones(16000, dtype=np.float32)
            yield np.ones(16000, dtype=np.float32)

        results = list(t.transcribe_streaming(gen()))
        assert results == ["gen chunk 1", "gen chunk 2"]
