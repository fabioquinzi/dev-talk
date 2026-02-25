"""Settings management with JSON persistence.

Config is stored at ~/.config/dev-talk/config.json.
All fields have sensible defaults so the app works out of the box.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "dev-talk"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    # STT engine: "local" or "openai"
    engine: str = "local"

    # Local engine settings
    model: str = "mlx-community/whisper-large-v3-turbo"
    language: str = "en"

    # OpenAI API settings
    openai_api_key: str = ""
    openai_model: str = "whisper-1"

    # Hotkeys
    push_to_talk_key: str = "fn"
    hands_free_keys: list[str] = field(default_factory=lambda: ["fn", "space"])

    # Microphone (None = system default)
    mic_device_id: int | None = None
    mic_device_name: str = ""

    # Transcription mode
    streaming_mode: bool = True
    chunk_duration_s: float = 3.0

    # Text injection method: "paste" or "type"
    injection_method: str = "paste"

    def save(self, path: Path | None = None) -> None:
        """Persist config to disk."""
        target = path or CONFIG_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from disk, falling back to defaults for missing keys."""
        target = path or CONFIG_FILE
        if not target.exists():
            return cls()
        try:
            data = json.loads(target.read_text())
            # Only use keys that are valid Config fields
            valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return cls(**filtered)
        except (json.JSONDecodeError, TypeError):
            return cls()

    def update(self, **kwargs: object) -> None:
        """Update fields and persist."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
