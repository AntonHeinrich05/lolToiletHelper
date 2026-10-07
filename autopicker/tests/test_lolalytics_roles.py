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


def test_counters_and_tierlist_parsing_and_patch_defaults():
    from lolpicker.lolalytics import parse_counters, parse_tierlist
    from lolpicker.urls import build_url, with_default_patch
    objs = ["x", {"summary": "3", "header": "2", "enemy": "4"}, {"lane": "jungle"}, {},
            {"jungle": [[33, 43.9, 0, 0, 1.7, 36070], [14, 45.8, 0, 0, 0.1, 300], [19, 46.4, 0, 0, 3.7, 78601]], "top": []}]
    html = '<html><script type="qwik/json">' + json.dumps({"objs": objs}) + '</script></html>'
    result = parse_counters(html)
    assert result["lane"] == "jungle"
    assert [r["champion_id"] for r in result["counters"]] == [33, 14, 19]  # too few rows for the games filter -> all kept, worst first
    assert result["counters"][0] == {"champion_id": 33, "winrate": 43.9, "pickrate": 1.7, "games": 36070}
    tier = ["x", {"cid": "2", "row": "3", "placeholder": "4"}, 11, {"lane": "jungle", "br": 19.8, "pr": 9.7, "wr": 50.5, "games": 2000}, False,
            {"cid": 5, "row": "6"}, {"lane": "top", "br": 30.0, "pr": 1, "wr": 50, "games": 10},
            {"cid": 7, "row": "8", "placeholder": "9"}, {"lane": "jungle", "br": 5.0, "pr": 1, "wr": 50, "games": 10}, True]
    html = '<html><script type="qwik/json">' + json.dumps({"objs": tier}) + '</script></html>'
    assert [r["champion_id"] for r in parse_tierlist(html, "jungle")] == [11]  # other lane and placeholders are dropped
    assert [r["champion_id"] for r in parse_tierlist(html)] == [5, 11]  # all lanes: highest ban rate first
    assert "patch=30" in build_url("Viego", "jungle", 420)
    assert with_default_patch("https://lolalytics.com/lol/viego/build/?tier=all&item=1_1") == "https://lolalytics.com/lol/viego/build/?item=1_1&patch=30&tier=all"
    assert with_default_patch("https://lolalytics.com/lol/viego/build/?patch=7&tier=all") == "https://lolalytics.com/lol/viego/build/?patch=7&tier=all"
    assert clean_config({"schema": 3, "lolalytics_import": {"patch": "7"}})["lolalytics_import"]["patch"] == "30"
    assert clean_config({"schema": 4, "lolalytics_import": {"patch": "7"}})["lolalytics_import"]["patch"] == "7"


def test_rune_page_preview_text():
    from lolpicker.lolalytics import preview_text
    html = qwik_page([8112, 8139, 8140, 8106], [8226, 8210], [5005, 5008, 5001], [4, 14])
    build = parse_page(html)
    assert build["winrate"] == 0.0 and build["games"] == 1234  # old fixture without 'wr'
    text = preview_text({**build, "winrate": 49.08, "games": 1172656}, {"tier": "all", "patch": "30", "build": "pick"})
    assert text == "Lolalytics: 49.1 % WR · 1.172.656 Spiele · Most Common, All Ranks, 30 Tage"
    assert preview_text({"winrate": 51.26, "games": 900}, {"tier": "gold_plus", "patch": "16.19", "build": "win"}).endswith("Highest Win, Gold+, Patch 16.19")
    assert build["items"] == {}  # fixture without items


# 2.8: tier-list sort (win rate / ban rate / pick rate), suggestion settings, item parsing, import flag, updater helpers
def test_tierlist_sort_suggestion_settings_items_and_updater(tmp_path):
    from lolpicker.lolalytics import sort_tierlist, parse_items, item_ids, format_games, BAN_SORTS
    from lolpicker import updater
    rows = [{"champion_id": 1, "banrate": 5.0, "pickrate": 9.0, "winrate": 53.0, "games": 50},
            {"champion_id": 2, "banrate": 20.0, "pickrate": 3.0, "winrate": 48.0, "games": 5000},
            {"champion_id": 3, "banrate": 1.0, "pickrate": 7.0, "winrate": 52.0, "games": 8000}]
    assert [r["champion_id"] for r in sort_tierlist(rows, "banrate")] == [2, 1, 3]
    assert [r["champion_id"] for r in sort_tierlist(rows, "pickrate")] == [1, 3, 2]
    assert [r["champion_id"] for r in sort_tierlist(rows, "winrate")] == [1, 3, 2]  # only 2 solid rows -> games filter not applied
    many = rows + [{"champion_id": i, "banrate": 0, "pickrate": 0, "winrate": 50.0, "games": 3000} for i in range(10, 14)]
    assert 1 not in [r["champion_id"] for r in sort_tierlist(many, "winrate")]  # 50 games are dropped once enough data remains
    assert set(BAN_SORTS) == {"winrate", "banrate", "pickrate"}
    cfg = clean_config({})
    assert cfg["ban_suggest"] == {"sort": "winrate", "tier": "all", "patch": "30"} and cfg["counter_suggest"] == {"tier": "all", "patch": "30"}
    assert cfg["show_item_rates"] is False and "show_rates" not in cfg
    cfg = clean_config({"ban_suggest": {"sort": "pickrate", "tier": "gold_plus", "patch": "x"}, "counter_suggest": {"tier": "nope", "patch": "7"}, "show_item_rates": True})
    assert cfg["ban_suggest"] == {"sort": "pickrate", "tier": "gold_plus", "patch": "30"} and cfg["counter_suggest"] == {"tier": "all", "patch": "7"}
    assert cfg["show_item_rates"] is True and clean_config({"ban_suggest": {"sort": "x"}})["ban_suggest"]["sort"] == "winrate"
    items = parse_items({"start": {"n": 597033, "wr": 48.75, "set": [1102, 2003], "setUnique": [1102, 2003], "count": [1, 2]},
                         "core": {"set": [6672, 3047, 6676], "wr": 49.55, "n": 283996},
                         "item4": [{"id": 6673, "n": 569991, "wr": 54.65}, {"id": 3036, "n": 509411, "wr": 55.76}], "item5": [], "item6": "x"})
    assert items["start"] == {"ids": [1102, 2003], "count": [1, 2], "winrate": 48.75, "games": 597033}
    assert items["core"]["ids"] == [6672, 3047, 6676] and items["core"]["count"] == [1, 1, 1]
    assert items["item4"] == [{"id": 6673, "winrate": 54.65, "games": 569991}, {"id": 3036, "winrate": 55.76, "games": 509411}]
    assert "item5" not in items and "item6" not in items
    assert item_ids(items) == [1102, 2003, 6672, 3047, 6676, 6673, 3036]
    assert format_games(1182574) == "1.2 Mio." and format_games(56414) == "56 Tsd." and format_games(900) == "900"
    base = {"primary": 8000, "sub": 8100, "perks": [1, 2, 3, 4, 5, 6], "shards": [1, 2, 3], "spells": [4, 14]}
    loadouts = clean_config({"loadouts": {"1": {**base, "imported": True}, "2": {**base, "imported": "yes"}}})["loadouts"]
    assert loadouts["1"]["imported"] is True and "imported" not in loadouts["2"]
    assert updater.installed(tmp_path) == {} and updater.describe({}).startswith("Installierte Version: unbekannt")
    (tmp_path / "version.json").write_text(json.dumps({"sha": "abcdef1234567", "branch": "main", "date": "2026-06-01T10:00:00Z"}), encoding="utf-8")
    assert updater.installed(tmp_path)["sha"] == "abcdef1234567" and "main @ abcdef1" in updater.describe(updater.installed(tmp_path))


def test_update_apply_copies_program_files_but_keeps_venv(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("update_apply", Path(__file__).resolve().parents[1] / "update_apply.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, root = tmp_path / "src", tmp_path / "root"
    (source / "lolpicker").mkdir(parents=True)
    (source / "lolpicker" / "ui.py").write_text("new", encoding="utf-8")
    (source / "Autopicker.py").write_text("new", encoding="utf-8")
    (source / "version.json").write_text("{}", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "x").write_text("bad", encoding="utf-8")
    (root / "lolpicker").mkdir(parents=True)
    (root / "lolpicker" / "ui.py").write_text("old", encoding="utf-8")
    (root / "lolpicker" / "old_only.py").write_text("keep", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "python.exe").write_text("venv", encoding="utf-8")
    (root / "native_manifests").mkdir()
    (root / "native_manifests" / "chromium.json").write_text("reg", encoding="utf-8")
    module.apply(source, root)
    assert (root / "lolpicker" / "ui.py").read_text(encoding="utf-8") == "new" and (root / "Autopicker.py").exists() and (root / "version.json").exists()
    assert (root / "lolpicker" / "old_only.py").exists() and (root / ".venv" / "python.exe").read_text(encoding="utf-8") == "venv"
    assert not (root / ".venv" / "x").exists() and (root / "native_manifests" / "chromium.json").read_text(encoding="utf-8") == "reg"
