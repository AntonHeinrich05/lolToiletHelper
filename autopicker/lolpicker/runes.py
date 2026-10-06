"""Rune/summoner spell data from Riot Data Dragon, cached in %LOCALAPPDATA%\\LoLAutopicker\\cache."""
import json
import logging
import ssl
import threading
import time
import urllib.request
from pathlib import Path

LOG = logging.getLogger(__name__)
DDRAGON = "https://ddragon.leagueoflegends.com"
LOCALE = "de_DE"
STYLE_ORDER = [8000, 8100, 8200, 8400, 8300]
# Stat shards are not part of runesReforged.json: rows offense / flex / defense like the client.
STAT_SHARDS = [
    [(5008, "Adaptive Kraft", "StatModsAdaptiveForceIcon.png", "+9 adaptive Kraft"),
     (5005, "Angriffstempo", "StatModsAttackSpeedIcon.png", "+10 % Angriffstempo"),
     (5007, "Fähigkeitstempo", "StatModsCDRScalingIcon.png", "+8 Fähigkeitstempo")],
    [(5008, "Adaptive Kraft", "StatModsAdaptiveForceIcon.png", "+9 adaptive Kraft"),
     (5010, "Lauftempo", "StatModsMovementSpeedIcon.png", "+2 % Lauftempo"),
     (5001, "Leben (skalierend)", "StatModsHealthScalingIcon.png", "+10–180 Leben, abhängig von der Stufe")],
    [(5011, "Leben", "StatModsHealthPlusIcon.png", "+65 Leben"),
     (5013, "Zähigkeit und Verlangsamungsresistenz", "StatModsTenacityIcon.png", "+10 % Zähigkeit und Verlangsamungsresistenz"),
     (5001, "Leben (skalierend)", "StatModsHealthScalingIcon.png", "+10–180 Leben, abhängig von der Stufe")],
]
# Summoner spells of the normal modes, in client order (see client "Zauber" tab).
SPELL_IDS = [6, 7, 11, 21, 3, 13, 32, 4, 12, 14, 1]
FALLBACK_SPELLS = {6: "Geist", 7: "Heilen", 11: "Zerschmettern", 21: "Barriere", 3: "Erschöpfen", 13: "Klarheit",
                   32: "Markieren", 4: "Blitz", 12: "Teleportation", 14: "Entzünden", 1: "Läuterung"}


class RuneData:
    """Loads styles, perks and spells once in the background; thread-safe `ready()` snapshot."""

    def __init__(self, directory):
        self.cache = Path(directory) / "cache"
        self.styles, self.perks, self.spells, self.version = [], {}, {}, ""
        self.loaded = threading.Event()
        self.error = ""
        self.lock = threading.Lock()
        self._opener = None

    def start(self):
        threading.Thread(target=self.load, name="DataDragon", daemon=True).start()

    def opener(self):
        if self._opener is None:
            self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        return self._opener

    def fetch(self, url, timeout=15):
        with self.opener().open(url, timeout=timeout) as response:
            return response.read(8 * 2 ** 20)

    def cached_json(self, name, url):
        path = self.cache / name
        try:
            with open(path, encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, ValueError):
            pass
        data = self.fetch(url)
        self.cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return json.loads(data)

    def load(self):
        try:
            versions = self.versions()
            self.version = versions[0]
            runes = self.cached_json(f"runes-{self.version}.json", f"{DDRAGON}/cdn/{self.version}/data/{LOCALE}/runesReforged.json")
            spells = self.cached_json(f"spells-{self.version}.json", f"{DDRAGON}/cdn/{self.version}/data/{LOCALE}/summoner.json")
            self.apply(runes, spells)
            LOG.info("Runen-Daten geladen (Data Dragon %s, %s Runen, %s Zauber)", self.version, len(self.perks), len(self.spells))
        except (OSError, ValueError, KeyError, IndexError) as error:
            self.error = "Runen-Daten konnten nicht geladen werden (Internet?)"
            LOG.warning("%s: %s", self.error, error)
        finally:
            self.loaded.set()
        if self.ready():
            self.prefetch_icons()

    def versions(self):
        """Fresh patch list once per day; cached copy when offline."""
        path = self.cache / "versions.json"
        try:
            if time.time() - path.stat().st_mtime < 86400:
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        try:
            data = self.fetch(f"{DDRAGON}/api/versions.json")
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return json.loads(data)
        except (OSError, ValueError):
            return json.loads(path.read_text(encoding="utf-8"))

    def all_icons(self):
        with self.lock:
            icons = [style["icon"] for style in self.styles]
            icons += [perk["icon"] for perk in self.perks.values()]
            icons += [spell["icon"] for spell in self.spells.values()]
        return icons

    def prefetch_icons(self):
        missing = 0
        for icon in self.all_icons():
            try:
                self.icon_bytes(icon)
            except OSError:
                missing += 1
        if missing:
            LOG.info("Runen-Symbole unvollständig: %s fehlen (Internet?)", missing)

    def apply(self, runes, spells):
        styles = {style["id"]: style for style in runes}
        with self.lock:
            self.styles = [styles[i] for i in STYLE_ORDER if i in styles] + [s for i, s in styles.items() if i not in STYLE_ORDER]
            self.perks = {}
            for style in self.styles:
                for slot in style["slots"]:
                    for perk in slot["runes"]:
                        self.perks[perk["id"]] = {"id": perk["id"], "name": perk["name"], "icon": perk["icon"],
                                                  "style": style["id"], "desc": perk.get("shortDesc", "")}
            for row in STAT_SHARDS:
                for identifier, name, icon, desc in row:
                    self.perks[identifier] = {"id": identifier, "name": name, "icon": f"perk-images/StatMods/{icon}", "style": 0, "desc": desc}
            self.spells = {}
            for spell in spells["data"].values():
                identifier = int(spell["key"])
                if identifier in SPELL_IDS:
                    self.spells[identifier] = {"id": identifier, "name": spell["name"], "icon": f"{self.version}/img/spell/{spell['image']['full']}",
                                               "desc": spell.get("description", "")}

    def ready(self):
        return self.loaded.is_set() and bool(self.styles)

    def icon_bytes(self, icon, fetch=True):
        """PNG bytes for a perk icon ('perk-images/...') or spell icon ('<version>/img/spell/...')."""
        path = self.cache / "img" / icon.replace("/", "_")
        try:
            return path.read_bytes()
        except OSError:
            if not fetch:
                return None
        url = f"{DDRAGON}/cdn/img/{icon}" if icon.startswith("perk-images/") else f"{DDRAGON}/cdn/{icon}"
        data = self.fetch(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def name(self, identifier):
        with self.lock:
            if identifier in self.perks:
                return self.perks[identifier]["name"]
            if identifier in self.spells:
                return self.spells[identifier]["name"]
            for style in self.styles:
                if style["id"] == identifier:
                    return style["name"]
        return FALLBACK_SPELLS.get(identifier, str(identifier))

    def validate(self, loadout):
        """Structural check against the loaded tree; True when data is not loaded yet."""
        if not self.ready():
            return True
        with self.lock:
            styles = {style["id"]: style for style in self.styles}
            primary, sub = styles.get(loadout["primary"]), styles.get(loadout["sub"])
            if not primary or not sub or primary is sub:
                return False
            for slot, perk in zip(primary["slots"], loadout["perks"][:4]):
                if perk not in {r["id"] for r in slot["runes"]}:
                    return False
            sub_rows = [i for i, slot in enumerate(sub["slots"][1:]) for perk in loadout["perks"][4:] if perk in {r["id"] for r in slot["runes"]}]
            if len(sub_rows) != 2 or sub_rows[0] == sub_rows[1]:
                return False
            return all(shard in {s[0] for s in row} for row, shard in zip(STAT_SHARDS, loadout["shards"]))


def page_body(name, loadout):
    return {"name": name, "primaryStyleId": loadout["primary"], "subStyleId": loadout["sub"],
            "selectedPerkIds": list(loadout["perks"]) + list(loadout["shards"]), "current": True}
