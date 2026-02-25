"""Tests for hotkey manager."""

from unittest.mock import MagicMock, call

import pytest
from pynput import keyboard

from dev_talk.hotkeys import HotkeyManager, RecordingMode, _normalize_key, parse_key


class TestParseKey:
    def test_parse_special_keys(self):
        assert parse_key("ctrl") == keyboard.Key.ctrl
        assert parse_key("shift") == keyboard.Key.shift
        assert parse_key("space") == keyboard.Key.space
        assert parse_key("cmd") == keyboard.Key.cmd
        assert parse_key("esc") == keyboard.Key.esc

    def test_parse_single_char(self):
        result = parse_key("a")
        assert isinstance(result, keyboard.KeyCode)

    def test_parse_case_insensitive(self):
        assert parse_key("CTRL") == keyboard.Key.ctrl
        assert parse_key("Space") == keyboard.Key.space

    def test_parse_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown key"):
            parse_key("nonexistent_key")

    def test_parse_f_keys(self):
        assert parse_key("f1") == keyboard.Key.f1
        assert parse_key("f12") == keyboard.Key.f12


class TestNormalizeKey:
    def test_normalize_special_key(self):
        assert _normalize_key(keyboard.Key.ctrl) == keyboard.Key.ctrl

    def test_normalize_char_key(self):
        key = keyboard.KeyCode.from_char("A")
        normalized = _normalize_key(key)
        assert normalized == keyboard.KeyCode.from_char("a")

    def test_normalize_keycode_without_char(self):
        key = keyboard.KeyCode(vk=65)
        result = _normalize_key(key)
        assert result == key


class TestHotkeyManager:
    def test_initial_state(self):
        hm = HotkeyManager()
        assert hm.is_running is False

    def test_push_to_talk_callbacks(self):
        start_cb = MagicMock()
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
            on_push_to_talk_stop=stop_cb,
        )

        # Simulate key press
        hm._on_press(keyboard.Key.space)
        start_cb.assert_called_once()
        assert hm._ptt_active is True

        # Simulate key release
        hm._on_release(keyboard.Key.space)
        stop_cb.assert_called_once()
        assert hm._ptt_active is False

    def test_push_to_talk_no_double_trigger(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        hm._on_press(keyboard.Key.space)
        hm._on_press(keyboard.Key.space)  # Should not re-trigger

        assert start_cb.call_count == 1

    def test_hands_free_toggle(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            hands_free_keys=["ctrl", "shift"],
            on_hands_free_toggle=toggle_cb,
        )

        # Press first key — should not trigger yet
        hm._on_press(keyboard.Key.ctrl)
        toggle_cb.assert_not_called()

        # Press second key — combo complete, should trigger
        hm._on_press(keyboard.Key.shift)
        toggle_cb.assert_called_once()

    def test_hands_free_order_independent(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            hands_free_keys=["shift", "ctrl"],
            on_hands_free_toggle=toggle_cb,
        )

        # Press in reverse order
        hm._on_press(keyboard.Key.shift)
        hm._on_press(keyboard.Key.ctrl)
        toggle_cb.assert_called_once()

    def test_update_keys(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        # Original key should work
        hm._on_press(keyboard.Key.space)
        assert start_cb.call_count == 1
        hm._on_release(keyboard.Key.space)

        # Update to ctrl
        hm.update_keys(push_to_talk_key="ctrl")

        # Old key should NOT work
        hm._on_press(keyboard.Key.space)
        assert start_cb.call_count == 1  # No change

        # New key should work
        hm._on_press(keyboard.Key.ctrl)
        assert start_cb.call_count == 2

    def test_stop_clears_state(self):
        hm = HotkeyManager(push_to_talk_key="space", hands_free_keys=["alt", "shift"])
        hm._pressed_keys.add(keyboard.Key.space)
        hm._ptt_active = True

        hm.stop()

        assert hm._pressed_keys == set()
        assert hm._ptt_active is False
        assert hm.is_running is False

    def test_start_is_idempotent(self):
        hm = HotkeyManager()
        hm.start()
        listener1 = hm._listener
        hm.start()  # Should be no-op
        assert hm._listener is listener1
        hm.stop()
