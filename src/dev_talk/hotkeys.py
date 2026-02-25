"""Global hotkey manager for push-to-talk and hands-free modes.

Uses pynput for regular keys and a Quartz CGEvent tap for the fn (globe)
key, which pynput cannot detect on macOS.
Requires macOS Input Monitoring permission.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Sentinel object representing the fn key (not available in pynput)
_FN_KEY_SENTINEL = "<<fn>>"


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
    "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20",
    "home", "left", "page_down", "page_up", "right", "shift", "shift_l", "shift_r",
    "space", "tab", "up",
]:
    if hasattr(keyboard.Key, _name):
        _SPECIAL_KEYS[_name] = getattr(keyboard.Key, _name)


def parse_key(key_str: str) -> keyboard.Key | keyboard.KeyCode | str:
    """Parse a key string into a pynput key object, or the fn sentinel."""
    key_str = key_str.lower().strip()
    if key_str == "fn":
        return _FN_KEY_SENTINEL
    if key_str in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key_str]
    if len(key_str) == 1:
        return keyboard.KeyCode.from_char(key_str)
    raise ValueError(f"Unknown key: {key_str!r}")


def _normalize_key(key: keyboard.Key | keyboard.KeyCode) -> keyboard.Key | keyboard.KeyCode:
    """Normalize a key for consistent comparison."""
    if isinstance(key, keyboard.KeyCode) and key.char is not None:
        return keyboard.KeyCode.from_char(key.char.lower())
    return key


class _FnKeyMonitor:
    """Monitors the fn (globe) key via Quartz CGEvent tap.

    The fn key is a modifier that fires kCGEventFlagsChanged (type 12).
    We detect it by checking the kCGEventFlagMaskSecondaryFn bit (0x800000).
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._fn_down = False
        self._thread: threading.Thread | None = None
        self._running = False
        self._run_loop = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._run_loop is not None:
            import Quartz
            Quartz.CFRunLoopStop(self._run_loop)
        self._thread = None
        self._fn_down = False

    def _run(self) -> None:
        import Quartz

        def callback(proxy, event_type, event, refcon):
            flags = Quartz.CGEventGetFlags(event)
            fn_pressed = bool(flags & Quartz.kCGEventFlagMaskSecondaryFn)

            if fn_pressed and not self._fn_down:
                self._fn_down = True
                self._on_press()
            elif not fn_pressed and self._fn_down:
                self._fn_down = False
                self._on_release()

            return event

        mask = 1 << Quartz.kCGEventFlagsChanged
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            callback,
            None,
        )

        if tap is None:
            logger.warning(
                "Could not create CGEvent tap for fn key. "
                "Grant Input Monitoring permission in System Settings."
            )
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        self._run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._run_loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        logger.info("Fn key monitor started via CGEvent tap")
        Quartz.CFRunLoopRun()


class HotkeyManager:
    """Manages global keyboard shortcuts for recording control.

    Two modes:
    - Push-to-talk: Hold a key to record, release to stop. Default: fn
    - Hands-free: Press a key combo to toggle recording on/off. Default: fn+space
    """

    def __init__(
        self,
        push_to_talk_key: str = "fn",
        hands_free_keys: list[str] | None = None,
        on_push_to_talk_start: Callable[[], None] | None = None,
        on_push_to_talk_stop: Callable[[], None] | None = None,
        on_hands_free_toggle: Callable[[], None] | None = None,
    ) -> None:
        self._ptt_key = parse_key(push_to_talk_key)
        self._hf_keys = {parse_key(k) for k in (hands_free_keys or ["fn", "space"])}
        self._uses_fn = self._ptt_key == _FN_KEY_SENTINEL or _FN_KEY_SENTINEL in self._hf_keys

        self._on_ptt_start = on_push_to_talk_start or (lambda: None)
        self._on_ptt_stop = on_push_to_talk_stop or (lambda: None)
        self._on_hf_toggle = on_hands_free_toggle or (lambda: None)

        self._pressed_keys: set = set()
        self._ptt_active = False
        self._listener: keyboard.Listener | None = None
        self._fn_monitor: _FnKeyMonitor | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for global hotkeys."""
        if self._running:
            return

        self._running = True

        # Start pynput listener for regular keys
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

        # Start fn key monitor if needed
        if self._uses_fn:
            self._fn_monitor = _FnKeyMonitor(
                on_press=self._on_fn_press,
                on_release=self._on_fn_release,
            )
            self._fn_monitor.start()

        logger.info("Hotkey manager started")

    def stop(self) -> None:
        """Stop listening for global hotkeys."""
        self._running = False
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._fn_monitor is not None:
            self._fn_monitor.stop()
            self._fn_monitor = None
        self._pressed_keys.clear()
        self._ptt_active = False
        logger.info("Hotkey manager stopped")

    def _on_fn_press(self) -> None:
        """Called when the fn key is pressed (from CGEvent tap)."""
        self._pressed_keys.add(_FN_KEY_SENTINEL)
        self._check_hotkeys(_FN_KEY_SENTINEL)

    def _on_fn_release(self) -> None:
        """Called when the fn key is released (from CGEvent tap)."""
        self._pressed_keys.discard(_FN_KEY_SENTINEL)

        if self._ptt_key == _FN_KEY_SENTINEL and self._ptt_active:
            self._ptt_active = False
            logger.debug("Push-to-talk stopped (fn released)")
            self._on_ptt_stop()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Called when a regular key is pressed (from pynput)."""
        normalized = _normalize_key(key)
        self._pressed_keys.add(normalized)
        self._check_hotkeys(normalized)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Called when a regular key is released (from pynput)."""
        normalized = _normalize_key(key)
        self._pressed_keys.discard(normalized)

        if normalized == self._ptt_key and self._ptt_active:
            self._ptt_active = False
            logger.debug("Push-to-talk stopped")
            self._on_ptt_stop()

    def _check_hotkeys(self, triggered_key) -> None:
        """Check if any hotkey combo is satisfied after a key press."""
        # Check hands-free combo first (all keys in the combo must be pressed)
        if self._hf_keys and self._hf_keys.issubset(self._pressed_keys):
            logger.debug("Hands-free toggle triggered")
            self._on_hf_toggle()
            return

        # Check push-to-talk (single key)
        if triggered_key == self._ptt_key and not self._ptt_active:
            self._ptt_active = True
            logger.debug("Push-to-talk started")
            self._on_ptt_start()

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

        old_uses_fn = self._uses_fn
        self._uses_fn = self._ptt_key == _FN_KEY_SENTINEL or _FN_KEY_SENTINEL in self._hf_keys

        # Start/stop fn monitor as needed
        if self._running:
            if self._uses_fn and not old_uses_fn and self._fn_monitor is None:
                self._fn_monitor = _FnKeyMonitor(
                    on_press=self._on_fn_press,
                    on_release=self._on_fn_release,
                )
                self._fn_monitor.start()
            elif not self._uses_fn and old_uses_fn and self._fn_monitor is not None:
                self._fn_monitor.stop()
                self._fn_monitor = None
