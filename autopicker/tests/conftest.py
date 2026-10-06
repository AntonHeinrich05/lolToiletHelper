"""Shared fixtures for desktop logic, bridge and UI regression tests."""
from pathlib import Path
import pytest


@pytest.fixture
def bundle_dir() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def localappdata(tmp_path, monkeypatch) -> Path:
    base = tmp_path / "localapp"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(base))
    return base


@pytest.fixture
def data_directory(localappdata) -> Path:
    path = localappdata / "LoLAutopicker"
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeSettings:
    """Simple mutable settings snapshot for async worker unit tests."""

    def __init__(self, value):
        self.value = dict(value)

    def snapshot(self):
        return dict(self.value)


@pytest.fixture
def fake_settings():
    return FakeSettings({
        "auto_ready_enabled": True,
        "auto_pick_enabled": True,
        "auto_pick_champs": [266],
        "auto_ban_champs": [51],
        "bad_matchups": {},
        "lockfile_path": "",
    })
