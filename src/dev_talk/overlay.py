"""Floating recording indicator overlay.

Shows a pill-shaped window near the bottom of the screen to indicate
recording state. Includes audio level bars and a stop button for
hands-free mode. Uses PyObjC for native macOS windows.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger(__name__)

# Audio level bars layout
_NUM_BARS = 16
_BAR_WIDTH = 3
_BAR_GAP = 2
_BAR_MIN_HEIGHT = 4
_BAR_MAX_HEIGHT = 22


class OverlayState(Enum):
    HIDDEN = auto()
    LOADING = auto()
    RECORDING = auto()
    RECORDING_HANDS_FREE = auto()
    TRANSCRIBING = auto()


def _get_appkit():
    import AppKit
    import Quartz  # noqa: F401 — registers CGColorRef type, suppresses ObjCPointerWarning
    return AppKit


def _make_button_target(callback):
    """Create an NSObject subclass instance that forwards button clicks to a callback.

    NSButton target/action requires an Objective-C object — a plain Python class
    won't receive the selector dispatch from the ObjC runtime.
    """
    AppKit = _get_appkit()

    class _ButtonTarget(AppKit.NSObject):
        def stopClicked_(self, sender):
            callback()

    return _ButtonTarget.alloc().init()


class RecordingOverlay:
    """Floating pill overlay near the dock showing recording state.

    Features:
    - Status indicator dot with label
    - Audio level bars that respond to microphone input
    - Clickable stop button (hands-free mode only)

    Must be updated from the main thread (use callAfter from background threads).
    """

    PILL_WIDTH = 320
    PILL_HEIGHT = 40
    BOTTOM_MARGIN = 80  # Above the dock

    def __init__(self, on_stop: Callable[[], None] | None = None) -> None:
        self._state = OverlayState.HIDDEN
        self._on_stop = on_stop or (lambda: None)
        self._window = None
        self._content = None
        self._label = None
        self._indicator = None
        self._bars: list = []
        self._stop_button = None
        self._button_target = None
        self._initialized = False

    @property
    def on_stop(self) -> Callable[[], None]:
        return self._on_stop

    @on_stop.setter
    def on_stop(self, value: Callable[[], None]) -> None:
        self._on_stop = value

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
        self._content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, self.PILL_WIDTH, self.PILL_HEIGHT)
        )
        self._content.setWantsLayer_(True)
        self._content.layer().setCornerRadius_(self.PILL_HEIGHT / 2)
        self._content.layer().setMasksToBounds_(True)
        self._content.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85).CGColor()
        )

        # Status indicator dot
        self._indicator = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(14, 12, 16, 16)
        )
        self._indicator.setWantsLayer_(True)
        self._indicator.layer().setCornerRadius_(8)
        self._indicator.layer().setBackgroundColor_(
            AppKit.NSColor.redColor().CGColor()
        )

        # Label
        self._label = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(38, 8, 100, 24)
        )
        self._label.setStringValue_("Recording...")
        self._label.setBezeled_(False)
        self._label.setDrawsBackground_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium))

        # Audio level bars
        bars_x = 145
        dim_color = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.3, 0.3, 0.3, 1.0)
        self._bars = []
        for i in range(_NUM_BARS):
            bar_x = bars_x + i * (_BAR_WIDTH + _BAR_GAP)
            bar = AppKit.NSView.alloc().initWithFrame_(
                AppKit.NSMakeRect(bar_x, (self.PILL_HEIGHT - _BAR_MIN_HEIGHT) / 2, _BAR_WIDTH, _BAR_MIN_HEIGHT)
            )
            bar.setWantsLayer_(True)
            bar.layer().setCornerRadius_(1.5)
            bar.layer().setBackgroundColor_(dim_color.CGColor())
            self._content.addSubview_(bar)
            self._bars.append(bar)

        # Stop button (shown only in hands-free mode)
        stop_x = self.PILL_WIDTH - 40
        self._stop_button = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(stop_x, 6, 28, 28)
        )
        self._stop_button.setBezelStyle_(AppKit.NSBezelStyleCircular)
        self._stop_button.setBordered_(False)
        self._stop_button.setWantsLayer_(True)
        self._stop_button.layer().setCornerRadius_(14)
        self._stop_button.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.8, 0.2, 0.2, 1.0).CGColor()
        )
        attr_title = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            "\u25A0",  # Black square (stop icon)
            {
                AppKit.NSForegroundColorAttributeName: AppKit.NSColor.whiteColor(),
                AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_weight_(10, AppKit.NSFontWeightBold),
            },
        )
        self._stop_button.setAttributedTitle_(attr_title)
        self._button_target = _make_button_target(self._on_stop)
        self._stop_button.setTarget_(self._button_target)
        self._stop_button.setAction_("stopClicked:")
        self._stop_button.setHidden_(True)

        self._content.addSubview_(self._indicator)
        self._content.addSubview_(self._label)
        self._content.addSubview_(self._stop_button)
        self._window.setContentView_(self._content)

        self._initialized = True
        logger.debug("Recording overlay initialized")

    @property
    def state(self) -> OverlayState:
        return self._state

    def show_loading(self) -> None:
        """Show the overlay in model loading state."""
        self._update_state(OverlayState.LOADING)

    def show_recording(self, hands_free: bool = False) -> None:
        """Show the overlay in recording state."""
        if hands_free:
            self._update_state(OverlayState.RECORDING_HANDS_FREE)
        else:
            self._update_state(OverlayState.RECORDING)

    def show_transcribing(self) -> None:
        """Show the overlay in transcribing state."""
        self._update_state(OverlayState.TRANSCRIBING)

    def hide(self) -> None:
        """Hide the overlay."""
        self._update_state(OverlayState.HIDDEN)

    def update_level(self, peak: float) -> None:
        """Update the audio level bars (0.0 to 1.0). Must be called on main thread."""
        if self._state not in (OverlayState.RECORDING, OverlayState.RECORDING_HANDS_FREE):
            return
        if not self._initialized or not self._bars:
            return

        try:
            AppKit = _get_appkit()
            # Amplify quiet signals for better visual response
            level = min(peak * 3.0, 1.0)

            for i, bar in enumerate(self._bars):
                threshold = (i + 1) / _NUM_BARS
                if level >= threshold:
                    # Active — green to yellow to red
                    frac = i / _NUM_BARS
                    if frac < 0.6:
                        color = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.2, 0.8, 0.4, 1.0)
                    elif frac < 0.8:
                        color = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.9, 0.8, 0.2, 1.0)
                    else:
                        color = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.9, 0.3, 0.2, 1.0)
                    bar_height = _BAR_MIN_HEIGHT + int((_BAR_MAX_HEIGHT - _BAR_MIN_HEIGHT) * level)
                else:
                    # Inactive — dim
                    color = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.3, 0.3, 0.3, 1.0)
                    bar_height = _BAR_MIN_HEIGHT

                bar.layer().setBackgroundColor_(color.CGColor())
                frame = bar.frame()
                bar.setFrame_(AppKit.NSMakeRect(
                    frame.origin.x,
                    (self.PILL_HEIGHT - bar_height) / 2,
                    _BAR_WIDTH,
                    bar_height,
                ))
        except Exception:
            pass  # Don't crash on level update failures

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
            self._window.setIgnoresMouseEvents_(True)
            self._reset_bars()
            return

        if new_state == OverlayState.LOADING:
            self._label.setStringValue_("Loading model...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.systemBlueColor().CGColor()
            )
            self._stop_button.setHidden_(True)
            self._window.setIgnoresMouseEvents_(True)
            self._reset_bars()
        elif new_state == OverlayState.RECORDING:
            self._label.setStringValue_("Recording...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.redColor().CGColor()
            )
            self._stop_button.setHidden_(True)
            self._window.setIgnoresMouseEvents_(True)
        elif new_state == OverlayState.RECORDING_HANDS_FREE:
            self._label.setStringValue_("Listening...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.redColor().CGColor()
            )
            self._stop_button.setHidden_(False)
            self._window.setIgnoresMouseEvents_(False)
        elif new_state == OverlayState.TRANSCRIBING:
            self._label.setStringValue_("Transcribing...")
            self._indicator.layer().setBackgroundColor_(
                AppKit.NSColor.systemYellowColor().CGColor()
            )
            self._stop_button.setHidden_(True)
            self._window.setIgnoresMouseEvents_(True)
            self._reset_bars()

        self._window.orderFront_(None)

    def _reset_bars(self) -> None:
        """Reset all bars to inactive state."""
        if not self._bars:
            return
        try:
            AppKit = _get_appkit()
            dim = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.3, 0.3, 0.3, 1.0)
            for bar in self._bars:
                bar.layer().setBackgroundColor_(dim.CGColor())
                frame = bar.frame()
                bar.setFrame_(AppKit.NSMakeRect(
                    frame.origin.x, (self.PILL_HEIGHT - _BAR_MIN_HEIGHT) / 2,
                    _BAR_WIDTH, _BAR_MIN_HEIGHT,
                ))
        except Exception:
            pass

    def cleanup(self) -> None:
        """Remove the overlay window."""
        if self._window is not None:
            self._window.orderOut_(None)
            self._window = None
        self._bars = []
        self._initialized = False
