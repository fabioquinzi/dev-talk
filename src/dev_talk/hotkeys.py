"""Global hotkey manager for push-to-talk and hands-free modes.

Uses NSEvent global monitors (AppKit/PyObjC) to detect keyboard events
system-wide. Only requires Accessibility permission — no Input Monitoring
needed. This matches how Wispr Flow handles hotkeys on macOS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger(__name__)


class RecordingMode(Enum):
    PUSH_TO_TALK = auto()
    HANDS_FREE = auto()


# --- Key representation ---

@dataclass(frozen=True)
class _Modifier:
    """A modifier key detected via NSEvent modifier flags."""
    flag: int


@dataclass(frozen=True)
class _KeyCode:
    """A key identified by its macOS virtual key code."""
    code: int


@dataclass(frozen=True)
class _CharKey:
    """A key identified by its character."""
    char: str


ParsedKey = _Modifier | _KeyCode | _CharKey


# --- Key maps ---

# Modifier keys (detected via NSEventMaskFlagsChanged + modifierFlags)
_MODIFIER_MAP: dict[str, _Modifier] = {
    "fn": _Modifier(0x800000),       # NSEventModifierFlagFunction
    "ctrl": _Modifier(0x40000),      # NSEventModifierFlagControl
    "ctrl_l": _Modifier(0x40000),
    "ctrl_r": _Modifier(0x40000),
    "shift": _Modifier(0x20000),     # NSEventModifierFlagShift
    "shift_l": _Modifier(0x20000),
    "shift_r": _Modifier(0x20000),
    "alt": _Modifier(0x80000),       # NSEventModifierFlagOption
    "alt_l": _Modifier(0x80000),
    "alt_r": _Modifier(0x80000),
    "cmd": _Modifier(0x100000),      # NSEventModifierFlagCommand
    "cmd_l": _Modifier(0x100000),
    "cmd_r": _Modifier(0x100000),
    "caps_lock": _Modifier(0x10000), # NSEventModifierFlagCapsLock
}

# Regular keys (detected via keyDown/keyUp + keyCode)
_KEYCODE_MAP: dict[str, _KeyCode] = {
    "space": _KeyCode(49),
    "tab": _KeyCode(48),
    "enter": _KeyCode(36),
    "esc": _KeyCode(53),
    "backspace": _KeyCode(51),
    "delete": _KeyCode(117),
    "up": _KeyCode(126),
    "down": _KeyCode(125),
    "left": _KeyCode(123),
    "right": _KeyCode(124),
    "home": _KeyCode(115),
    "end": _KeyCode(119),
    "page_up": _KeyCode(116),
    "page_down": _KeyCode(121),
    "f1": _KeyCode(122),
    "f2": _KeyCode(120),
    "f3": _KeyCode(99),
    "f4": _KeyCode(118),
    "f5": _KeyCode(96),
    "f6": _KeyCode(97),
    "f7": _KeyCode(98),
    "f8": _KeyCode(100),
    "f9": _KeyCode(101),
    "f10": _KeyCode(109),
    "f11": _KeyCode(103),
    "f12": _KeyCode(111),
    "f13": _KeyCode(105),
    "f14": _KeyCode(107),
    "f15": _KeyCode(113),
    "f16": _KeyCode(106),
    "f17": _KeyCode(64),
    "f18": _KeyCode(79),
    "f19": _KeyCode(80),
    "f20": _KeyCode(90),
}


def parse_key(key_str: str) -> ParsedKey:
    """Parse a key name string into a key object."""
    key_str = key_str.lower().strip()
    if key_str in _MODIFIER_MAP:
        return _MODIFIER_MAP[key_str]
    if key_str in _KEYCODE_MAP:
        return _KEYCODE_MAP[key_str]
    if len(key_str) == 1:
        return _CharKey(key_str)
    raise ValueError(f"Unknown key: {key_str!r}")


class HotkeyManager:
    """Manages global keyboard shortcuts for recording control.

    Uses NSEvent global monitors — only requires Accessibility permission.
    Default: fn (push-to-talk), fn+Space (hands-free toggle).
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
        self._hf_keys: set[ParsedKey] = {parse_key(k) for k in (hands_free_keys or ["fn", "space"])}

        self._on_ptt_start = on_push_to_talk_start or (lambda: None)
        self._on_ptt_stop = on_push_to_talk_stop or (lambda: None)
        self._on_hf_toggle = on_hands_free_toggle or (lambda: None)

        self._current_flags: int = 0
        self._pressed_keys: set[ParsedKey] = set()
        self._ptt_active = False
        self._monitors: list = []
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for global hotkeys via NSEvent monitors."""
        if self._running:
            return

        self._running = True

        try:
            import AppKit

            mask = (
                AppKit.NSEventMaskFlagsChanged
                | AppKit.NSEventMaskKeyDown
                | AppKit.NSEventMaskKeyUp
            )
            monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                mask, self._handle_event
            )
            if monitor is not None:
                self._monitors.append(monitor)
                logger.info("Hotkey manager started (NSEvent global monitor)")
            else:
                logger.warning(
                    "Could not create NSEvent global monitor. "
                    "Grant Accessibility permission in System Settings."
                )
        except ImportError:
            logger.warning("AppKit not available — hotkey monitoring disabled")

    def stop(self) -> None:
        """Stop listening for global hotkeys."""
        self._running = False
        try:
            import AppKit

            for monitor in self._monitors:
                AppKit.NSEvent.removeMonitor_(monitor)
        except ImportError:
            pass
        self._monitors.clear()
        self._pressed_keys.clear()
        self._current_flags = 0
        self._ptt_active = False
        logger.info("Hotkey manager stopped")

    def _handle_event(self, event) -> None:
        """Process an NSEvent from the global monitor."""
        try:
            import AppKit

            event_type = event.type()
            if event_type == AppKit.NSEventTypeFlagsChanged:
                self._on_flags_changed(event.modifierFlags())
            elif event_type == AppKit.NSEventTypeKeyDown:
                chars = (event.charactersIgnoringModifiers() or "").lower()
                self._on_key_down(event.keyCode(), chars)
            elif event_type == AppKit.NSEventTypeKeyUp:
                chars = (event.charactersIgnoringModifiers() or "").lower()
                self._on_key_up(event.keyCode(), chars)
        except Exception:
            logger.exception("Error handling keyboard event")

    # --- Internal methods (also used directly in tests) ---

    def _on_flags_changed(self, new_flags: int) -> None:
        """Handle modifier key state changes."""
        old_flags = self._current_flags
        self._current_flags = new_flags

        # Collect all modifiers we care about
        watched: set[_Modifier] = set()
        if isinstance(self._ptt_key, _Modifier):
            watched.add(self._ptt_key)
        watched.update(k for k in self._hf_keys if isinstance(k, _Modifier))

        for mod in watched:
            was_pressed = bool(old_flags & mod.flag)
            is_pressed = bool(new_flags & mod.flag)

            if is_pressed and not was_pressed:
                self._check_hotkeys(mod)
            elif was_pressed and not is_pressed:
                if mod == self._ptt_key and self._ptt_active:
                    self._ptt_active = False
                    logger.debug("Push-to-talk stopped (%s released)", mod)
                    self._on_ptt_stop()

    def _on_key_down(self, key_code: int, chars: str) -> None:
        """Handle regular key press."""
        code_key = _KeyCode(key_code)
        self._pressed_keys.add(code_key)
        if chars:
            self._pressed_keys.add(_CharKey(chars))

        # Find which configured key this matches
        triggered = None
        if code_key in self._hf_keys or code_key == self._ptt_key:
            triggered = code_key
        elif chars:
            ck = _CharKey(chars)
            if ck in self._hf_keys or ck == self._ptt_key:
                triggered = ck

        if triggered is not None:
            self._check_hotkeys(triggered)

    def _on_key_up(self, key_code: int, chars: str) -> None:
        """Handle regular key release."""
        code_key = _KeyCode(key_code)
        self._pressed_keys.discard(code_key)
        if chars:
            self._pressed_keys.discard(_CharKey(chars))

        # Check PTT release
        released = code_key == self._ptt_key
        if not released and chars:
            released = _CharKey(chars) == self._ptt_key

        if released and self._ptt_active:
            self._ptt_active = False
            logger.debug("Push-to-talk stopped")
            self._on_ptt_stop()

    def _is_combo_active(self, keys: set[ParsedKey]) -> bool:
        """Check if all keys in a combo are currently pressed."""
        for key in keys:
            if isinstance(key, _Modifier):
                if not (self._current_flags & key.flag):
                    return False
            else:
                if key not in self._pressed_keys:
                    return False
        return True

    def _check_hotkeys(self, triggered_key: ParsedKey) -> None:
        """Check if any hotkey combo is satisfied after a key press."""
        # Hands-free combo takes priority (all keys must be pressed)
        if self._hf_keys and self._is_combo_active(self._hf_keys):
            # If PTT was active, cancel it silently — don't fire ptt_stop,
            # the recording will continue under hands-free control.
            if self._ptt_active:
                self._ptt_active = False
                logger.debug("PTT cancelled — switching to hands-free")
            logger.debug("Hands-free toggle triggered")
            self._on_hf_toggle()
            return

        # Push-to-talk (single key)
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
