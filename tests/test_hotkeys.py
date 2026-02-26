"""Tests for hotkey manager.

Tests call the internal methods (_on_flags_changed, _on_key_down, _on_key_up)
directly to verify hotkey logic without needing AppKit/NSEvent.
"""

from unittest.mock import MagicMock

import pytest

from dev_talk.hotkeys import (
    HotkeyManager,
    RecordingMode,
    _CharKey,
    _KeyCode,
    _Modifier,
    _KEYCODE_MAP,
    _MODIFIER_MAP,
    parse_key,
)

# Common key constants for tests
FN_FLAG = 0x800000
CTRL_FLAG = 0x40000
SHIFT_FLAG = 0x20000
ALT_FLAG = 0x80000
CMD_FLAG = 0x100000
SPACE_CODE = 49


class TestParseKey:
    def test_parse_fn(self):
        result = parse_key("fn")
        assert result == _Modifier(FN_FLAG)

    def test_parse_fn_case_insensitive(self):
        assert parse_key("FN") == _Modifier(FN_FLAG)
        assert parse_key("Fn") == _Modifier(FN_FLAG)

    def test_parse_modifiers(self):
        assert parse_key("ctrl") == _Modifier(CTRL_FLAG)
        assert parse_key("shift") == _Modifier(SHIFT_FLAG)
        assert parse_key("alt") == _Modifier(ALT_FLAG)
        assert parse_key("cmd") == _Modifier(CMD_FLAG)

    def test_parse_special_keys(self):
        assert parse_key("space") == _KeyCode(SPACE_CODE)
        assert parse_key("esc") == _KeyCode(53)
        assert parse_key("tab") == _KeyCode(48)
        assert parse_key("enter") == _KeyCode(36)

    def test_parse_f_keys(self):
        assert parse_key("f1") == _KeyCode(122)
        assert parse_key("f5") == _KeyCode(96)
        assert parse_key("f12") == _KeyCode(111)

    def test_parse_single_char(self):
        result = parse_key("a")
        assert result == _CharKey("a")

    def test_parse_case_insensitive_special(self):
        assert parse_key("CTRL") == _Modifier(CTRL_FLAG)
        assert parse_key("Space") == _KeyCode(SPACE_CODE)

    def test_parse_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown key"):
            parse_key("nonexistent_key")


class TestHotkeyManager:
    def test_initial_state(self):
        hm = HotkeyManager()
        assert hm.is_running is False

    def test_default_keys(self):
        """Default push-to-talk is fn, hands-free is fn+space."""
        hm = HotkeyManager()
        assert hm._ptt_key == _Modifier(FN_FLAG)
        assert _Modifier(FN_FLAG) in hm._hf_keys
        assert _KeyCode(SPACE_CODE) in hm._hf_keys

    def test_push_to_talk_with_regular_key(self):
        start_cb = MagicMock()
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
            on_push_to_talk_stop=stop_cb,
        )

        # Simulate space key press (keyCode=49)
        hm._on_key_down(SPACE_CODE, " ")
        start_cb.assert_called_once()
        assert hm._ptt_active is True

        # Simulate space key release
        hm._on_key_up(SPACE_CODE, " ")
        stop_cb.assert_called_once()
        assert hm._ptt_active is False

    def test_push_to_talk_no_double_trigger(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        hm._on_key_down(SPACE_CODE, " ")
        hm._on_key_down(SPACE_CODE, " ")  # Should not re-trigger

        assert start_cb.call_count == 1

    def test_hands_free_toggle_with_modifiers(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="f5",
            hands_free_keys=["ctrl", "shift"],
            on_hands_free_toggle=toggle_cb,
        )

        # Press ctrl — should not trigger yet
        hm._on_flags_changed(CTRL_FLAG)
        toggle_cb.assert_not_called()

        # Press shift while ctrl held — combo complete
        hm._on_flags_changed(CTRL_FLAG | SHIFT_FLAG)
        toggle_cb.assert_called_once()

    def test_hands_free_order_independent(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="f5",
            hands_free_keys=["shift", "ctrl"],
            on_hands_free_toggle=toggle_cb,
        )

        # Press shift first, then ctrl
        hm._on_flags_changed(SHIFT_FLAG)
        hm._on_flags_changed(SHIFT_FLAG | CTRL_FLAG)
        toggle_cb.assert_called_once()

    def test_update_keys(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        # Original key should work
        hm._on_key_down(SPACE_CODE, " ")
        assert start_cb.call_count == 1
        hm._on_key_up(SPACE_CODE, " ")

        # Update to f5 (keyCode=96)
        hm.update_keys(push_to_talk_key="f5")

        # Old key should NOT work
        hm._on_key_down(SPACE_CODE, " ")
        assert start_cb.call_count == 1  # No change

        # New key should work
        hm._on_key_down(96, "")
        assert start_cb.call_count == 2

    def test_stop_clears_state(self):
        hm = HotkeyManager(push_to_talk_key="space", hands_free_keys=["alt", "shift"])
        hm._pressed_keys.add(_KeyCode(SPACE_CODE))
        hm._ptt_active = True

        hm.stop()

        assert hm._pressed_keys == set()
        assert hm._ptt_active is False
        assert hm.is_running is False

    def test_start_is_idempotent(self):
        hm = HotkeyManager()
        hm.start()
        monitors1 = list(hm._monitors)
        hm.start()  # Should be no-op
        assert hm._monitors == monitors1
        hm.stop()


class TestFnKeyPushToTalk:
    """Tests for fn key as push-to-talk via modifier flags."""

    def test_fn_push_to_talk_start(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        # fn pressed (modifier flag set)
        hm._on_flags_changed(FN_FLAG)
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

        # fn pressed then released
        hm._on_flags_changed(FN_FLAG)
        hm._on_flags_changed(0)
        stop_cb.assert_called_once()
        assert hm._ptt_active is False

    def test_fn_push_to_talk_no_double_trigger(self):
        start_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_start=start_cb,
        )

        hm._on_flags_changed(FN_FLAG)
        # Same flags again — fn still held, should not re-trigger
        hm._on_flags_changed(FN_FLAG)
        assert start_cb.call_count == 1

    def test_fn_release_without_press_is_noop(self):
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
            on_push_to_talk_stop=stop_cb,
        )

        # fn not pressed, flags go to 0 — should not trigger stop
        hm._on_flags_changed(0)
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

        # fn pressed first (modifier)
        hm._on_flags_changed(FN_FLAG)
        toggle_cb.assert_not_called()

        # space pressed while fn held (keyDown)
        hm._on_key_down(SPACE_CODE, " ")
        toggle_cb.assert_called_once()

    def test_space_then_fn_triggers_hands_free(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_hands_free_toggle=toggle_cb,
        )

        # space pressed first
        hm._on_key_down(SPACE_CODE, " ")
        toggle_cb.assert_not_called()

        # fn pressed while space held
        hm._on_flags_changed(FN_FLAG)
        toggle_cb.assert_called_once()

    def test_hands_free_takes_priority_over_ptt(self):
        """When fn+space combo is pressed, hands-free should fire, not just PTT."""
        start_cb = MagicMock()
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_push_to_talk_start=start_cb,
            on_hands_free_toggle=toggle_cb,
        )

        # fn alone first triggers PTT
        hm._on_flags_changed(FN_FLAG)
        assert start_cb.call_count == 1

        # Then space makes it a hands-free combo
        hm._on_key_down(SPACE_CODE, " ")
        toggle_cb.assert_called_once()

    def test_ptt_cancelled_silently_when_hf_triggers(self):
        """PTT should be cancelled without firing stop when HF combo activates."""
        start_cb = MagicMock()
        stop_cb = MagicMock()
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["fn", "space"],
            on_push_to_talk_start=start_cb,
            on_push_to_talk_stop=stop_cb,
            on_hands_free_toggle=toggle_cb,
        )

        # fn pressed — triggers PTT start
        hm._on_flags_changed(FN_FLAG)
        assert hm._ptt_active is True
        start_cb.assert_called_once()

        # space pressed while fn held — triggers hands-free
        hm._on_key_down(SPACE_CODE, " ")
        toggle_cb.assert_called_once()
        # PTT should be silently cancelled (no stop callback)
        assert hm._ptt_active is False
        stop_cb.assert_not_called()

        # fn released — should NOT fire PTT stop (already cancelled)
        hm._on_flags_changed(0)
        stop_cb.assert_not_called()


class TestUpdateKeysWithModifiers:
    def test_update_to_fn_key(self):
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["alt", "shift"],
        )
        assert hm._ptt_key == _KeyCode(SPACE_CODE)

        hm.update_keys(push_to_talk_key="fn")
        assert hm._ptt_key == _Modifier(FN_FLAG)

    def test_update_away_from_fn(self):
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["alt", "shift"],
        )
        assert hm._ptt_key == _Modifier(FN_FLAG)

        hm.update_keys(push_to_talk_key="space")
        assert hm._ptt_key == _KeyCode(SPACE_CODE)

    def test_update_hands_free_to_include_fn(self):
        hm = HotkeyManager(
            push_to_talk_key="space",
            hands_free_keys=["ctrl", "shift"],
        )
        assert _Modifier(FN_FLAG) not in hm._hf_keys

        hm.update_keys(hands_free_keys=["fn", "space"])
        assert _Modifier(FN_FLAG) in hm._hf_keys
        assert _KeyCode(SPACE_CODE) in hm._hf_keys


class TestCharKeyMatching:
    """Tests for character-based key matching (a-z, 0-9)."""

    def test_char_key_push_to_talk(self):
        start_cb = MagicMock()
        stop_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="v",
            hands_free_keys=["ctrl", "shift"],
            on_push_to_talk_start=start_cb,
            on_push_to_talk_stop=stop_cb,
        )

        # keyCode 9 = 'v' on QWERTY, but chars="v" is what matters
        hm._on_key_down(9, "v")
        start_cb.assert_called_once()

        hm._on_key_up(9, "v")
        stop_cb.assert_called_once()

    def test_combo_with_modifier_and_keycode(self):
        toggle_cb = MagicMock()
        hm = HotkeyManager(
            push_to_talk_key="fn",
            hands_free_keys=["ctrl", "space"],
            on_hands_free_toggle=toggle_cb,
        )

        # ctrl pressed
        hm._on_flags_changed(CTRL_FLAG)
        toggle_cb.assert_not_called()

        # space pressed while ctrl held
        hm._on_key_down(SPACE_CODE, " ")
        toggle_cb.assert_called_once()
