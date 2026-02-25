"""System diagnostics and permission checks.

Verifies macOS permissions (Accessibility, Microphone) and tests hardware
functionality (mic recording, hotkey detection).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    PASS = auto()
    FAIL = auto()
    WARN = auto()


@dataclass
class DiagnosticResult:
    name: str
    status: CheckStatus
    message: str


def get_host_app() -> str:
    """Return a friendly name for the parent process that owns permissions."""
    try:
        ppid = os.getppid()
        result = subprocess.run(
            ["ps", "-p", str(ppid), "-o", "comm="],
            capture_output=True, text=True, timeout=2,
        )
        name = result.stdout.strip()
        if not name:
            return "Unknown"
        # Map common process names to friendly names
        lower = name.lower()
        if "code" in lower or "electron" in lower:
            return "Visual Studio Code"
        if "iterm" in lower:
            return "iTerm2"
        if "terminal" in lower:
            return "Terminal"
        if "warp" in lower:
            return "Warp"
        # Return last path component
        return name.rsplit("/", 1)[-1]
    except Exception:
        return "Unknown"


def check_accessibility() -> DiagnosticResult:
    """Check if Accessibility permission is granted."""
    try:
        from ApplicationServices import AXIsProcessTrusted

        if AXIsProcessTrusted():
            return DiagnosticResult("Accessibility", CheckStatus.PASS, "Granted")
        return DiagnosticResult(
            "Accessibility", CheckStatus.FAIL,
            "NOT granted. Required for hotkeys and text injection."
        )
    except ImportError:
        return DiagnosticResult(
            "Accessibility", CheckStatus.WARN,
            "Could not check (ApplicationServices unavailable)."
        )


def check_microphone() -> DiagnosticResult:
    """Check if microphone is accessible via sounddevice."""
    try:
        import sounddevice as sd

        with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1024):
            pass
        return DiagnosticResult("Microphone", CheckStatus.PASS, "Accessible")
    except Exception as e:
        return DiagnosticResult("Microphone", CheckStatus.FAIL, f"Failed: {e}")


def test_microphone_recording(device_id: int | None = None) -> DiagnosticResult:
    """Record 1 second of audio and verify capture works."""
    try:
        import numpy as np
        import sounddevice as sd

        duration = 1.0
        audio = sd.rec(
            int(16000 * duration),
            samplerate=16000,
            channels=1,
            dtype="float32",
            device=device_id,
        )
        sd.wait()
        audio = audio.flatten()

        if audio.size == 0:
            return DiagnosticResult(
                "Mic Recording", CheckStatus.FAIL, "No audio captured (0 samples)."
            )

        peak = float(np.max(np.abs(audio)))
        if peak < 0.001:
            return DiagnosticResult(
                "Mic Recording", CheckStatus.WARN,
                f"Captured {duration:.0f}s but very quiet (peak={peak:.4f}). "
                "Check mic volume or try speaking."
            )
        return DiagnosticResult(
            "Mic Recording", CheckStatus.PASS,
            f"OK — {duration:.0f}s captured, peak level={peak:.3f}"
        )
    except Exception as e:
        return DiagnosticResult("Mic Recording", CheckStatus.FAIL, f"Failed: {e}")


def test_fn_key_detection() -> tuple[threading.Event, object]:
    """Start a temporary fn key monitor and return (event, monitor_handle).

    The event is set when fn is pressed. Caller must call handle.stop().
    Uses the same NSEvent approach as HotkeyManager.
    """
    detected = threading.Event()

    class _FnTestMonitor:
        def __init__(self):
            self._monitor = None

        def start(self):
            try:
                import AppKit

                mask = AppKit.NSEventMaskFlagsChanged
                self._monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    mask, self._handle
                )
            except ImportError:
                pass

        def _handle(self, event):
            try:
                import AppKit

                if event.type() == AppKit.NSEventTypeFlagsChanged:
                    if event.modifierFlags() & 0x800000:  # fn flag
                        detected.set()
            except Exception:
                pass

        def stop(self):
            if self._monitor is not None:
                try:
                    import AppKit

                    AppKit.NSEvent.removeMonitor_(self._monitor)
                except ImportError:
                    pass
                self._monitor = None

    monitor = _FnTestMonitor()
    monitor.start()
    return detected, monitor


def check_all_permissions() -> list[DiagnosticResult]:
    """Run all permission checks."""
    return [check_accessibility(), check_microphone()]


def format_results(results: list[DiagnosticResult], host_app: str) -> str:
    """Format diagnostic results for display in an alert."""
    icons = {CheckStatus.PASS: "✓", CheckStatus.FAIL: "✗", CheckStatus.WARN: "⚠"}
    lines = [f"Running inside: {host_app}", f"Permissions apply to {host_app}.", ""]

    all_pass = True
    for r in results:
        icon = icons[r.status]
        lines.append(f"{icon}  {r.name}: {r.message}")
        if r.status != CheckStatus.PASS:
            all_pass = False

    if all_pass:
        lines.append("\nAll checks passed!")
    else:
        lines.append(f"\nGrant permissions to {host_app} in:")
        lines.append("System Settings → Privacy & Security")

    return "\n".join(lines)
