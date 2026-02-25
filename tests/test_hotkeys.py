"""Tests for hotkey manager."""

from unittest.mock import MagicMock, call

import pytest
from pynput import keyboard

from dev_talk.hotkeys import (
    HotkeyManager,
    RecordingMode,
    _FN_KEY_SENTINEL,
    _normalize_key,
    parse_key,
)


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

    def test_parse_fn_returns_sentinel(self):
        result = parse_key("fn")
        assert result == _FN_KEY_SENTINEL

    def test_parse_fn_case_insensitive(self):
        assert parse_key("FN") == _FN_KEY_SENTINEL
        assert parse_key("Fn") == _FN_KEY_SENTINEL


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

    def test_default_keys(self):
        """Default push-to-talk is fn, hands-free is fn+space."""
        hm = HotkeyManager()
        assert hm._ptt_key == _FN_KEY_SENTINEL
        assert _FN_KEY_SENTINEL in hm._hf_keys
        assert keyboard.Key.space in hm._hf_keys
        assert hm._uses_fn is True

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


class TestFnKeyPushToTalk:
    """Tests for fn key as push-to-talk via the _on_fn_press/_on_fn_release callbacks."""

    def test_fn_push_to_talk_start(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        hm._on_fn_press()
        start_cb.assert_called_once()
        assert hm._ptt_active is True

    def test_fn_push_to_talk_stop(self):
        start_cb = MagicMock()
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
            on_push_to_talk_stop=stop_cb,
        )

        hm._on_fn_press()
        hm._on_fn_release()
        stop_cb.assert_called_once()
        assert hm._ptt_active is False

    def test_fn_push_to_talk_no_double_trigger(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        hm._on_fn_press()
        # Pressing again without releasing should not re-trigger
        # (simulated by calling _check_hotkeys with fn sentinel again)
        hm._check_hotkeys(_FN_KEY_SENTINEL)
        assert start_cb.call_count == 1

    def test_fn_release_without_press_is_noop(self):
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_stop=stop_cb,
        )

        hm._on_fn_release()
        stop_cb.assert_not_called()


class TestFnHandsFreeCombo:
    """Tests for fn+space as hands-free toggle (default combo)."""

    def test_fn_plus_space_triggers_hands_free(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_hands_free_toggle=toggle_cb,
        )

        # fn pressed first
        hm._on_fn_press()
        toggle_cb.assert_not_called()

        # space pressed while fn held — combo complete
        hm._on_press(keyboard.Key.space)
        toggle_cb.assert_called_once()

    def test_space_then_fn_triggers_hands_free(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_hands_free_toggle=toggle_cb,
        )

        # space pressed first
        hm._on_press(keyboard.Key.space)
        toggle_cb.assert_not_called()

        # fn pressed while space held — combo complete
        hm._on_fn_press()
        toggle_cb.assert_called_once()

    def test_hands_free_takes_priority_over_ptt(self):
        """When fn+space combo is pressed, hands-free should fire, not PTT."""
        start_cb = MagicMock()
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_push_to_talk_start=start_cb,
            on_hands_free_toggle=toggle_cb,
        )

        # fn alone first triggers PTT
        hm._on_fn_press()
        assert start_cb.call_count == 1

        # Then space makes it a hands-free combo
        hm._on_press(keyboard.Key.space)
        toggle_cb.assert_called_once()


class TestUpdateKeysWithFn:
    def test_update_to_fn_key(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        assert hm._uses_fn is False

        hm.update_keys(push_to_talk_key="fn")
        assert hm._ptt_key == _FN_KEY_SENTINEL
        assert hm._uses_fn is True

    def test_update_away_from_fn(self):
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
        )
        assert hm._uses_fn is True

        hm.update_keys(push_to_talk_key="space", hands_free_keys=["ctrl", "shift"])
        assert hm._uses_fn is False

    def test_update_hands_free_to_include_fn(self):
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["ctrl", "shift"],
        )
        assert hm._uses_fn is False

        hm.update_keys(hands_free_keys=["fn", "space"])
        assert hm._uses_fn is True
        assert _FN_KEY_SENTINEL in hm._hf_keys
