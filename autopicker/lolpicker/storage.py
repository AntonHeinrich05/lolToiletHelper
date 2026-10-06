"""Atomic, per-user settings. Network workers only consume snapshots."""
import copy
import json
import logging
import os
import re
from pathlib import Path
import tempfile
import threading

DEFAULT_HOTKEYS = {
    "toggle_overlay": "<alt>+q",
    "open_lolalytics": "<alt>+<shift>+1",
    "open_vs": "<alt>+<shift>+2",
    "close_tab": "<alt>+<shift>+3",
    "close_all_browsers": "<alt>+<shift>+4",
}
DEFAULTS = {
    "schema": 4, "auto_ready_enabled": True, "auto_pick_enabled": False,
    "auto_pick_champs": [], "auto_ban_champs": [], "bad_matchups": {}, "auto_pick_minimized": True,
    "hotkeys": DEFAULT_HOTKEYS, "live_tracking": True,
    "weak_pc_mode": False, "debug_mode": False, "preferred_browser": "",
    "lockfile_path": "", "live_api_port": 2999,
    "opacity_default": 0.75, "opacity_ingame": 0.5, "loadouts": {},
    "flash_side": "left", "lolalytics_import": {"enabled": False, "tier": "all", "patch": "30", "build": "pick"},
    "role_lists": {}, "list_role": "", "close_scope": "lolalytics", "show_rates": True,
}
OPACITY_MIN, OPACITY_MAX = 0.2, 1.0
ROLES = ("top", "jungle", "middle", "bottom", "support")
ROLE_LABELS = {"": "Alle Rollen", "top": "Top", "jungle": "Jungle", "middle": "Mid", "bottom": "Bot", "support": "Support"}
CLOSE_SCOPES = {"lolalytics": "Nur Lolalytics-Tabs", "browser": "Ganze Browser (alle Tabs)"}


def clean_champ_list(value):
    return list(dict.fromkeys(x for x in value if type(x) is int and x > 0))[:30] if isinstance(value, list) else []


def clean_loadout(value):
    """One champion loadout: primary/sub style, 6 perk ids (4 primary, 2 sub), 3 shards, 2 spells."""
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("primary", "sub"):
        if type(value.get(key)) is not int or value[key] <= 0:
            return None
        result[key] = value[key]
    for key, length in (("perks", 6), ("shards", 3), ("spells", 2)):
        items = value.get(key)
        if not isinstance(items, list) or len(items) != length or any(type(x) is not int or x <= 0 for x in items):
            return None
        result[key] = list(items)
    jungle = value.get("jungle_spells")
    if isinstance(jungle, list) and len(jungle) == 2 and all(type(x) is int and x > 0 for x in jungle):
        result["jungle_spells"] = list(jungle)
    own = clean_import_settings(value.get("lolalytics"), {})
    if own:
        result["lolalytics"] = own  # champion-specific Lolalytics rank/patch/build (only the keys that differ from the defaults)
    return result


def clean_import_settings(value, defaults):
    """Validated Lolalytics import settings on top of `defaults`; unknown values keep the default."""
    result = dict(defaults)
    if not isinstance(value, dict):
        return result
    from .lolalytics import TIERS, BUILDS
    if isinstance(value.get("enabled"), bool) and "enabled" in defaults:
        result["enabled"] = value["enabled"]
    if value.get("tier") in TIERS:
        result["tier"] = value["tier"]
    if isinstance(value.get("patch"), str) and re.fullmatch(r"\d{1,2}(\.\d{1,2})?", value["patch"]):
        result["patch"] = value["patch"]
    if value.get("build") in BUILDS:
        result["build"] = value["build"]
    return result


def data_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "LoLAutopicker"


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8-sig") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else copy.deepcopy(default)
    except (OSError, ValueError):
        return copy.deepcopy(default)


def clean_config(value):
    result = copy.deepcopy(DEFAULTS)
    for key in ("auto_ready_enabled", "auto_pick_enabled", "auto_pick_minimized", "live_tracking", "weak_pc_mode", "debug_mode", "show_rates"):
        if isinstance(value.get(key), bool):
            result[key] = value[key]
    for key in ("auto_pick_champs", "auto_ban_champs"):
        if isinstance(value.get(key), list):
            result[key] = list(dict.fromkeys(x for x in value[key] if type(x) is int and x > 0))[:30]
    if isinstance(value.get("bad_matchups"), dict):
        result["bad_matchups"] = {
            str(k): list(dict.fromkeys(x for x in v if type(x) is int and x > 0))[:6]
            for k, v in value["bad_matchups"].items() if str(k).isdigit() and isinstance(v, list)
        }
    for key in ("preferred_browser", "lockfile_path"):
        if isinstance(value.get(key), str):
            result[key] = value[key]
    if type(value.get("live_api_port")) is int and 1 <= value["live_api_port"] <= 65535:
        result["live_api_port"] = value["live_api_port"]
    for key in ("opacity_default", "opacity_ingame"):
        number = value.get(key)
        if isinstance(number, (int, float)) and not isinstance(number, bool) and OPACITY_MIN <= number <= OPACITY_MAX:
            result[key] = round(float(number), 2)
    if value.get("flash_side") in ("left", "right"):
        result["flash_side"] = value["flash_side"]
    if value.get("close_scope") in CLOSE_SCOPES:
        result["close_scope"] = value["close_scope"]
    result["lolalytics_import"] = clean_import_settings(value.get("lolalytics_import"), result["lolalytics_import"])
    schema = value.get("schema")
    if isinstance(schema, int) and schema < 3:
        result["lolalytics_import"]["enabled"] = False  # 2.6: Lolalytics runes without own choice are OFF by default
    if isinstance(schema, int) and schema < 4 and result["lolalytics_import"]["patch"] == "7":
        result["lolalytics_import"]["patch"] = "30"  # 2.7: All Ranks + 30 days are the standard, not the 7-day Lolalytics default
    if isinstance(value.get("role_lists"), dict):
        for role in ROLES:
            lists = value["role_lists"].get(role)
            if isinstance(lists, dict):
                cleaned = {"auto_pick_champs": clean_champ_list(lists.get("auto_pick_champs")),
                           "auto_ban_champs": clean_champ_list(lists.get("auto_ban_champs"))}
                if cleaned["auto_pick_champs"] or cleaned["auto_ban_champs"]:
                    result["role_lists"][role] = cleaned
    if value.get("list_role") in ROLES:
        result["list_role"] = value["list_role"]
    if isinstance(value.get("loadouts"), dict):
        result["loadouts"] = {}
        for key, loadout in value["loadouts"].items():
            cleaned = clean_loadout(loadout)
            if str(key).isdigit() and cleaned:
                result["loadouts"][str(key)] = cleaned
    from .hotkeys import parse_combo
    used = set()
    saved = value.get("hotkeys", {})
    if not isinstance(saved, dict):
        saved = {}
    for action, default in DEFAULT_HOTKEYS.items():
        combo = saved.get(action, default)
        # Recover the known Shift+1 recording bug from the old application.
        if isinstance(combo, str):
            combo = combo.replace("+exclam", "+1").replace("+!", "+1")
        try:
            parsed = parse_combo(combo)
            if parsed in used:
                raise ValueError("duplicate")
            result["hotkeys"][action] = combo
            used.add(parsed)
        except (ValueError, TypeError):
            # Disable conflicts, do not claim that an unregistered key is active.
            result["hotkeys"][action] = ""
    return result


class Settings:
    def __init__(self, directory=None, legacy_dir=None):
        self.path = Path(directory or data_dir()) / "settings.json"
        self.lock = threading.RLock()
        self.last_error = ""
        source = self.path
        if not source.exists() and legacy_dir:
            source = Path(legacy_dir) / "lolhelper_config.json"
        self.value = clean_config(read_json(source, {}))

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.value)

    def update(self, **changes):
        with self.lock:
            candidate = clean_config({**self.value, **changes})
            try:
                atomic_json(self.path, candidate)
            except OSError:
                self.last_error = "Einstellungen konnten nicht gespeichert werden. Speicherort prüfen."
                logging.getLogger(__name__).error(self.last_error)
                return False
            self.value = candidate
            self.last_error = ""
            return True