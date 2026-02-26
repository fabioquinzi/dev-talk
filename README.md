# Dev Talk

Local speech-to-text for macOS — speak anywhere, type everywhere.

A menubar application that captures your voice and transcribes it into text in any application, powered by [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) running locally on Apple Silicon. Inspired by [Wispr Flow](https://wisprflow.ai/).

## Features

- **Push-to-talk** — Hold a key (default: `fn`), speak, release to transcribe
- **Hands-free mode** — Press a combo (default: `fn+Space`) to toggle continuous recording
- **Streaming transcription** — Text appears while you speak (chunked processing)
- **Full recording mode** — Record everything, then transcribe at once (more accurate)
- **Local-first** — Runs entirely on your Mac using MLX Whisper, no cloud needed
- **OpenAI API fallback** — Optional cloud transcription via OpenAI Whisper API
- **Anti-hallucination** — 3-layer defense (energy gate + Silero VAD + tuned Whisper params) prevents phantom text on silence
- **Any microphone** — Select from all connected input devices
- **Any text field** — Injects text into whatever app is focused (via Cmd+V or keyboard simulation)
- **Recording indicator** — Floating pill overlay shows when you're recording
- **Menubar app** — Waveform icon lives in your menubar, turns red while recording

## Requirements

- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.12+
- ~1.6 GB disk space for the Whisper model (auto-downloaded on first run)
- ~2-4 GB RAM while running

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/fabioquinzi/dev-talk.git
cd dev-talk
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run the app

```bash
python -m dev_talk
```

The app will appear in your menubar. On first run, the Whisper model (~1.6 GB) will be downloaded automatically.

### 3. Grant permissions

macOS will prompt you to grant:
- **Microphone access** — for recording
- **Accessibility** — for global hotkeys and text injection (System Settings → Privacy & Security → Accessibility)

Use **Setup & Diagnostics** in the menubar dropdown to verify permissions and test hotkey detection.

> **Note:** When running from a terminal (VS Code, Terminal.app, iTerm), permissions are attributed to the terminal app, not Dev Talk. The diagnostics menu will tell you which app needs the permissions.

### 4. Start talking

- **Push-to-talk:** Hold `fn`, speak, release → text appears in your focused app
- **Hands-free:** Press `fn+Space` to start, speak freely, press again to stop

## Configuration

Settings are stored in `~/.config/dev-talk/config.json`. Edit directly or use the menubar dropdown.

```json
{
  "engine": "local",
  "model": "mlx-community/whisper-large-v3-turbo",
  "language": "en",
  "openai_api_key": "",
  "openai_model": "whisper-1",
  "push_to_talk_key": "fn",
  "hands_free_keys": ["fn", "space"],
  "mic_device_id": null,
  "streaming_mode": true,
  "chunk_duration_s": 3.0,
  "injection_method": "paste",
  "vad_enabled": true,
  "energy_threshold_db": -40.0
}
```

### Key settings

| Setting | Values | Description |
|---|---|---|
| `engine` | `"local"`, `"openai"` | STT engine to use |
| `model` | Any MLX Whisper model | Local model from HuggingFace |
| `streaming_mode` | `true`, `false` | Chunked streaming vs full recording |
| `chunk_duration_s` | `1.0` - `10.0` | Seconds per streaming chunk |
| `injection_method` | `"paste"`, `"type"` | Text injection method |
| `push_to_talk_key` | Any key name | Hold-to-record key |
| `hands_free_keys` | List of key names | Toggle-recording combo |
| `vad_enabled` | `true`, `false` | Voice activity detection to prevent hallucinations |
| `energy_threshold_db` | `-60.0` to `-20.0` | RMS energy gate threshold in dB |

### Using OpenAI API

To use the OpenAI Whisper API instead of local transcription:

1. Get an API key from [platform.openai.com](https://platform.openai.com/)
2. Add it to your config:
   ```json
   {
     "openai_api_key": "sk-your-key-here",
     "engine": "openai"
   }
   ```
3. Or switch engines from the menubar dropdown

Cost: ~$0.006/minute ($0.36/hour).

## Build Standalone App

```bash
pip install py2app
python setup.py py2app
```

The `.app` bundle will be in `dist/`. Copy it to `/Applications/`:

```bash
cp -r "dist/Dev Talk.app" /Applications/
```

## Development

### Run tests

```bash
pytest tests/ -v
```

### Project structure

```
src/dev_talk/
  app.py              — Menubar app (rumps) wiring everything together
  audio.py            — Microphone capture and device enumeration
  transcriber.py      — STT engine abstraction (protocol + coordinator)
  vad.py              — Voice activity detection and energy gating
  config.py           — JSON settings persistence
  hotkeys.py          — Global keyboard shortcuts (NSEvent global monitors)
  diagnostics.py      — Permission checks and hardware tests
  text_input.py       — Text injection via CGEvent / clipboard
  overlay.py          — Floating recording indicator (PyObjC)
  resources/          — Menubar waveform icons (idle/recording, 1x/2x)
  engines/
    local_mlx.py      — MLX Whisper local engine
    remote_openai.py  — OpenAI Whisper API engine
tests/                — pytest test suite
```

### Available hotkey names

Special keys: `fn`, `ctrl`, `shift`, `alt`, `cmd`, `space`, `tab`, `esc`, `f1`-`f20`, `caps_lock`, `enter`, `backspace`, `delete`, `up`, `down`, `left`, `right`, `home`, `end`, `page_up`, `page_down`

Single characters: `a`-`z`, `0`-`9`

## How It Works

1. **Hotkey pressed** → Audio recording starts from selected microphone
2. **Audio captured** → 16kHz mono float32 via PortAudio/sounddevice
3. **Pre-filtering** → Energy gate (skip silence) → Silero VAD (skip non-speech noise)
4. **Transcription** → Audio sent to MLX Whisper (local) or OpenAI API (remote)
   - Streaming mode: 3-second chunks transcribed incrementally
   - Full mode: entire recording transcribed at once
5. **Text injection** → Transcribed text pasted into the focused text field via Cmd+V
6. **Hotkey released** → Recording stops, overlay hides

## Resource Usage (M4 MacBook)

| Resource | Impact |
|---|---|
| Disk | ~1.6 GB model + ~100 MB app |
| RAM | ~2-4 GB while running |
| CPU/GPU | Brief spikes during transcription |
| Battery | Minimal — only active during recording |
| Accuracy | ~5-7% word error rate (English) |
| Speed | 10-27x real-time (10s audio in 0.4-1.2s) |

## License

MIT
