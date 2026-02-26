"""py2app build script for Dev Talk.

Build a standalone macOS .app bundle:
    python setup.py py2app

Development mode (alias):
    python setup.py py2app -A
"""

from setuptools import setup

APP = ["src/dev_talk/__main__.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,  # TODO: Add app icon
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
