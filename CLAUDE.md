# Dev Talk — Project Context

## What is this?

Dev Talk is a macOS menubar speech-to-text application inspired by [Wispr Flow](https://wisprflow.ai/). It captures audio from any microphone, transcribes it locally using MLX Whisper (or remotely via OpenAI API), and injects the text into whatever app/field is currently focused.

## Target Platform

- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.12+
- English only

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| macOS menubar | `rumps` + `PyObjC` |
| STT (local) | `mlx-whisper` (whisper-large-v3-turbo) |
| STT (remote) | OpenAI Whisper API (`openai` SDK) |
| Audio capture | `sounddevice` (PortAudio) |
| Global hotkeys | `pynput` |
| Text injection | `PyObjC` / Quartz CGEvent |
| Packaging | `py2app` |
| Testing | `pytest` |

## Project Structure

```
src/dev_talk/          — Main application package
  app.py               — rumps menubar app entry point
  audio.py             — Microphone management and recording
  transcriber.py       — STT engine abstraction
  engines/
    local_mlx.py       — MLX Whisper local engine
    remote_openai.py   — OpenAI API remote engine
  hotkeys.py           — Global keyboard shortcuts
  text_input.py        — CGEvent text injection
  overlay.py           — Floating recording indicator
  config.py            — Settings persistence (~/.config/dev-talk/config.json)
tests/                 — pytest test suite
```

## Key Design Decisions

1. **Local-first:** Default engine is MLX Whisper running on Apple Silicon. OpenAI API is an optional fallback.
2. **Two transcription modes:** Streaming (chunked 3s segments, text appears while speaking) and non-streaming (full recording then transcribe). User can toggle between them.
3. **Text injection:** Uses clipboard paste (Cmd+V) by default for speed; CGEvent character-by-character for streaming mode.
4. **Permissions:** App needs Accessibility + Microphone + Input Monitoring permissions on macOS.

## Development Workflow

- All development happens on the `develop` branch
- Each task/feature gets its own commit
- User merges to `main` after testing
- Run tests: `pytest tests/`
- Run app: `python -m dev_talk`
- Build .app: `python setup.py py2app`

## Conventions

- Use latest versions of all Python packages
- Never mention AI authorship in commits
- Keep modules focused and testable
- Type hints on all public interfaces
- Config stored at `~/.config/dev-talk/config.json`
