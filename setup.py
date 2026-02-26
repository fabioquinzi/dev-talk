"""py2app build script for Dev Talk.

Build a standalone macOS .app bundle:
    python setup.py py2app

Development mode (alias):
    python setup.py py2app -A
"""

from pathlib import Path

from setuptools import setup

APP = ["src/dev_talk/__main__.py"]
RESOURCES_DIR = Path("src/dev_talk/resources")
DATA_FILES = []
RESOURCE_FILES = [str(p) for p in RESOURCES_DIR.glob("*.png")]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": str(RESOURCES_DIR / "DevTalk.icns"),
    "plist": {
        "LSUIElement": True,  # Hide from Dock (menubar-only app)
        "CFBundleName": "Dev Talk",
        "CFBundleDisplayName": "Dev Talk",
        "CFBundleIdentifier": "com.devtalk.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSMicrophoneUsageDescription": "Dev Talk needs microphone access for speech-to-text.",
        "NSAccessibilityUsageDescription": "Dev Talk needs accessibility access to inject text and capture global hotkeys.",
    },
    "resources": RESOURCE_FILES,
    "packages": [
        "dev_talk",
        "dev_talk.engines",
        "rumps",
        "mlx",
        "mlx_whisper",
        "sounddevice",
        "numpy",
        "openai",
        "silero_vad_lite",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
