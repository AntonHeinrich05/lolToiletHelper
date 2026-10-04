"""Regression tests for storage migration, hotkeys, URL handling and selection decisions."""
import json
from pathlib import Path
import threading
import time
import types

import pytest

from lolpicker import hotkeys
from lolpicker.hotkeys import parse_combo, combo_from_event, Hotkeys
from lolpicker.selection import active_action, available, choose, draft_opponent, live_matchup
from lolpicker.storage import Settings, clean_config
from lolpicker.urls import UrlStore, build_url, canonical


# storage.py: migration, atomic persistence and save-failure handling
def test_clean_config_migrates_shift_exclam_and_disables_duplicate():
    cfg = clean_config({
        "hotkeys": {
            "toggle_overlay": "<alt>+q",
            "open_lolalytics": "<alt>+<shift>+!",
            "open_vs": "<alt>+<shift>+1",
            "close_tab": "<alt>+<shift>+2",
            "close_all_browsers": "<alt>+<shift>+3",
        }
    })
    assert cfg["hotkeys"]["open_lolalytics"] == "<alt>+<shift>+1"
    assert cfg["hotkeys"]["open_vs"] == ""


def test_settings_update_persists_to_file(data_directory):
    settings = Settings(directory=data_directory)
    ok = settings.update(auto_pick_champs=[266, 266, 51], bad_matchups={"266": [51, 51]})
    assert ok is True
    raw = json.loads((data_directory / "settings.json").read_text(encoding="utf-8"))
    assert raw["auto_pick_champs"] == [266, 51]
    assert raw["bad_matchups"]["266"] == [51]


def test_settings_update_failed_save_sets_error(data_directory, monkeypatch):
    settings = Settings(directory=data_directory)

    def failing_atomic_json(*_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("lolpicker.storage.atomic_json", failing_atomic_json)
    ok = settings.update(auto_ready_enabled=False)
    assert ok is False
    assert "gespeichert" in settings.last_error.lower()


# hotkeys.py: parser and rebinding rollback behaviour
def test_parse_combo_accepts_alt_shift_number_keycode_semantics():
    mods, vk = parse_combo("<alt>+<shift>+1")
    assert mods == (1 | 4)
    assert vk == 49


def test_combo_from_event_converts_exclam_to_1_on_non_windows():
    event = types.SimpleNamespace(keycode=None, keysym="exclam", state=1)
    combo = combo_from_event(event, windows=False)
    assert combo == "<shift>+1"


class _FakeRoot:
    def after(self, *_args, **_kwargs):
        return None


class _FakeUser32:
    class _Fn:
        def __init__(self, owner, name):
            self.owner = owner
            self.name = name
            self.argtypes = None

        def __call__(self, *args):
            return self.owner._call(self.name, *args)

    def __init__(self):
        self.registrations = {}
        self.fail_vk = None
        self.RegisterHotKey = self._Fn(self, "RegisterHotKey")
        self.UnregisterHotKey = self._Fn(self, "UnregisterHotKey")
        self.PeekMessageW = self._Fn(self, "PeekMessageW")

    def _call(self, name, *args):
        if name == "RegisterHotKey":
            _hwnd, identifier, _mods, vk = args
            if self.fail_vk is not None and vk == self.fail_vk:
                return 0
            self.registrations[identifier] = vk
            return 1
        if name == "UnregisterHotKey":
            _hwnd, identifier = args
            self.registrations.pop(identifier, None)
            return 1
        if name == "PeekMessageW":
            return 0
        return 0


class _ThreadAffineUser32:
    """Simulated Win32 API: Register/Unregister/Peek must run on one worker thread."""

    class _Fn:
        def __init__(self, owner, name):
            self.owner = owner
            self.name = name
            self.argtypes = None

        def __call__(self, *args):
            return self.owner._call(self.name, *args)

    def __init__(self):
        self.owner_thread = None
        self.thread_calls = []
        self.registrations = {}
        self.messages = []
        self.unregister_calls = 0
        self.RegisterHotKey = self._Fn(self, "RegisterHotKey")
        self.UnregisterHotKey = self._Fn(self, "UnregisterHotKey")
        self.PeekMessageW = self._Fn(self, "PeekMessageW")

    def _mark(self, name):
        tid = threading.get_ident()
        self.thread_calls.append((name, tid))
        if self.owner_thread is None:
            self.owner_thread = tid
        elif tid != self.owner_thread:
            raise AssertionError(f"{name} called from non-owner thread")

    def queue_hotkey(self, identifier):
        self.messages.append(identifier)

    def _call(self, name, *args):
        self._mark(name)
        if name == "RegisterHotKey":
            _hwnd, identifier, _mods, vk = args
            self.registrations[identifier] = vk
            return 1
        if name == "UnregisterHotKey":
            _hwnd, identifier = args
            self.unregister_calls += 1
            self.registrations.pop(identifier, None)
            return 1
        if name == "PeekMessageW":
            msg_ptr, _hwnd, _min_msg, _max_msg, remove = args
            if remove == 1 and self.messages:
                msg_ptr._obj.wParam = self.messages.pop(0)
                return 1
            return 0
        return 0


def test_hotkeys_apply_rolls_back_to_previous_bindings(monkeypatch):
    fake = _FakeUser32()
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr(hotkeys.ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)

    hk = Hotkeys(_FakeRoot(), lambda _action: None)
    old = {"toggle_overlay": "<alt>+q", "open_lolalytics": "<alt>+<shift>+1"}
    hk.apply(old)
    fake.fail_vk = ord("R")

    with pytest.raises(ValueError):
        hk.apply({"toggle_overlay": "<alt>+r", "open_lolalytics": "<alt>+<shift>+1"})

    assert hk.bindings == old
    assert set(hk.ids.values()) == set(old.keys())


def test_hotkeys_rebind_replaces_old_combo(monkeypatch):
    fake = _FakeUser32()
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr(hotkeys.ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)
    hk = Hotkeys(_FakeRoot(), lambda _action: None)
    hk.apply({"toggle_overlay": "<alt>+q"})
    hk.apply({"toggle_overlay": "<alt>+w"})
    assert hk.bindings["toggle_overlay"] == "<alt>+w"
    assert list(fake.registrations.values()) == [ord("W")]


def test_hotkeys_worker_thread_affinity_and_poll_dispatch(monkeypatch):
    fake = _ThreadAffineUser32()
    callback_actions = []
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr(hotkeys.ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)

    hk = Hotkeys(_FakeRoot(), callback_actions.append)
    try:
        hk.apply({"toggle_overlay": "<alt>+q"})
        fake.queue_hotkey(1)
        time.sleep(0.05)

        # callback must be marshalled through poll(), not directly from worker thread
        assert callback_actions == []
        hk.poll()
        assert callback_actions == ["toggle_overlay"]

        # all Win32 API calls stayed on one owning worker thread
        tids = {tid for _name, tid in fake.thread_calls}
        assert len(tids) == 1
    finally:
        hk.close()


def test_hotkeys_rebind_drops_old_generation_events_and_clears_old_registration(monkeypatch):
    fake = _ThreadAffineUser32()
    callback_actions = []
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr(hotkeys.ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)

    hk = Hotkeys(_FakeRoot(), callback_actions.append)
    try:
        hk.apply({"toggle_overlay": "<alt>+q"})
        fake.queue_hotkey(1)
        hk.apply({"open_vs": "<alt>+w"})
        time.sleep(0.06)
        hk.poll()

        assert "toggle_overlay" not in callback_actions
        assert list(fake.registrations.values()) == [ord("W")]
    finally:
        hk.close()


def test_hotkeys_close_unregs_native_and_stops_worker(monkeypatch):
    fake = _ThreadAffineUser32()
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr(hotkeys.ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)

    hk = Hotkeys(_FakeRoot(), lambda _action: None)
    hk.apply({"toggle_overlay": "<alt>+q", "open_lolalytics": "<alt>+<shift>+1"})
    hk.close()

    assert hk.closed is True
    assert hk.ids == {}
    assert fake.registrations == {}
    assert fake.unregister_calls >= 2


# urls.py: canonicalization, same-champion persistence, corrected VS
def test_url_canonicalization_sorts_query_and_rejects_host_abuse():
    a = canonical("http://www.lolalytics.com/lol/aatrox/build/?b=2&a=1")
    b = canonical("https://lolalytics.com/lol/aatrox/build/?a=1&b=2")
    assert a == b
    with pytest.raises(ValueError):
        canonical("https://evil.com/lol/aatrox/build/")
    with pytest.raises(ValueError):
        canonical("https://user:pw@lolalytics.com/lol/aatrox/build/")
    with pytest.raises(ValueError):
        canonical("https://lolalytics.com/not-lol/aatrox/")


def test_url_store_persists_same_champion_and_isolates_other_champions(tmp_path):
    store = UrlStore(tmp_path / "urls.json")
    base = "https://lolalytics.com/lol/aatrox/build/?tier=all&item=1_6692"
    vs = "https://lolalytics.com/lol/aatrox/vs/caitlyn/build/?tier=all&vslane=bottom"
    assert store.remember(base, expected_champion="aatrox", kind="base") is True
    assert store.remember(vs, expected_champion="aatrox", kind="vs") is True
    assert store.remember("https://lolalytics.com/lol/caitlyn/build/?tier=all", expected_champion="aatrox", kind="base") is False

    fresh_base = "https://lolalytics.com/lol/aatrox/build/?tier=all"
    fresh_vs = "https://lolalytics.com/lol/aatrox/vs/caitlyn/build/?tier=all&vslane=middle"
    assert "item=1_6692" in store.restore(fresh_base, kind="base")
    assert "vslane=bottom" in store.restore(fresh_vs, kind="vs")


def test_corrected_vs_preserves_item_filters_and_overrides_lanes(tmp_path):
    store = UrlStore(tmp_path / "urls.json")
    old = "https://lolalytics.com/lol/aatrox/vs/caitlyn/build/?tier=all&item=1_6692&vslane=bottom&lane=top"
    fresh = "https://lolalytics.com/lol/aatrox/vs/kennen/build/?tier=all&lane=middle&vslane=middle"
    corrected = store.corrected_vs(old, fresh)
    assert "/vs/kennen/" in corrected
    assert "item=1_6692" in corrected
    assert "lane=middle" in corrected and "vslane=middle" in corrected


def test_build_url_contains_vslane_for_standard_queue():
    url = build_url("Aatrox", role="top", queue_id=420, opponent="Caitlyn", opponent_role="bottom")
    assert "lane=top" in url
    assert "vslane=bottom" in url


# selection.py: own active actions only and safe fallback decisions
def test_selection_active_action_and_available_logic():
    session = {
        "localPlayerCellId": 1,
        "myTeam": [{"cellId": 1, "championPickIntent": 51}, {"cellId": 2, "championId": 266}],
        "theirTeam": [{"cellId": 6, "championId": 222, "assignedPosition": "BOTTOM"}],
        "actions": [[
            {"id": 10, "type": "pick", "actorCellId": 2, "isInProgress": True, "completed": False},
            {"id": 11, "type": "pick", "actorCellId": 1, "isInProgress": True, "completed": False},
        ]],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "pickableChampionIds": [266, 51],
        "bannableChampionIds": [51, 222],
    }
    assert active_action(session)["id"] == 11
    assert available(session, 51, "ban") is False


def test_choose_uses_bad_matchup_fallback_and_allowed_list():
    session = {
        "localPlayerCellId": 1,
        "myTeam": [{"cellId": 1, "assignedPosition": "TOP", "championId": 0}],
        "theirTeam": [{"cellId": 6, "assignedPosition": "BOTTOM", "championId": 222}],
        "actions": [[]],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "pickableChampionIds": [266, 51],
    }
    options = {"auto_pick_champs": [266, 51], "bad_matchups": {"266": [222], "51": [222]}}
    assert choose(session, options, "pick") == 266


def test_draft_and_live_matchup_safe_resolution():
    session = {
        "localPlayerCellId": 1,
        "myTeam": [{"cellId": 1, "assignedPosition": "TOP"}],
        "theirTeam": [{"cellId": 6, "assignedPosition": "TOP", "championId": 222}],
        "actions": [[]],
    }
    assert draft_opponent(session)["champion_id"] == 222

    uncertain = {
        "activePlayer": {"summonerName": "Me"},
        "allPlayers": [
            {"summonerName": "Me", "team": "ORDER", "position": "TOP", "championName": "Aatrox"},
            {"summonerName": "Enemy1", "team": "CHAOS", "position": "TOP", "championName": "Garen"},
            {"summonerName": "Enemy2", "team": "CHAOS", "position": "TOP", "championName": "Darius"},
        ],
    }
    assert live_matchup(uncertain) is None
