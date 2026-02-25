"""Tests for config module."""

import json

from dev_talk.config import Config


def test_default_config():
    cfg = Config()
    assert cfg.engine == "local"
    assert cfg.model == "mlx-community/whisper-large-v3-turbo"
    assert cfg.language == "en"
    assert cfg.streaming_mode is True
    assert cfg.chunk_duration_s == 3.0
    assert cfg.push_to_talk_key == "fn"
    assert cfg.hands_free_keys == ["fn", "space"]
    assert cfg.mic_device_id is None
    assert cfg.injection_method == "paste"


def test_save_and_load(tmp_config_dir):
    path = tmp_config_dir / "config.json"

    cfg = Config(engine="openai", openai_api_key="sk-test123")
    cfg.save(path)

    loaded = Config.load(path)
    assert loaded.engine == "openai"
    assert loaded.openai_api_key == "sk-test123"
    # Defaults should still be present
    assert loaded.model == "mlx-community/whisper-large-v3-turbo"


def test_load_missing_file(tmp_config_dir):
    path = tmp_config_dir / "nonexistent.json"
    cfg = Config.load(path)
    assert cfg.engine == "local"  # Falls back to defaults


def test_load_corrupted_file(tmp_config_dir):
    path = tmp_config_dir / "config.json"
    path.write_text("not valid json {{{")

    cfg = Config.load(path)
    assert cfg.engine == "local"  # Falls back to defaults


def test_load_ignores_unknown_keys(tmp_config_dir):
    path = tmp_config_dir / "config.json"
    path.write_text(json.dumps({"engine": "openai", "unknown_key": "value"}))

    cfg = Config.load(path)
    assert cfg.engine == "openai"
    assert not hasattr(cfg, "unknown_key")


def test_load_partial_config(tmp_config_dir):
    path = tmp_config_dir / "config.json"
    path.write_text(json.dumps({"engine": "openai"}))

    cfg = Config.load(path)
    assert cfg.engine == "openai"
    assert cfg.model == "mlx-community/whisper-large-v3-turbo"  # Default preserved


def test_update(tmp_config_dir):
    path = tmp_config_dir / "config.json"
    cfg = Config()
    cfg.save(path)

    cfg.update(engine="openai", streaming_mode=False)
    assert cfg.engine == "openai"
    assert cfg.streaming_mode is False


def test_update_ignores_invalid_keys(tmp_config_dir):
    cfg = Config()
    cfg.update(nonexistent_field="value")
    assert not hasattr(cfg, "nonexistent_field")


def test_roundtrip_all_fields(tmp_config_dir):
    path = tmp_config_dir / "config.json"
    cfg = Config(
        engine="openai",
        model="custom-model",
        language="en",
        openai_api_key="sk-abc",
        openai_model="gpt-4o-mini-transcribe",
        push_to_talk_key="right_ctrl",
        hands_free_keys=["ctrl", "shift"],
        mic_device_id=3,
        mic_device_name="HyperX SoloCast",
        streaming_mode=False,
        chunk_duration_s=5.0,
        injection_method="type",
    )
    cfg.save(path)

    loaded = Config.load(path)
    assert loaded.engine == "openai"
    assert loaded.model == "custom-model"
    assert loaded.openai_api_key == "sk-abc"
    assert loaded.openai_model == "gpt-4o-mini-transcribe"
    assert loaded.push_to_talk_key == "right_ctrl"
    assert loaded.hands_free_keys == ["ctrl", "shift"]
    assert loaded.mic_device_id == 3
    assert loaded.mic_device_name == "HyperX SoloCast"
    assert loaded.streaming_mode is False
    assert loaded.chunk_duration_s == 5.0
    assert loaded.injection_method == "type"
