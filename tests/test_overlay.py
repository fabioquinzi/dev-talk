"""Tests for recording overlay."""

from unittest.mock import MagicMock, patch

import pytest

from dev_talk.overlay import OverlayState, RecordingOverlay


class TestOverlayState:
    def test_states_exist(self):
        assert OverlayState.HIDDEN is not None
        assert OverlayState.LOADING is not None
        assert OverlayState.RECORDING is not None
        assert OverlayState.RECORDING_HANDS_FREE is not None
        assert OverlayState.TRANSCRIBING is not None


class TestRecordingOverlay:
    def test_initial_state(self):
        overlay = RecordingOverlay()
        assert overlay.state == OverlayState.HIDDEN
        assert overlay._initialized is False

    def test_show_loading_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()
        overlay._stop_button = MagicMock()

        with patch("dev_talk.overlay._get_appkit") as mock_appkit:
            mock_appkit.return_value = MagicMock()
            overlay.show_loading()

        assert overlay.state == OverlayState.LOADING

    def test_show_recording_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()
        overlay._stop_button = MagicMock()

        with patch("dev_talk.overlay._get_appkit") as mock_appkit:
            mock_appkit.return_value = MagicMock()
            overlay.show_recording()

        assert overlay.state == OverlayState.RECORDING

    def test_show_recording_hands_free_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()
        overlay._stop_button = MagicMock()

        with patch("dev_talk.overlay._get_appkit") as mock_appkit:
            mock_appkit.return_value = MagicMock()
            overlay.show_recording(hands_free=True)

        assert overlay.state == OverlayState.RECORDING_HANDS_FREE

    def test_show_transcribing_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()
        overlay._stop_button = MagicMock()

        with patch("dev_talk.overlay._get_appkit") as mock_appkit:
            mock_appkit.return_value = MagicMock()
            overlay.show_transcribing()

        assert overlay.state == OverlayState.TRANSCRIBING

    def test_hide_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()

        overlay.hide()
        assert overlay.state == OverlayState.HIDDEN
        overlay._window.orderOut_.assert_called_once()

    def test_cleanup(self):
        overlay = RecordingOverlay()
        overlay._window = MagicMock()
        overlay._initialized = True

        overlay.cleanup()
        assert overlay._window is None
        assert overlay._initialized is False

    def test_on_stop_callback(self):
        cb = MagicMock()
        overlay = RecordingOverlay(on_stop=cb)
        assert overlay.on_stop is cb

        # Simulate what the NSObject button target does on click
        overlay._on_stop()
        cb.assert_called_once()

    def test_on_stop_property_setter(self):
        overlay = RecordingOverlay()
        cb = MagicMock()
        overlay.on_stop = cb
        assert overlay.on_stop is cb

    def test_update_level_ignored_when_hidden(self):
        overlay = RecordingOverlay()
        overlay._initialized = True
        overlay._bars = [MagicMock() for _ in range(16)]
        # State is HIDDEN — update_level should be a no-op
        overlay.update_level(0.5)
        for bar in overlay._bars:
            bar.layer.assert_not_called()

    def test_update_level_ignored_when_not_initialized(self):
        overlay = RecordingOverlay()
        overlay._state = OverlayState.RECORDING
        overlay._initialized = False
        # Should not crash
        overlay.update_level(0.5)

    def test_graceful_when_no_gui(self):
        """Should not crash when GUI context is unavailable."""
        overlay = RecordingOverlay()
        # Force _ensure_initialized to raise (simulating no GUI)
        overlay._ensure_initialized = MagicMock(side_effect=Exception("No GUI"))

        # Should not raise
        overlay._update_state(OverlayState.RECORDING)
        assert overlay.state == OverlayState.RECORDING
