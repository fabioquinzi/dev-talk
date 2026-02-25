"""Tests for audio module."""

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dev_talk.audio import SAMPLE_RATE, AudioDevice, AudioManager


class TestAudioDevice:
    def test_audio_device_fields(self):
        dev = AudioDevice(device_id=1, name="Test Mic", channels=1, sample_rate=16000.0)
        assert dev.device_id == 1
        assert dev.name == "Test Mic"
        assert dev.channels == 1
        assert dev.is_default is False

    def test_audio_device_default_flag(self):
        dev = AudioDevice(
            device_id=0, name="Default Mic", channels=2, sample_rate=48000.0, is_default=True
        )
        assert dev.is_default is True


class TestListDevices:
    @patch("dev_talk.audio.sd")
    def test_list_devices_filters_input_only(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Mic", "max_input_channels": 1, "max_output_channels": 0, "default_samplerate": 16000.0},
            {"name": "Speaker", "max_input_channels": 0, "max_output_channels": 2, "default_samplerate": 48000.0},
            {"name": "Headset", "max_input_channels": 2, "max_output_channels": 2, "default_samplerate": 44100.0},
        ]
        mock_sd.default.device = (0, 1)

        devices = AudioManager.list_devices()
        assert len(devices) == 2
        assert devices[0].name == "Mic"
        assert devices[0].is_default is True
        assert devices[1].name == "Headset"
        assert devices[1].is_default is False


class TestAudioManager:
    def test_initial_state(self):
        am = AudioManager()
        assert am.is_recording is False
        assert am.device_id is None

    def test_set_device_id(self):
        am = AudioManager()
        am.device_id = 3
        assert am.device_id == 3

    def test_cannot_change_device_while_recording(self):
        am = AudioManager()
        am._recording = True
        with pytest.raises(RuntimeError, match="Cannot change device while recording"):
            am.device_id = 5

    def test_stop_recording_when_not_recording(self):
        am = AudioManager()
        audio = am.stop_recording()
        assert audio.size == 0
        assert audio.dtype == np.float32

    def test_get_chunk_empty(self):
        am = AudioManager()
        chunk = am.get_chunk()
        assert chunk.size == 0

    def test_get_chunk_with_data(self):
        am = AudioManager()
        fake_frame = np.ones((1024, 1), dtype=np.float32)
        am._frames = [fake_frame, fake_frame]

        chunk = am.get_chunk(clear=True)
        assert chunk.shape == (2048,)
        assert am._frames == []  # Buffer cleared

    def test_get_chunk_no_clear(self):
        am = AudioManager()
        fake_frame = np.ones((1024, 1), dtype=np.float32)
        am._frames = [fake_frame]

        chunk = am.get_chunk(clear=False)
        assert chunk.shape == (1024,)
        assert len(am._frames) == 1  # Buffer preserved

    @patch("dev_talk.audio.sd.InputStream")
    def test_start_and_stop_recording(self, mock_stream_cls):
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        am = AudioManager(device_id=2)
        am.start_recording()

        assert am.is_recording is True
        mock_stream.start.assert_called_once()

        # Simulate some recorded frames
        am._frames = [np.ones((1024, 1), dtype=np.float32)]

        audio = am.stop_recording()
        assert am.is_recording is False
        assert audio.shape == (1024,)
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    @patch("dev_talk.audio.sd.InputStream")
    def test_start_recording_idempotent(self, mock_stream_cls):
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        am = AudioManager()
        am.start_recording()
        am.start_recording()  # Should be a no-op

        assert mock_stream_cls.call_count == 1

    def test_stream_chunks_yields_correct_sizes(self):
        am = AudioManager()
        am._recording = True

        # Pre-fill buffer with 2 seconds of audio
        samples_2s = SAMPLE_RATE * 2
        am._frames = [np.ones((samples_2s, 1), dtype=np.float32)]

        # Stop recording after a short delay so the generator terminates
        def stop_later():
            time.sleep(0.3)
            am._recording = False

        t = threading.Thread(target=stop_later)
        t.start()

        chunks = list(am.stream_chunks(chunk_duration_s=1.0))
        t.join()

        # Should have at least 2 full 1-second chunks
        assert len(chunks) >= 2
        assert chunks[0].shape == (SAMPLE_RATE,)
