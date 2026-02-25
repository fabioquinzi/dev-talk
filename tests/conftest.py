"""Shared test fixtures."""

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary directory for config files."""
    config_dir = tmp_path / "dev-talk"
    config_dir.mkdir()
    return config_dir
