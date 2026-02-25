"""Tests for recording overlay."""

from unittest.mock import MagicMock, patch

import pytest

from dev_talk.overlay import OverlayState, RecordingOverlay


class TestOverlayState:
    def test_states_exist(self):
        assert OverlayState.HIDDEN is not None
        assert OverlayState.RECORDING is not None
        assert OverlayState.TRANSCRIBING is not None


class TestRecordingOverlay:
    def test_initial_state(self):
        overlay = RecordingOverlay()
        assert overlay.state == OverlayState.HIDDEN
        assert overlay._initialized is False

    def test_show_recording_sets_state(self):
        overlay = RecordingOverlay()
        # Mock the AppKit initialization since we're not in a GUI context
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()

        with patch("dev_talk.overlay._get_appkit") as mock_appkit:
            mock_appkit.return_value = MagicMock()
            overlay.show_recording()

        assert overlay.state == OverlayState.RECORDING

    def test_show_transcribing_sets_state(self):
        overlay = RecordingOverlay()
        overlay._ensure_initialized = MagicMock()
        overlay._window = MagicMock()
        overlay._label = MagicMock()
        overlay._indicator = MagicMock()
        overlay._indicator.layer.return_value = MagicMock()

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

    def test_graceful_when_no_gui(self):
        """Should not crash when GUI context is unavailable."""
        overlay = RecordingOverlay()
        # Force _ensure_initialized to raise (simulating no GUI)
        overlay._ensure_initialized = MagicMock(side_effect=Exception("No GUI"))

        # Should not raise
        overlay._update_state(OverlayState.RECORDING)
        assert overlay.state == OverlayState.RECORDING
