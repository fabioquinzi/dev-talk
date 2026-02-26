# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this?

Dev Talk is a macOS menubar speech-to-text app for Apple Silicon. It captures audio, transcribes locally via MLX Whisper (or remotely via OpenAI API), and injects text into the focused application. Inspired by [Wispr Flow](https://wisprflow.ai/).

- macOS on Apple Silicon only (M1/M2/M3/M4), Python 3.12+, English only
- Local-first: default engine is MLX Whisper (`mlx-community/whisper-large-v3-turbo`, ~1.6 GB)

## Commands

```bash
# Install (editable + dev deps)
pip install -e ".[dev]"

# Run the app
python -m dev_talk

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_hotkeys.py -v

# Run a single test
pytest tests/test_app.py::TestPushToTalk::test_ptt_start_calls_start_recording -v

# Lint (ruff is configured in pyproject.toml, line-length=100, target py312)
ruff check src/ tests/
ruff format src/ tests/

# Build standalone .app
python setup.py py2app
```

## Architecture

### Data flow

Hotkey pressed → AudioManager records 16kHz mono float32 → Transcriber pre-filters (energy gate → Silero VAD) → engine transcribes → `inject_text()` pastes into focused app via Cmd+V (or CGEvent char-by-char for streaming)

### Anti-hallucination (vad.py)

3-layer defense against Whisper generating phantom text on silence:
1. **Energy gate** — `is_silent()` skips audio below RMS threshold (default -40 dB). Cost: ~0
2. **Silero VAD** — `VoiceActivityDetector` uses `silero-vad-lite` to detect speech in 32ms windows. Gracefully degrades if not installed. Cost: <1ms
3. **Tuned Whisper params** — `condition_on_previous_text=False`, `word_timestamps=True`, `no_speech_threshold=0.3`, `temperature=(0.0,)` in MLX engine

### Two transcription modes

1. **Full recording** — record everything, then transcribe the whole buffer at once via `Transcriber.transcribe_full()`
2. **Streaming** — `AudioManager.stream_chunks()` yields 3s chunks in a background thread, `Transcriber.transcribe_streaming()` yields text incrementally

### Engine protocol

All STT engines implement the `TranscriberEngine` protocol (in `transcriber.py`): `transcribe(audio, language)`, `is_available()`, `get_name()`. The `Transcriber` class is a coordinator that delegates to a pluggable engine. Two implementations exist: `MLXWhisperEngine` (local) and `OpenAIWhisperEngine` (remote).

### Hotkey system

Uses **NSEvent global monitors** via PyObjC/AppKit (not pynput). Key types: `_Modifier` (detected via flag bits on NSEventMaskFlagsChanged), `_KeyCode` (macOS virtual keycodes), `_CharKey` (single characters). The `HotkeyManager` tracks modifier flag state and pressed keys, then checks combos. Default: `fn` for push-to-talk, `fn+Space` for hands-free toggle.

### Overlay

`RecordingOverlay` is a native floating NSWindow (PyObjC) with a pill shape, status dot, label, audio level bars, and a stop button. Button target uses an NSObject subclass wrapper (`_make_button_target`) since plain Python objects can't receive ObjC selector dispatch. State machine: HIDDEN → LOADING → RECORDING → RECORDING_HANDS_FREE → TRANSCRIBING. Must be updated from the main thread (use `callAfter` from background threads).

### Threading model

`app.py` is the orchestrator. Recording, streaming transcription, engine warmup, and audio level monitoring all run in daemon threads. UI updates are dispatched to the main thread via `PyObjCTools.AppHelper.callAfter`. The MLX engine uses a `_gpu_lock` since Metal can't handle concurrent transcriptions.

### Text injection

Two methods in `text_input.py`: clipboard paste (Cmd+V via CGEvent — fast, default) and character-by-character CGEvent keyboard simulation (for streaming). Both require Accessibility permission.

## Test patterns

- Tests are fully mocked — no real audio, models, or GUI needed
- **App tests** use `MethodType` binding: `_make_app()` creates a plain object, binds all `DevTalkApp` methods to it, and sets mocked subsystems as attributes. This avoids `rumps.App.__init__` which requires a running macOS app
- `callAfter` is patched to execute synchronously (`_sync_call_after`)
- `mlx_whisper` is always mocked to avoid downloading the 1.6 GB model
- PyObjC/AppKit/Quartz imports are mocked in tests that touch overlay, hotkeys, or text injection

## Conventions

- All development on the `develop` branch; user merges to `main`
- Use latest versions of all Python packages
- Never mention AI authorship in commits
- Type hints on all public interfaces
- Config stored at `~/.config/dev-talk/config.json` (see `config.py` for all fields with defaults)
- macOS permissions needed: Accessibility, Microphone (attributed to the host terminal when running from CLI)
