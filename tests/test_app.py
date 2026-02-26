"""Tests for the main app module.

Tests orchestration logic by binding DevTalkApp methods to a plain object
with mocked subsystems, avoiding the rumps.App init.
"""

from unittest.mock import MagicMock, patch
from types import MethodType

import numpy as np

from dev_talk.app import ICON_IDLE, ICON_RECORDING
import pytest

from dev_talk.config import Config

# Patch callAfter to run synchronously in tests (no main thread run loop)
_original_call_after = None


def _sync_call_after(func):
    """In tests, just call the function immediately."""
    func()


@pytest.fixture(autouse=True)
def _patch_call_after():
    with patch("dev_talk.app.callAfter", side_effect=_sync_call_after):
        yield


def _make_app():
    """Create a fake app with DevTalkApp methods bound to it."""
    from dev_talk.app import DevTalkApp

    app = type("FakeApp", (), {})()
    app._config = Config()
    app._audio = MagicMock()
    app._audio.is_recording = False
    app._overlay = MagicMock()
    app._hands_free_active = False
    app._recording_thread = None
    app._level_monitor_active = False
    app._engine = MagicMock()
    app._transcriber = MagicMock()
    app._hotkeys = MagicMock()
    app.icon = ICON_IDLE
    app.template = True
    app.menu = MagicMock()

    # Bind all DevTalkApp methods to our fake app
    for name in dir(DevTalkApp):
        if name.startswith("__"):
            continue
        attr = getattr(DevTalkApp, name, None)
        if callable(attr) and not isinstance(attr, (staticmethod, classmethod)):
            try:
                setattr(app, name, MethodType(attr, app))
            except (TypeError, AttributeError):
                pass

    return app


class TestStartRecording:
    def test_start_recording_activates_audio(self):
        app = _make_app()
        app._config.streaming_mode = False

        with patch("dev_talk.app.threading.Thread"):
            app._start_recording()

        app._audio.start_recording.assert_called_once()
        assert app.icon == ICON_RECORDING
        app._overlay.show_recording.assert_called_once_with(hands_free=False)

    def test_start_recording_hands_free_flag(self):
        app = _make_app()
        app._config.streaming_mode = False
        app._hands_free_active = True

        with patch("dev_talk.app.threading.Thread"):
            app._start_recording()

        app._overlay.show_recording.assert_called_once_with(hands_free=True)

    def test_start_recording_streaming_starts_thread(self):
        app = _make_app()
        app._config.streaming_mode = True

        with patch("dev_talk.app.threading.Thread") as MockThread:
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread
            app._start_recording()

        app._audio.start_recording.assert_called_once()
        # Two threads: level monitor + streaming transcribe
        assert MockThread.call_count == 2


class TestStopRecording:
    def test_stop_non_streaming_transcribes(self):
        app = _make_app()
        app._config.streaming_mode = False
        app._audio.stop_recording.return_value = np.ones(16000, dtype=np.float32)

        with patch("dev_talk.app.threading.Thread") as MockThread:
            mock_thread = MagicMock()
            MockThread.return_value = mock_thread
            app._stop_recording_and_transcribe()

        app._audio.stop_recording.assert_called_once()
        app._overlay.show_transcribing.assert_called_once()

    def test_stop_streaming_hides_overlay(self):
        app = _make_app()
        app._config.streaming_mode = True
        app._audio.stop_recording.return_value = np.array([], dtype=np.float32)

        app._stop_recording_and_transcribe()

        app._audio.stop_recording.assert_called_once()
        assert app.icon == ICON_IDLE
        app._overlay.hide.assert_called_once()


class TestPushToTalk:
    def test_ptt_start_calls_start_recording(self):
        app = _make_app()
        app._audio.is_recording = False
        app._config.streaming_mode = False

        with patch("dev_talk.app.threading.Thread"):
            app._on_ptt_start()
        app._audio.start_recording.assert_called_once()

    def test_ptt_start_skipped_when_recording(self):
        app = _make_app()
        app._audio.is_recording = True

        app._on_ptt_start()
        app._audio.start_recording.assert_not_called()

    def test_ptt_start_skipped_when_hands_free_active(self):
        app = _make_app()
        app._audio.is_recording = False
        app._hands_free_active = True

        app._on_ptt_start()
        app._audio.start_recording.assert_not_called()

    def test_ptt_stop_calls_stop(self):
        app = _make_app()
        app._audio.is_recording = True
        app._config.streaming_mode = True
        app._audio.stop_recording.return_value = np.array([], dtype=np.float32)

        app._on_ptt_stop()
        app._audio.stop_recording.assert_called_once()

    def test_ptt_stop_skipped_when_not_recording(self):
        app = _make_app()
        app._audio.is_recording = False

        app._on_ptt_stop()
        app._audio.stop_recording.assert_not_called()

    def test_ptt_stop_skipped_when_hands_free_active(self):
        app = _make_app()
        app._audio.is_recording = True
        app._hands_free_active = True

        app._on_ptt_stop()
        app._audio.stop_recording.assert_not_called()


class TestHandsFree:
    def test_toggle_on_starts_recording(self):
        app = _make_app()
        app._hands_free_active = False
        app._config.streaming_mode = False

        with patch("dev_talk.app.threading.Thread"):
            app._on_hands_free_toggle()

        assert app._hands_free_active is True
        app._audio.start_recording.assert_called_once()
        app._overlay.show_recording.assert_called_once_with(hands_free=True)

    def test_toggle_on_takes_over_existing_recording(self):
        app = _make_app()
        app._hands_free_active = False
        app._audio.is_recording = True

        app._on_hands_free_toggle()

        assert app._hands_free_active is True
        # Should NOT call start_recording again — just switch overlay mode
        app._audio.start_recording.assert_not_called()
        app._overlay.show_recording.assert_called_once_with(hands_free=True)

    def test_toggle_off_stops_recording(self):
        app = _make_app()
        app._hands_free_active = True
        app._config.streaming_mode = True
        app._audio.stop_recording.return_value = np.array([], dtype=np.float32)

        app._on_hands_free_toggle()

        assert app._hands_free_active is False
        app._audio.stop_recording.assert_called_once()


class TestStopButton:
    def test_stop_button_stops_hands_free(self):
        app = _make_app()
        app._hands_free_active = True
        app._config.streaming_mode = True
        app._audio.stop_recording.return_value = np.array([], dtype=np.float32)

        app._on_stop_button()

        assert app._hands_free_active is False
        app._audio.stop_recording.assert_called_once()

    def test_stop_button_ignored_when_not_hands_free(self):
        app = _make_app()
        app._hands_free_active = False

        app._on_stop_button()

        app._audio.stop_recording.assert_not_called()


class TestTranscription:
    @patch("dev_talk.app.inject_text")
    def test_transcribe_full_injects_text(self, mock_inject):
        app = _make_app()
        app._transcriber.transcribe_full.return_value = "hello world"

        app._transcribe_full(np.ones(16000, dtype=np.float32))

        mock_inject.assert_called_once_with("hello world", method="paste")

    @patch("dev_talk.app.inject_text")
    def test_transcribe_full_skips_empty(self, mock_inject):
        app = _make_app()
        app._transcriber.transcribe_full.return_value = ""

        app._transcribe_full(np.ones(16000, dtype=np.float32))

        mock_inject.assert_not_called()

    @patch("dev_talk.app.inject_text")
    @patch("dev_talk.app.rumps.notification")
    def test_transcribe_full_handles_error(self, mock_notif, mock_inject):
        app = _make_app()
        app._transcriber.transcribe_full.side_effect = RuntimeError("fail")

        app._transcribe_full(np.ones(16000, dtype=np.float32))

        mock_inject.assert_not_called()

    @patch("dev_talk.app.inject_text")
    def test_stream_transcribe(self, mock_inject):
        app = _make_app()
        app._audio.stream_chunks.return_value = iter([
            np.ones(16000, dtype=np.float32),
        ])
        app._transcriber.transcribe_streaming.return_value = iter(["hello", "world"])

        app._stream_transcribe()

        assert mock_inject.call_count == 2
        mock_inject.assert_any_call("hello ", method="paste")
        mock_inject.assert_any_call("world ", method="paste")


class TestMicSelection:
    def test_select_mic(self):
        app = _make_app()

        app._select_mic(device_id=3, device_name="Test Mic")

        assert app._config.mic_device_id == 3
        assert app._audio.device_id == 3


class TestStreamingToggle:
    def test_toggle_streaming_mode(self):
        app = _make_app()
        app._config.streaming_mode = True

        app._toggle_streaming_mode(MagicMock())

        assert app._config.streaming_mode is False


class TestWarmupEngine:
    def test_warmup_calls_engine(self):
        app = _make_app()
        app._engine.warmup = MagicMock()

        app._warmup_engine()

        app._engine.warmup.assert_called_once()
        app._overlay.show_loading.assert_called_once()
        app._overlay.hide.assert_called_once()

    def test_warmup_skipped_without_method(self):
        app = _make_app()
        # Default MagicMock engine has no real warmup — remove it
        del app._engine.warmup

        app._warmup_engine()

        app._overlay.show_loading.assert_not_called()

    @patch("dev_talk.app.rumps.notification")
    def test_warmup_handles_error(self, mock_notif):
        app = _make_app()
        app._engine.warmup = MagicMock(side_effect=RuntimeError("download failed"))

        app._warmup_engine()

        mock_notif.assert_called_once()
        app._overlay.hide.assert_called_once()


class TestQuit:
    @patch("dev_talk.app.rumps.quit_application")
    def test_quit_cleans_up(self, mock_quit):
        app = _make_app()
        app._audio.is_recording = False

        app._quit(MagicMock())

        app._hotkeys.stop.assert_called_once()
        app._overlay.cleanup.assert_called_once()
        mock_quit.assert_called_once()
