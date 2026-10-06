"""Lolalytics build import: parse the server-rendered page state (no browser, no scraping of the DOM)."""
import json
import logging
import re
import ssl
import urllib.request

from .urls import LANES, slug

LOG = logging.getLogger(__name__)
TIERS = ["all", "1trick", "challenger", "grandmaster", "grandmaster_plus", "master", "master_plus", "diamond", "d2_plus",
         "diamond_plus", "emerald", "emerald_plus", "platinum", "platinum_plus", "gold", "gold_plus", "silver", "bronze", "iron", "unranked"]
TIER_LABELS = {"all": "All Ranks", "1trick": "1Trick", "challenger": "Challenger", "grandmaster": "G.Master", "grandmaster_plus": "G.Master+",
               "master": "Master", "master_plus": "Master+", "diamond": "Diamond", "d2_plus": "D2+", "diamond_plus": "Diamond+",
               "emerald": "Emerald", "emerald_plus": "Emerald+", "platinum": "Platinum", "platinum_plus": "Platinum+", "gold": "Gold",
               "gold_plus": "Gold+", "silver": "Silver", "bronze": "Bronze", "iron": "Iron", "unranked": "Unranked"}
PATCHES = ["7", "14", "30"]  # days; a patch number like "16.19" is accepted as well
BUILDS = {"pick": "Most Common", "win": "Highest Win"}
IMPORT_DEFAULTS = {"enabled": False, "tier": "all", "patch": "30", "build": "pick"}
FLASH, SMITE = 4, 11


def import_settings(config, loadout=None):
    """Global rank/patch/build, overridden by the champion's own Lolalytics settings when present."""
    return {**IMPORT_DEFAULTS, **(config or {}), **((loadout or {}).get("lolalytics") or {})}


def recent_patches(version, count=6):
    """'16.19.1' -> ['16.19', '16.18', ...] for the patch dropdowns."""
    parts = str(version or "").split(".")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return []
    major, minor = int(parts[0]), int(parts[1])
    return [f"{major}.{minor - i}" for i in range(count) if minor - i >= 1]


def patch_options(version):
    return [("7", "7 Tage"), ("14", "14 Tage"), ("30", "30 Tage")] + [(p, f"Patch {p}") for p in recent_patches(version)]


def build_page_url(champion, lane="", tier="all", patch="30"):
    query = f"tier={tier}&patch={patch}" + (f"&lane={LANES.get(lane.lower(), lane)}" if lane else "")
    return f"https://lolalytics.com/lol/{slug(champion)}/build/?{query}"


def parse_page(html, build="pick"):
    """Returns {'perks': [6], 'shards': [3], 'spells': [2], 'lane': str} from the embedded Qwik state."""
    match = re.search(r'<script type="qwik/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("Lolalytics-Seite ohne Daten")
    objs = json.loads(match.group(1))["objs"]

    def deref(value, depth=0):
        if depth > 14:
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9a-z]{1,4}", value) and int(value, 36) < len(objs):
            return deref(objs[int(value, 36)], depth + 1)
        if isinstance(value, dict):
            return {k: deref(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [deref(v, depth + 1) for v in value]
        return value

    root = next((o for o in objs if isinstance(o, dict) and "summary" in o and "header" in o), None)
    if not root:
        raise ValueError("Keine Build-Daten für diesen Champion/diese Lane")
    summary = deref(root["summary"])[build if build in BUILDS else "pick"]
    runes, spells = summary["runes"]["set"], summary["sums"]["ids"]
    perks = list(runes["pri"]) + list(runes["sec"])
    if len(perks) != 6 or len(runes["mod"]) != 3 or len(spells) != 2:
        raise ValueError("Unvollständige Runen-Daten")
    return {"perks": [int(p) for p in perks], "shards": [int(s) for s in runes["mod"]], "spells": [int(s) for s in spells],
            "lane": str(deref(root["header"]).get("lane", "")), "games": int(summary["runes"].get("n", 0) or 0)}


def fetch_build(champion, lane="", tier="all", patch="30", build="pick", timeout=20):
    url = build_page_url(champion, lane, tier, patch)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LoLAutopicker/2.5"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request, timeout=timeout) as response:
        html = response.read(6 * 2 ** 20).decode("utf-8", "replace")
    result = parse_page(html, build)
    LOG.info("Lolalytics-Build geladen: %s (%s, %s, %s, %s Spiele)", url, result["lane"], tier, BUILDS.get(build, build), result["games"])
    return result


def to_loadout(build, rune_data, flash_side="left"):
    """Lolalytics set -> settings loadout; style ids come from the perk ids via Data Dragon."""
    with rune_data.lock:
        styles = {pid: perk["style"] for pid, perk in rune_data.perks.items() if perk["style"]}
    primary, sub = styles.get(build["perks"][0]), styles.get(build["perks"][4])
    if not primary or not sub:
        raise ValueError("Runen-Daten (Data Dragon) fehlen noch oder passen nicht zur Lolalytics-Seite")
    return {"primary": primary, "sub": sub, "perks": list(build["perks"]), "shards": list(build["shards"]),
            "spells": order_spells(build["spells"], flash_side)}


def order_spells(spells, flash_side="left"):
    """Flash on D (left, spell1) or F (right, spell2) as the player prefers; Lolalytics shows Flash left by default."""
    spells = list(spells)
    if FLASH in spells:
        other = next((s for s in spells if s != FLASH), spells[0])
        return [FLASH, other] if flash_side == "left" else [other, FLASH]
    return spells


def spells_for_role(loadout, role, flash_side="left"):
    """Jungle without Smite -> own jungle spells if configured, else Flash + Smite."""
    spells = list(loadout["spells"])
    if LANES.get(str(role).lower(), "") == "jungle" and SMITE not in spells:
        spells = list(loadout.get("jungle_spells") or [FLASH, SMITE])
    return order_spells(spells, flash_side)
