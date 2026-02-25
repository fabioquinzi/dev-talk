# Dev Talk - Architecture & Design

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   macOS Menubar                      │
│  ┌──────────┐  ┌────────────┐  ┌────────────────┐  │
│  │ Mic Icon │  │ Mic Select │  │   Settings     │  │
│  └────┬─────┘  └─────┬──────┘  └───────┬────────┘  │
│       │               │                 │            │
├───────┴───────────────┴─────────────────┴────────────┤
│                    App Core (app.py)                  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Hotkeys  │  │  Audio   │  │   Transcriber    │  │
│  │ Manager  │  │ Capture  │  │   (abstract)     │  │
│  │          │  │          │  │                   │  │
│  │ pynput + │  │sounddevice│ │ ┌──────┐┌──────┐ │  │
│  └────┬─────┘  └────┬─────┘ │ │ MLX  ││OpenAI│ │  │
│       │              │       │ │Whisper││ API  │ │  │
│       │              │       │ └──────┘└──────┘ │  │
│       │              │       └────────┬─────────┘  │
│       │              │                │             │
│  ┌────┴──────────────┴────────────────┴──────────┐  │
│  │              Orchestrator                      │  │
│  │  - Manages recording state                     │  │
│  │  - Routes audio to transcriber                 │  │
│  │  - Sends text to injection                     │  │
│  └───────────────────────┬────────────────────────┘  │
│                          │                           │
│  ┌───────────────────────┴────────────────────────┐  │
│  │  Text Injection (CGEvent keyboard simulation)  │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Recording Overlay (floating NSWindow/NSPanel) │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## Module Design

### 1. `app.py` — Main Application

The rumps-based menubar application. Entry point for the entire app.

**Responsibilities:**
- Initialize all subsystems
- Render menubar icon + dropdown menu
- Handle menu interactions (mic selection, settings, quit)
- Coordinate between hotkeys, audio, transcriber, and text injection

### 2. `audio.py` — Audio Capture

Manages microphone enumeration and audio recording.

**Key interfaces:**
```python
class AudioManager:
    def list_devices() -> list[AudioDevice]
    def select_device(device_id: int) -> None
    def start_recording() -> None
    def stop_recording() -> numpy.ndarray  # Returns audio data
    def get_audio_chunk(duration_s: float) -> numpy.ndarray  # For streaming
    def is_recording() -> bool
```

**Details:**
- Uses `sounddevice` for cross-platform PortAudio access
- Records at 16kHz mono (Whisper's expected format)
- Supports both "record all then return" and "chunked streaming" modes
- Thread-safe recording with callback-based audio capture

### 3. `transcriber.py` — STT Engine Abstraction

Abstract interface for speech-to-text engines.

```python
class TranscriberEngine(Protocol):
    def transcribe(self, audio: numpy.ndarray) -> str
    def is_available(self) -> bool
    def get_name(self) -> str

class Transcriber:
    def __init__(self, engine: TranscriberEngine)
    def transcribe_full(self, audio: numpy.ndarray) -> str
    def transcribe_streaming(self, audio_stream: Iterator[numpy.ndarray]) -> Iterator[str]
```

### 4. `engines/local_mlx.py` — MLX Whisper Engine

Local transcription using MLX Whisper on Apple Silicon.

**Details:**
- Uses `mlx-whisper` package
- Model: `mlx-community/whisper-large-v3-turbo` (quantized for speed)
- Auto-downloads model on first use (~1.6 GB)
- Runs inference on Apple GPU/ANE via MLX

### 5. `engines/remote_openai.py` — OpenAI API Engine

Remote transcription via OpenAI's Whisper API.

**Details:**
- Uses `openai` Python SDK
- Supports `whisper-1` and `gpt-4o-mini-transcribe` models
- API key stored in config file
- Sends audio as WAV/FLAC to API endpoint

### 6. `hotkeys.py` — Global Hotkey Manager

Manages global keyboard shortcuts for push-to-talk and hands-free modes.

Uses NSEvent global monitors (AppKit) to detect all keyboard events including the
`fn` (globe) key. Only requires Accessibility permission — no Input Monitoring needed.

```python
class HotkeyManager:
    def __init__(self, push_to_talk_key="fn", hands_free_keys=["fn", "space"], ...)
    def start() -> None
    def stop() -> None
    def update_keys(push_to_talk_key=None, hands_free_keys=None) -> None
```

**Modes:**
- **Push-to-talk:** Hold `fn` → record → release → transcribe → inject text
- **Hands-free:** Press `fn+Space` → start recording → press again → stop → transcribe → inject text

### 7. `text_input.py` — Text Injection

Simulates keyboard input to type transcribed text into any focused field.

```python
class TextInjector:
    def type_text(self, text: str) -> None      # Character-by-character
    def paste_text(self, text: str) -> None      # Via clipboard (faster)
    def inject(self, text: str, method: str = "paste") -> None
```

**Methods:**
- **CGEvent keyboard simulation:** Types character-by-character via Quartz CGEventCreateKeyboardEvent
- **Clipboard paste:** Copies text to clipboard, simulates Cmd+V (faster for large text)
- Default: clipboard paste for bulk, keyboard sim for streaming chunks

### 8. `overlay.py` — Recording Indicator

Floating window near the dock showing recording state.

**UI States:**
- **Idle:** Hidden
- **Recording (push-to-talk):** Small pill showing "Recording..." with waveform animation
- **Recording (hands-free):** Pill showing "Listening..." with mic icon
- **Transcribing:** Pill showing "Transcribing..." with spinner

### 9. `config.py` — Settings Management

Persistent configuration stored in `~/.config/dev-talk/config.json`.

```python
@dataclass
class Config:
    engine: str = "local"                    # "local" or "openai"
    model: str = "mlx-community/whisper-large-v3-turbo"
    openai_api_key: str = ""
    openai_model: str = "whisper-1"
    push_to_talk_key: str = "fn"
    hands_free_keys: list[str] = ["space", "fn"]
    mic_device_id: int | None = None         # None = system default
    streaming_mode: bool = True              # True = chunked streaming
    chunk_duration_s: float = 3.0            # Seconds per streaming chunk
    language: str = "en"
```

---

## Transcription Modes

### Mode 1: Streaming (Chunked)

```
[User speaks] ──→ [3s chunk] ──→ [Transcribe] ──→ [Inject text]
                  [3s chunk] ──→ [Transcribe] ──→ [Inject text]
                  [3s chunk] ──→ [Transcribe] ──→ [Inject text]
                  ...
```

- Audio is split into configurable chunks (default 3s)
- Each chunk is transcribed independently
- Text is injected immediately after each chunk completes
- Gives "typing while speaking" experience
- May have slight accuracy loss at chunk boundaries

### Mode 2: Non-Streaming (Full Recording)

```
[User speaks] ──→ [Full audio buffer] ──→ [Transcribe all] ──→ [Inject text]
```

- All audio is recorded into a single buffer
- Transcription happens after recording stops
- More accurate (full context for the model)
- Higher latency (must wait for full recording + transcription)
- Better for short push-to-talk phrases

---

## Permissions Required

The app needs the following macOS permissions:

1. **Microphone Access** — for audio recording
2. **Accessibility** — for global hotkeys (NSEvent monitors) and text injection (CGEvent paste)

No Input Monitoring permission is needed. NSEvent global monitors only require Accessibility.

---

## Packaging

### Development
```bash
pip install -e ".[dev]"
python -m dev_talk
```

### Production (.app bundle)
```bash
python setup.py py2app
# Creates dist/Dev Talk.app
cp -r "dist/Dev Talk.app" /Applications/
```

The .app bundle includes:
- Python runtime
- All dependencies
- MLX Whisper model (or auto-downloads on first run)
- App icon and resources
