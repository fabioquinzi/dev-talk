"""Text injection into the active application.

Two methods:
1. Clipboard paste (Cmd+V) — fast, good for bulk text
2. CGEvent keyboard simulation — character-by-character, good for streaming

Requires macOS Accessibility permission.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def _get_quartz():
    """Lazy import Quartz to avoid import errors on non-macOS."""
    import Quartz

    return Quartz


def _get_appkit():
    """Lazy import AppKit."""
    import AppKit

    return AppKit


def paste_text(text: str) -> None:
    """Inject text by copying to clipboard and simulating Cmd+V.

    This is the fastest method for injecting large blocks of text.
    """
    if not text:
        return

    AppKit = _get_appkit()
    Quartz = _get_quartz()

    # Save current clipboard content
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    old_contents = pasteboard.stringForType_(AppKit.NSStringPboardType)

    # Set new text on clipboard
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, AppKit.NSStringPboardType)

    # Small delay to ensure pasteboard is ready
    time.sleep(0.05)

    # Simulate Cmd+V
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    # Key down V with Cmd modifier
    key_down = Quartz.CGEventCreateKeyboardEvent(source, 9, True)  # 9 = 'v' keycode
    Quartz.CGEventSetFlags(key_down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_down)

    # Key up V
    key_up = Quartz.CGEventCreateKeyboardEvent(source, 9, False)
    Quartz.CGEventSetFlags(key_up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_up)

    # Wait for paste to complete
    time.sleep(0.1)

    # Restore old clipboard content
    if old_contents is not None:
        pasteboard.clearContents()
        pasteboard.setString_forType_(old_contents, AppKit.NSStringPboardType)

    logger.debug("Pasted %d characters", len(text))


def type_text(text: str, delay: float = 0.01) -> None:
    """Inject text by simulating individual key events via CGEvent.

    Slower but works for streaming — types character-by-character.

    Args:
        text: The text to type.
        delay: Delay between characters in seconds.
    """
    if not text:
        return

    Quartz = _get_quartz()

    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    for char in text:
        # Create a key event and set the Unicode string
        key_down = Quartz.CGEventCreateKeyboardEvent(source, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(key_down, len(char), char)
        Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_down)

        key_up = Quartz.CGEventCreateKeyboardEvent(source, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(key_up, len(char), char)
        Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_up)

        if delay > 0:
            time.sleep(delay)

    logger.debug("Typed %d characters", len(text))


def inject_text(text: str, method: str = "paste") -> None:
    """Inject text into the currently focused text field.

    Args:
        text: The text to inject.
        method: "paste" for clipboard-based, "type" for character-by-character.
    """
    if not text:
        return

    if method == "paste":
        paste_text(text)
    elif method == "type":
        type_text(text)
    else:
        raise ValueError(f"Unknown injection method: {method!r}. Use 'paste' or 'type'.")
