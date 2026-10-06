"""2.5: Lolalytics import parsing, spell ordering/jungle fallback, role lists."""
import json

from lolpicker.lolalytics import parse_page, order_spells, spells_for_role, to_loadout, build_page_url
from lolpicker.runes import RuneData
from lolpicker.selection import effective_lists, choose
from lolpicker.storage import clean_config


def qwik_page(pick_perks, sec, mods, spells, lane="middle"):
    # Qwik serializes objects into a flat list; references are base-36 indexes.
    objs = ["x", {"summary": "3", "header": "2"}, {"lane": lane}, {"pick": "4", "win": "4"},
            {"runes": "5", "sums": "6"}, {"set": "7", "n": 1234}, {"ids": spells},
            {"pri": pick_perks, "sec": sec, "mod": mods}]
    return '<html><script type="qwik/json">' + json.dumps({"objs": objs}) + '</script></html>'


def test_parse_page_extracts_runes_shards_and_spells():
    html = qwik_page([8112, 8139, 8140, 8106], [8226, 8210], [5005, 5008, 5001], [4, 14])
    build = parse_page(html)
    assert build["perks"] == [8112, 8139, 8140, 8106, 8226, 8210]
    assert build["shards"] == [5005, 5008, 5001] and build["spells"] == [4, 14] and build["lane"] == "middle" and build["games"] == 1234
    assert build_page_url("Kai'Sa", "bottom", "emerald_plus", "7") == "https://lolalytics.com/lol/kaisa/build/?tier=emerald_plus&patch=7&lane=bottom"


def test_to_loadout_derives_styles_and_flash_side(tmp_path):
    data = RuneData(tmp_path)
    data.apply([{"id": 8100, "name": "D", "icon": "d.png", "slots": [{"runes": [{"id": 8112, "name": "E", "icon": "e"}]}, {"runes": [{"id": 8139, "name": "a", "icon": "a"}]},
                                                                      {"runes": [{"id": 8140, "name": "b", "icon": "b"}]}, {"runes": [{"id": 8106, "name": "c", "icon": "c"}]}]},
                {"id": 8200, "name": "S", "icon": "s.png", "slots": [{"runes": []}, {"runes": [{"id": 8226, "name": "d", "icon": "d"}]}, {"runes": [{"id": 8210, "name": "e", "icon": "e"}]}, {"runes": []}]}],
               {"data": {}})
    build = {"perks": [8112, 8139, 8140, 8106, 8226, 8210], "shards": [5005, 5008, 5001], "spells": [4, 14]}
    assert to_loadout(build, data, "left")["spells"] == [4, 14]
    loadout = to_loadout(build, data, "right")
    assert loadout["primary"] == 8100 and loadout["sub"] == 8200 and loadout["spells"] == [14, 4]


def test_spell_ordering_and_jungle_fallback():
    assert order_spells([14, 4], "left") == [4, 14]
    assert order_spells([4, 14], "right") == [14, 4]
    assert order_spells([11, 6], "left") == [11, 6]
    loadout = {"spells": [4, 14]}
    assert spells_for_role(loadout, "jungle", "left") == [4, 11]
    assert spells_for_role(loadout, "jungle", "right") == [11, 4]
    assert spells_for_role({"spells": [4, 14], "jungle_spells": [6, 11]}, "JUNGLE", "left") == [6, 11]
    assert spells_for_role({"spells": [4, 11]}, "jungle", "right") == [11, 4]
    assert spells_for_role(loadout, "top", "left") == [4, 14]


def test_role_lists_storage_and_selection():
    cfg = clean_config({"auto_pick_champs": [266], "auto_ban_champs": [51], "flash_side": "right", "list_role": "jungle",
                        "lolalytics_import": {"enabled": False, "tier": "gold_plus", "patch": "16.18", "build": "win"},
                        "role_lists": {"jungle": {"auto_pick_champs": [64, "x"], "auto_ban_champs": []}, "top": {"auto_pick_champs": []}, "mid": {"auto_pick_champs": [1]}}})
    assert cfg["flash_side"] == "right" and cfg["list_role"] == "jungle"
    assert cfg["lolalytics_import"] == {"enabled": False, "tier": "gold_plus", "patch": "16.18", "build": "win"}
    assert cfg["role_lists"] == {"jungle": {"auto_pick_champs": [64], "auto_ban_champs": []}}
    assert effective_lists(cfg, "jungle") == {"auto_pick_champs": [64], "auto_ban_champs": [51]}
    # 2.6: assigned top without a top list -> the list selected in the overlay (jungle) stays in use, not 'Alle Rollen'
    assert effective_lists(cfg, "top") == {"auto_pick_champs": [64], "auto_ban_champs": [51]}
    assert effective_lists(cfg, "") == {"auto_pick_champs": [64], "auto_ban_champs": [51]}
    assert effective_lists({**cfg, "list_role": ""}, "top") == {"auto_pick_champs": [266], "auto_ban_champs": [51]}
    cfg_top = clean_config({**cfg, "role_lists": {**cfg["role_lists"], "top": {"auto_pick_champs": [98], "auto_ban_champs": []}}})
    assert effective_lists(cfg_top, "top") == {"auto_pick_champs": [98], "auto_ban_champs": [51]}  # own top list wins
    session = {"localPlayerCellId": 1, "myTeam": [{"cellId": 1, "assignedPosition": "jungle"}], "theirTeam": [], "actions": [], "bans": {}}
    assert choose(session, cfg, "pick") == 64
    session["myTeam"][0]["assignedPosition"] = "top"
    assert choose(session, cfg, "pick") == 64
    assert choose(session, cfg_top, "pick") == 98
    assert clean_config({"lolalytics_import": {"patch": "abc", "tier": "nope"}})["lolalytics_import"] == {"enabled": False, "tier": "all", "patch": "30", "build": "pick"}
    # migration: settings written by 2.5 (schema 2) had the import ON by default -> now OFF; explicit newer files keep their value
    assert clean_config({"schema": 2, "lolalytics_import": {"enabled": True}})["lolalytics_import"]["enabled"] is False
    assert clean_config({"schema": 3, "lolalytics_import": {"enabled": True}})["lolalytics_import"]["enabled"] is True
    assert clean_config({"close_scope": "browser"})["close_scope"] == "browser" and clean_config({"close_scope": "x"})["close_scope"] == "lolalytics"


def test_champion_specific_import_settings():
    from lolpicker.lolalytics import import_settings, patch_options
    base = {"primary": 8000, "sub": 8100, "perks": [1, 2, 3, 4, 5, 6], "shards": [1, 2, 3], "spells": [4, 14]}
    cfg = clean_config({"loadouts": {"266": {**base, "lolalytics": {"build": "win", "tier": "nope", "patch": "7", "enabled": True}}}})
    assert cfg["loadouts"]["266"]["lolalytics"] == {"build": "win", "patch": "7"}
    assert "lolalytics" not in clean_config({"loadouts": {"266": {**base, "lolalytics": {}}}})["loadouts"]["266"]
    glob = {"enabled": False, "tier": "gold_plus", "patch": "30", "build": "pick"}
    assert import_settings(glob, cfg["loadouts"]["266"]) == {"enabled": False, "tier": "gold_plus", "patch": "7", "build": "win"}
    assert import_settings(glob, None) == glob
    assert patch_options("16.19.1")[:4] == [("7", "7 Tage"), ("14", "14 Tage"), ("30", "30 Tage"), ("16.19", "Patch 16.19")]
    assert patch_options("") == [("7", "7 Tage"), ("14", "14 Tage"), ("30", "30 Tage")]
