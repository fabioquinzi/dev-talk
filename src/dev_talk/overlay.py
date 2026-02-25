"""Floating recording indicator overlay.

Shows a small pill-shaped window near the bottom of the screen
to indicate recording state. Uses PyObjC for native macOS windows.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto

logger = logging.getLogger(__name__)


class OverlayState(Enum):
    HIDDEN = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


def _get_appkit():
    import AppKit
    return AppKit


def _get_quartz():
    import Quartz
    return Quartz


class RecordingOverlay:
    """Floating pill overlay near the dock showing recording state.

    Must be created and updated from the main thread (or via performSelectorOnMainThread).
    """

    PILL_WIDTH = 200
    PILL_HEIGHT = 40
    BOTTOM_MARGIN = 80  # Above the dock

    def __init__(self) -> None:
        self._state = OverlayState.HIDDEN
        self._window = None
        self._label = None
        self._indicator = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Create the overlay window (must be called from main thread)."""
        if self._initialized:
            return

        AppKit = _get_appkit()

        # Get screen dimensions
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.frame()
        x = (screen_frame.size.width - self.PILL_WIDTH) / 2
        y = self.BOTTOM_MARGIN

        # Create borderless, floating window
        rect = AppKit.NSMakeRect(x, y, self.PILL_WIDTH, self.PILL_HEIGHT)
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(AppKit.NSFloatingWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._window.setHasShadow_(True)
        self._window.setIgnoresMouseEvents_(True)
        self._window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        # Content view with rounded corners
        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, self.PILL_WIDTH, self.PILL_HEIGHT)
        )
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(self.PILL_HEIGHT / 2)
        content.layer().setMasksToBounds_(True)
        content.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85).CGColor()
        )

        # Status indicator dot
        self._indicator = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(12, 12, 16, 16)
        )
        self._indicator.setWantsLayer_(True)
        self._indicator.layer().setCornerRadius_(8)
        self._indicator.layer().setBackgroundColor_(
            AppKit.NSColor.redColor().CGColor()
        )

        # Label
        self._label = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(36, 8, self.PILL_WIDTH - 48, 24)
        )
        self._label.setStringValue_("Recording...")
        self._label.setBezeled_(False)
        self._label.setDrawsBackground_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium))

        content.addSubview_(self._indicator)
        content.addSubview_(self._label)
        self._window.setContentView_(content)

        self._initialized = True
        logger.debug("Recording overlay initialized")

    @property
    def state(self) -> OverlayState:
        return self._state

    def show_recording(self) -> None:
        """Show the overlay in recording state."""
        self._update_state(OverlayState.RECORDING)

    def show_transcribing(self) -> None:
        """Show the overlay in transcribing state."""
        self._update_state(OverlayState.TRANSCRIBING)

    def hide(self) -> None:
        """Hide the overlay."""
        self._update_state(OverlayState.HIDDEN)

    def _update_state(self, new_state: OverlayState) -> None:
        """Update overlay appearance based on state."""
        self._state = new_state

        try:
            self._ensure_initialized()
        except Exception:
            logger.debug("Cannot initialize overlay (no GUI context)")
            return

        AppKit = _get_appkit()

        if new_state == OverlayState.HIDDEN:
            self._window.orderOut_(None)
            return

        if new_state == OverlayState.RECORDING:
            self._label.setStringValue_("Recording...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.redColor().CGColor()
            )
        elif new_state == OverlayState.TRANSCRIBING:
            self._label.setStringValue_("Transcribing...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.systemYellowColor().CGColor()
            )

        self._window.orderFront_(None)

    def cleanup(self) -> None:
        """Remove the overlay window."""
        if self._window is not None:
            self._window.orderOut_(None)
            self._window = None
        self._initialized = False
