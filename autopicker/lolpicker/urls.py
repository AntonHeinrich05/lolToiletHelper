"""Strict URL scoping; retain item/VS parameters without crossing champions."""
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .storage import atomic_json, read_json

LANES = {"top": "top", "jungle": "jungle", "middle": "middle", "mid": "middle",
         "bottom": "bottom", "adc": "bottom", "utility": "support", "support": "support"}
NO_LANE = {450, 2400, 1700, 1710, 1750}


def slug(name):
    aliases = {"monkeyking": "wukong", "nunu & willump": "nunu", "renata glasc": "renata"}
    return re.sub(r"[^a-z0-9]", "", aliases.get(name.lower(), name.lower()))


def canonical(url):
    if not isinstance(url, str) or len(url) > 8192:
        raise ValueError("Ungültige URL")
    p = urlsplit(url)
    if p.scheme not in ("https", "http") or p.hostname not in ("lolalytics.com", "www.lolalytics.com"):
        raise ValueError("Nur Lolalytics-URLs erlaubt")
    if p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError("Ungültiger Host")
    path = p.path.rstrip("/") + "/"
    if not re.fullmatch(r"/lol/[a-z0-9]+/(?:[a-z0-9]+/)*", path):
        raise ValueError("Keine Champion-Seite")
    # Sorting keys (stable) leaves repeated parameter values in their original order.
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True), key=lambda x: x[0]))
    return urlunsplit(("https", "lolalytics.com", path, query, p.fragment))


def identity(url):
    parts = urlsplit(canonical(url)).path.strip("/").split("/")
    opponent = parts[3] if len(parts) > 3 and parts[2] == "vs" else ""
    mode = "aram" if "aram" in parts[2:] else "arena" if "arena" in parts[2:] else "classic"
    return parts[1], opponent, mode


def build_url(champion, role="", queue_id=0, opponent="", opponent_role=""):
    own = slug(champion)
    if not own:
        return None
    mode = "arena/" if queue_id in (1700, 1710, 1750) else "aram/" if queue_id in (450, 2400) else ""
    suffix = f"vs/{slug(opponent)}/build/" if opponent and not mode else f"{mode}build/"
    query = {"tier": "all"}
    if not mode and LANES.get(role.lower()):
        query["lane"] = LANES[role.lower()]
    if opponent and not mode and LANES.get(opponent_role.lower()):
        query["vslane"] = LANES[opponent_role.lower()]
    return canonical(f"https://lolalytics.com/lol/{own}/{suffix}?{urlencode(query)}")


class UrlStore:
    def __init__(self, path, legacy_path=None):
        self.path, self.lock = Path(path), threading.RLock()
        self.value = read_json(path, {})
        if not self.value and legacy_path:
            for entry in read_json(legacy_path, {}).values():
                if isinstance(entry, dict) and isinstance(entry.get("url"), str):
                    try:
                        self.remember(entry["url"])
                    except (ValueError, OSError):
                        pass

    def remember(self, url, expected_champion=None, kind="base"):
        url = canonical(url)
        champ, _, mode = identity(url)
        if expected_champion and champ != expected_champion:
            return False
        key = f"{champ}|{mode}|{kind}"
        page_key = "page|" + "|".join(identity(url))
        with self.lock:
            if self.value.get(key) == url and self.value.get(page_key) == url:
                return True
            updated = {**self.value, key: url, page_key: url}
            atomic_json(self.path, updated)
            self.value = updated
        return True

    def restore(self, fresh, kind="base"):
        champ, opponent, mode = identity(fresh)
        with self.lock:
            # Base button resumes the last same-champion page, including a manually chosen VS.
            key = f"{champ}|{mode}|base" if kind == "base" else "page|" + "|".join((champ, opponent, mode))
            saved = self.value.get(key)
        try:
            if saved and identity(saved)[0] == champ and identity(saved)[2] == mode:
                return canonical(saved)
        except ValueError:
            pass
        return fresh

    def corrected_vs(self, old, fresh):
        """Keep build filters, replace the opponent AND both authoritative lanes."""
        if identity(old)[0] != identity(fresh)[0]:
            return fresh
        previous, current = urlsplit(canonical(old)), urlsplit(canonical(fresh))
        params = [(k, v) for k, v in parse_qsl(previous.query, keep_blank_values=True) if k not in ("lane", "vslane")]
        old_keys = {k for k, _ in params}
        params += [(k, v) for k, v in parse_qsl(current.query) if k in ("lane", "vslane") or k not in old_keys]
        return canonical(urlunsplit(current._replace(query=urlencode(params))))