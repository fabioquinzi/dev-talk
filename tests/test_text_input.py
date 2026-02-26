"""Tests for text injection module.

These tests mock Quartz/AppKit to avoid requiring Accessibility permissions
and to run in CI environments.
"""

from unittest.mock import MagicMock, patch

import pytest

from dev_talk.text_input import inject_text, paste_text, type_text


@pytest.fixture
def mock_quartz():
    mock = MagicMock()
    mock.kCGEventSourceStateCombinedSessionState = 0
    mock.kCGEventFlagMaskCommand = 1 << 20
    mock.kCGAnnotatedSessionEventTap = 0
    with patch("dev_talk.text_input._get_quartz", return_value=mock):
        yield mock


@pytest.fixture
def mock_appkit():
    mock = MagicMock()
    pasteboard = MagicMock()
    pasteboard.stringForType_.return_value = "old clipboard"
    mock.NSPasteboard.generalPasteboard.return_value = pasteboard
    mock.NSStringPboardType = "public.utf8-plain-text"
    with patch("dev_talk.text_input._get_appkit", return_value=mock):
        yield mock, pasteboard


class TestPasteText:
    def test_paste_empty_string(self, mock_quartz, mock_appkit):
        paste_text("")
        # Should not interact with Quartz at all
        mock_quartz.CGEventSourceCreate.assert_not_called()

    @patch("dev_talk.text_input.time")
    def test_paste_sets_clipboard_and_simulates_cmd_v(self, mock_time, mock_quartz, mock_appkit):
        _, pasteboard = mock_appkit
        paste_text("hello world")

        # Should have set text on pasteboard
        pasteboard.clearContents.assert_called()
        pasteboard.setString_forType_.assert_called()

        # Should have created key events
        assert mock_quartz.CGEventCreateKeyboardEvent.call_count >= 2  # down + up
        assert mock_quartz.CGEventPost.call_count >= 2

    @patch("dev_talk.text_input.time")
    def test_paste_restores_old_clipboard(self, mock_time, mock_quartz, mock_appkit):
        _, pasteboard = mock_appkit
        pasteboard.stringForType_.return_value = "original content"

        paste_text("new text")

        # Last setString call should restore original content
        calls = pasteboard.setString_forType_.call_args_list
        assert len(calls) >= 2
        last_call = calls[-1]
        assert last_call[0][0] == "original content"


class TestTypeText:
    def test_type_empty_string(self, mock_quartz):
        type_text("")
        mock_quartz.CGEventSourceCreate.assert_not_called()

    @patch("dev_talk.text_input.time")
    def test_type_creates_events_per_character(self, mock_time, mock_quartz):
        type_text("abc", delay=0)

        # 3 chars × 2 events (down + up) = 6 key events
        assert mock_quartz.CGEventCreateKeyboardEvent.call_count == 6
        # 3 chars × 2 posts = 6 posts
        assert mock_quartz.CGEventPost.call_count == 6

    @patch("dev_talk.text_input.time")
    def test_type_sets_unicode_string(self, mock_time, mock_quartz):
        type_text("A", delay=0)

        # Should call CGEventKeyboardSetUnicodeString with the character
        calls = mock_quartz.CGEventKeyboardSetUnicodeString.call_args_list
        assert len(calls) == 2  # down + up
        assert calls[0][0][2] == "A"


class TestInjectText:
    @patch("dev_talk.text_input.paste_text")
    def test_inject_paste_method(self, mock_paste):
        inject_text("hello", method="paste")
        mock_paste.assert_called_once_with("hello")

    @patch("dev_talk.text_input.type_text")
    def test_inject_type_method(self, mock_type):
        inject_text("hello", method="type")
        mock_type.assert_called_once_with("hello")

    def test_inject_empty_string(self):
        # Should not raise
        inject_text("", method="paste")
        inject_text("", method="type")

    def test_inject_invalid_method(self):
        with pytest.raises(ValueError, match="Unknown injection method"):
            inject_text("hello", method="invalid")
