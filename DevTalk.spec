# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Dev Talk macOS app bundle."""

import os
import sys
from pathlib import Path

block_cipher = None

# Paths
SITE_PACKAGES = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
SRC_DIR = Path("src")
RESOURCES_DIR = SRC_DIR / "dev_talk" / "resources"

# silero-vad-lite ships native libs + ONNX model as data files
silero_data = str(SITE_PACKAGES / "silero_vad_lite" / "data")

# mlx_whisper assets (tokenizer, mel filters, etc.)
mlx_whisper_dir = str(SITE_PACKAGES / "mlx_whisper")

# sounddevice PortAudio dylib
sounddevice_data = str(SITE_PACKAGES / "_sounddevice_data")

a = Analysis(
    ["src/dev_talk/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # App resources (menubar icons)
        (str(RESOURCES_DIR / "waveform_idle.png"), "dev_talk/resources"),
        (str(RESOURCES_DIR / "waveform_idle@2x.png"), "dev_talk/resources"),
        (str(RESOURCES_DIR / "waveform_recording.png"), "dev_talk/resources"),
        (str(RESOURCES_DIR / "waveform_recording@2x.png"), "dev_talk/resources"),
        # silero-vad-lite data (ONNX model + native libs)
        (silero_data, "silero_vad_lite/data"),
        # mlx_whisper assets
        (mlx_whisper_dir + "/assets", "mlx_whisper/assets"),
        # PortAudio dylib
        (sounddevice_data, "_sounddevice_data"),
    ],
    hiddenimports=[
        "dev_talk",
        "dev_talk.app",
        "dev_talk.audio",
        "dev_talk.config",
        "dev_talk.diagnostics",
        "dev_talk.engines",
        "dev_talk.engines.local_mlx",
        "dev_talk.engines.remote_openai",
        "dev_talk.hotkeys",
        "dev_talk.overlay",
        "dev_talk.text_input",
        "dev_talk.transcriber",
        "dev_talk.vad",
        "rumps",
        "mlx",
        "mlx.core",
        "mlx.nn",
        "mlx_whisper",
        "sounddevice",
        "numpy",
        "openai",
        "silero_vad_lite",
        "AppKit",
        "Cocoa",
        "Quartz",
        "PyObjCTools",
        "PyObjCTools.AppHelper",
        "objc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "scipy",
        "llvmlite",
        "numba",
        "PIL",
        "Pillow",
        "pytest",
        "py",
        "pygments",
        "jinja2",
        "tensorboard",
        "fsspec",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Dev Talk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Dev Talk",
)

app = BUNDLE(
    coll,
    name="Dev Talk.app",
    icon=str(RESOURCES_DIR / "DevTalk.icns"),
    bundle_identifier="com.devtalk.app",
    info_plist={
        "LSUIElement": True,
        "CFBundleName": "Dev Talk",
        "CFBundleDisplayName": "Dev Talk",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSMicrophoneUsageDescription": "Dev Talk needs microphone access for speech-to-text.",
        "NSAccessibilityUsageDescription": "Dev Talk needs accessibility access to inject text and capture global hotkeys.",
        "NSHighResolutionCapable": True,
    },
)
