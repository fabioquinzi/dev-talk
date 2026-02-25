"""Global hotkey manager for push-to-talk and hands-free modes.

Uses pynput for cross-application keyboard monitoring.
Requires macOS Input Monitoring permission.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)


class RecordingMode(Enum):
    PUSH_TO_TALK = auto()
    HANDS_FREE = auto()


# Map common key names to pynput Key objects.
# Built dynamically to avoid AttributeError on platforms where some keys don't exist.
_SPECIAL_KEYS: dict[str, keyboard.Key] = {}
for _name in [
    "alt", "alt_l", "alt_r", "backspace", "caps_lock", "cmd", "cmd_l", "cmd_r",
    "ctrl", "ctrl_l", "ctrl_r", "delete", "down", "end", "enter", "esc",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "fn",
    "home", "left", "page_down", "page_up", "right", "shift", "shift_l", "shift_r",
    "space", "tab", "up",
]:
    if hasattr(keyboard.Key, _name):
        _SPECIAL_KEYS[_name] = getattr(keyboard.Key, _name)


def parse_key(key_str: str) -> keyboard.Key | keyboard.KeyCode:
    """Parse a key string into a pynput key object."""
    key_str = key_str.lower().strip()
    if key_str in _SPECIAL_KEYS and _SPECIAL_KEYS[key_str] is not None:
        return _SPECIAL_KEYS[key_str]
    if len(key_str) == 1:
        return keyboard.KeyCode.from_char(key_str)
    raise ValueError(f"Unknown key: {key_str!r}")


def _normalize_key(key: keyboard.Key | keyboard.KeyCode) -> keyboard.Key | keyboard.KeyCode:
    """Normalize a key for consistent comparison."""
    if isinstance(key, keyboard.KeyCode) and key.char is not None:
        return keyboard.KeyCode.from_char(key.char.lower())
    return key


class HotkeyManager:
    """Manages global keyboard shortcuts for recording control.

    Two modes:
    - Push-to-talk: Hold a key to record, release to stop.
    - Hands-free: Press a key combo to toggle recording on/off.
    """

    def __init__(
        self,
        push_to_talk_key: str = "f5",
        hands_free_keys: list[str] | None = None,
        on_push_to_talk_start: Callable[[], None] | None = None,
        on_push_to_talk_stop: Callable[[], None] | None = None,
        on_hands_free_toggle: Callable[[], None] | None = None,
    ) -> None:
        self._ptt_key = parse_key(push_to_talk_key)
        self._hf_keys = {parse_key(k) for k in (hands_free_keys or ["ctrl", "shift"])}

        self._on_ptt_start = on_push_to_talk_start or (lambda: None)
        self._on_ptt_stop = on_push_to_talk_stop or (lambda: None)
        self._on_hf_toggle = on_hands_free_toggle or (lambda: None)

        self._pressed_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        self._ptt_active = False
        self._listener: keyboard.Listener | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for global hotkeys."""
        if self._running:
            return

        self._running = True
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey manager started")

    def stop(self) -> None:
        """Stop listening for global hotkeys."""
        self._running = False
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._pressed_keys.clear()
        self._ptt_active = False
        logger.info("Hotkey manager stopped")

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        normalized = _normalize_key(key)
        self._pressed_keys.add(normalized)

        # Check hands-free combo (all keys in the combo must be pressed)
        if self._hf_keys and self._hf_keys.issubset(self._pressed_keys):
            logger.debug("Hands-free toggle triggered")
            self._on_hf_toggle()
            return

        # Check push-to-talk (single key)
        if normalized == self._ptt_key and not self._ptt_active:
            self._ptt_active = True
            logger.debug("Push-to-talk started")
            self._on_ptt_start()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        normalized = _normalize_key(key)
        self._pressed_keys.discard(normalized)

        # Check push-to-talk release
        if normalized == self._ptt_key and self._ptt_active:
            self._ptt_active = False
            logger.debug("Push-to-talk stopped")
            self._on_ptt_stop()

    def update_keys(
        self,
        push_to_talk_key: str | None = None,
        hands_free_keys: list[str] | None = None,
    ) -> None:
        """Update hotkey bindings. Safe to call while running."""
        if push_to_talk_key is not None:
            self._ptt_key = parse_key(push_to_talk_key)
        if hands_free_keys is not None:
            self._hf_keys = {parse_key(k) for k in hands_free_keys}
