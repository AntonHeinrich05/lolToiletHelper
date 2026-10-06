"""Reconnectable local LCU client. Single request errors never tear down the connection."""
import asyncio
from base64 import b64encode
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import threading
import time
import aiohttp
import psutil
from .selection import actions, active_action, available, choose, own_player, roster, draft_opponent, effective_lists
from .runes import page_body
from .lolalytics import fetch_build, to_loadout, spells_for_role

LOG = logging.getLogger(__name__)
PHASE = "/lol-gameflow/v1/gameflow-phase"
READY = "/lol-matchmaking/v1/ready-check"
SELECT = "/lol-champ-select/v1/session"
LOBBY = "/lol-lobby/v2/lobby"
CLIENT_NAMES = ("leagueclient.exe", "leagueclientux.exe", "leagueclient", "leagueclientux")
MAX_POLL_FAILURES = 4
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=8)


@dataclass(frozen=True)
class Credentials:
    port: int
    password: str = field(repr=False)
    pid: int = 0


def parse_lockfile(text):
    _, pid, port, password, protocol = text.strip().split(":", 4)
    if protocol != "https" or not 1 <= int(port) <= 65535 or not password:
        raise ValueError("Ungültiges Lockfile")
    return Credentials(int(port), password, int(pid))


def parse_cmdline(cmdline, pid=0):
    port = password = None
    for argument in cmdline or []:
        if argument.startswith("--app-port="):
            port = int(argument.split("=", 1)[1])
        elif argument.startswith("--remoting-auth-token="):
            password = argument.split("=", 1)[1]
    if port and password and 1 <= port <= 65535:
        return Credentials(port, password, pid)
    return None


def default_lockfiles():
    roots = [Path("C:/Riot Games"), Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Riot Games",
             Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Riot Games"]
    return [root / "League of Legends/lockfile" for root in roots]


def discover(configured=""):
    candidates = [Path(configured)] if configured else []
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = (process.info["name"] or "").lower()
            if name not in CLIENT_NAMES:
                continue
            if name.startswith("leagueclientux"):
                # Same source as the previously working lcu-driver: the UX process command line.
                credentials = parse_cmdline(process.cmdline(), process.info["pid"])
                if credentials:
                    return credentials
            exe = process.exe()
            if exe:
                base = Path(exe).parent
                candidates.extend([base / "lockfile", base.parent / "lockfile"])
        except (psutil.Error, OSError, ValueError):
            continue
    candidates.extend(default_lockfiles())
    for path in dict.fromkeys(candidates):
        try:
            credentials = parse_lockfile(path.read_text(encoding="utf-8"))
            if psutil.pid_exists(credentials.pid):
                return credentials
        except (OSError, ValueError):
            continue
    return None


class LCUWorker(threading.Thread):
    def __init__(self, settings, emit, names=None, runes=None):
        super().__init__(daemon=True, name="LCU")
        self.settings, self.emit = settings, emit
        self.names = names or {}
        self.runes = runes
        self.stopped = threading.Event()
        self.phase, self.queue_id = "None", 0
        self.ready_accepted = False
        self.completed = set()
        self.attempted = {}
        self.loadout_done = set()
        self.connected = False
        self.loop = None
        self.main_task = None
        self.lock = None
        self.http = None
        self.base = ""

    def stop(self):
        self.stopped.set()
        if self.loop and self.main_task:
            try:
                self.loop.call_soon_threadsafe(self.main_task.cancel)
            except RuntimeError:
                pass

    def run(self):
        try:
            asyncio.run(self.main())
        except asyncio.CancelledError:
            pass

    def reset_state(self):
        self.phase, self.queue_id = "None", 0
        self.ready_accepted = False
        self.completed.clear()
        self.attempted.clear()
        self.loadout_done.clear()

    def set_connected(self, connected):
        if connected == self.connected:
            return
        self.connected = connected
        self.emit({"type": "status", "connected": connected})
        if not connected:
            # League closed or restarted: the overlay must not keep a stale phase.
            self.emit({"type": "phase", "phase": "None", "queue_id": 0})

    async def main(self):
        self.loop, self.main_task = asyncio.get_running_loop(), asyncio.current_task()
        self.lock = asyncio.Lock()
        delay = 1.0
        while not self.stopped.is_set():
            try:
                credentials = await asyncio.to_thread(discover, self.settings.snapshot()["lockfile_path"])
            except Exception:
                LOG.exception("League-Suche fehlgeschlagen")
                credentials = None
            if credentials is None:
                delay = 1.0
                await asyncio.sleep(1.5)
                continue
            self.reset_state()
            try:
                await self.session(credentials)
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if self.connected:
                    LOG.info("LCU-Verbindung getrennt (%s); Zugang wird neu eingelesen", error.__class__.__name__)
                    delay = 1.0
                else:
                    LOG.info("LCU noch nicht erreichbar (%s), neuer Versuch in %.1fs", error.__class__.__name__, delay)
            finally:
                self.set_connected(False)
                self.http = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5)

    async def session(self, credentials):
        authorization = "Basic " + b64encode(f"riot:{credentials.password}".encode("utf-8")).decode("ascii")
        # SSL exception is restricted to the discovered loopback LCU, not Internet traffic.
        connector = aiohttp.TCPConnector(ssl=False, force_close=True)
        timeout = aiohttp.ClientTimeout(total=None, connect=5, sock_connect=5)
        async with aiohttp.ClientSession(connector=connector, headers={"Authorization": authorization},
                                         timeout=timeout, trust_env=False) as http:
            self.http = http
            self.base = f"https://127.0.0.1:{credentials.port}"
            ws = await asyncio.wait_for(http.ws_connect(f"wss://127.0.0.1:{credentials.port}/", ssl=False,
                                                        heartbeat=None, max_msg_size=2 ** 21), 10)
            try:
                # URI topics avoid receiving the entire client's high-volume event stream.
                for path in (PHASE, READY, SELECT, LOBBY):
                    await ws.send_json([5, "OnJsonApiEvent" + path.replace("/", "_")])
                LOG.info("Mit League verbunden (Port %s)", credentials.port)
                self.set_connected(True)
                tasks = [asyncio.create_task(self.snapshot_loop()), asyncio.create_task(self.event_loop(ws))]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                await ws.close()

    async def request(self, method, path, body=None):
        async with self.http.request(method, self.base + path, json=body, ssl=False, timeout=REQUEST_TIMEOUT) as response:
            if response.status in (401, 403):
                LOG.warning("LCU verweigert %s %s (%s)", method, path, response.status)
            if response.status >= 400:
                body = (await response.text())[:200]
                if method != "GET":
                    LOG.info("%s %s -> HTTP %s %s", method, path, response.status, body)
                return response.status, None
            text = await response.text()
            try:
                return response.status, json.loads(text) if text else None
            except ValueError:
                return response.status, None

    async def poll(self):
        _, phase = await self.request("GET", PHASE)
        if isinstance(phase, str):
            await self.handle(PHASE, phase)
        if self.phase == "ReadyCheck":
            _, data = await self.request("GET", READY)
            await self.handle(READY, data)
        elif self.phase == "ChampSelect":
            _, data = await self.request("GET", SELECT)
            await self.handle(SELECT, data)
        elif self.phase == "Lobby":
            _, data = await self.request("GET", LOBBY)
            await self.handle(LOBBY, data)

    async def snapshot_loop(self):
        failures = 0
        while True:
            try:
                async with self.lock:
                    await self.poll()
                failures = 0
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as error:
                failures += 1
                LOG.info("LCU-Abfrage fehlgeschlagen (%s/%s): %s", failures, MAX_POLL_FAILURES, error.__class__.__name__)
                if failures >= MAX_POLL_FAILURES:
                    raise ConnectionError("LCU antwortet nicht mehr") from error
                await asyncio.sleep(1)
                continue
            except Exception:
                LOG.exception("Fehler bei der Verarbeitung des Client-Zustands")
            # Fallback only; WebSocket accepts immediately on arrival, not on this timer.
            await asyncio.sleep(0.5 if self.phase in ("ReadyCheck", "ChampSelect") else 5)

    async def event_loop(self, ws):
        async for message in ws:
            if message.type == aiohttp.WSMsgType.TEXT:
                try:
                    payload = json.loads(message.data)
                except ValueError:
                    continue
                if isinstance(payload, list) and len(payload) >= 3 and payload[0] == 8 and isinstance(payload[2], dict):
                    event = payload[2]
                    if event.get("eventType") == "Delete":
                        continue
                    try:
                        async with self.lock:
                            await self.handle(event.get("uri"), event.get("data"))
                    except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as error:
                        LOG.info("LCU-Anfrage nach Ereignis fehlgeschlagen: %s", error.__class__.__name__)
                    except Exception:
                        LOG.exception("Fehler bei der Verarbeitung eines Client-Ereignisses")
            elif message.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                break
        LOG.info("League-WebSocket geschlossen")

    async def handle(self, path, data):
        if path == PHASE and isinstance(data, str):
            if data != self.phase:
                self.phase = data
                self.ready_accepted = False
                if data != "ChampSelect":
                    self.completed.clear()
                    self.attempted.clear()
                    self.loadout_done.clear()
                if data in ("ChampSelect", "GameStart", "InProgress", "Reconnect"):
                    _, game = await self.request("GET", "/lol-gameflow/v1/session")
                    if isinstance(game, dict):
                        queue = ((game.get("gameData") or {}).get("queue") or {}).get("id")
                        if isinstance(queue, int):
                            self.queue_id = queue
                LOG.debug("Spielphase: %s", data)
                self.emit({"type": "phase", "phase": data, "queue_id": self.queue_id})
            if data == "ReadyCheck":
                _, ready = await self.request("GET", READY)
                await self.accept_ready(ready)
        elif path == READY and isinstance(data, dict):
            await self.accept_ready(data)
        elif path == LOBBY and isinstance(data, dict):
            queue = (data.get("gameConfig") or {}).get("queueId", 0)
            self.queue_id = queue if isinstance(queue, int) else 0
        elif path == SELECT and isinstance(data, dict) and "localPlayerCellId" in data:
            queue = data.get("queueId")
            if isinstance(queue, int) and queue > 0:
                self.queue_id = queue
            me = own_player(data)
            self.emit({"type": "draft", "champion_id": me.get("championId", 0) or me.get("championPickIntent", 0),
                       "role": me.get("assignedPosition", ""), "roster": roster(data),
                       "opponent": draft_opponent(data), "queue_id": self.queue_id})
            options = self.settings.snapshot()
            enemies = {enemy["champion_id"] for enemy in roster(data)}
            selected = me.get("championId") or me.get("championPickIntent")
            locked = any(a.get("type") == "pick" and a.get("completed") and a.get("actorCellId") == data.get("localPlayerCellId")
                         for a in actions(data))
            lists = effective_lists(options, me.get("assignedPosition"))
            states = {}
            for champion in lists["auto_pick_champs"]:
                if champion == selected:
                    states[champion] = "hovered"
                elif locked:
                    states[champion] = "ok"  # after lock-in the other rows stay neutral
                elif not available(data, champion):
                    states[champion] = "banned"
                elif enemies.intersection(options["bad_matchups"].get(str(champion), [])):
                    states[champion] = "bad_matchup"
                else:
                    states[champion] = "ok"
            my_bans = {a.get("championId") for a in actions(data) if a.get("type") == "ban" and a.get("completed")
                       and a.get("actorCellId") == data.get("localPlayerCellId")}
            ban_states = {}
            for champion in lists["auto_ban_champs"]:
                if champion in my_bans:
                    ban_states[champion] = "hovered"  # our own completed ban: blue like a locked pick
                elif not available(data, champion, "ban"):
                    ban_states[champion] = "banned"
                else:
                    ban_states[champion] = "ok"
            self.emit({"type": "pick_status", "status": states, "ban_status": ban_states, "role": me.get("assignedPosition", "")})
            if locked and selected and selected not in self.loadout_done:
                self.loadout_done.add(selected)
                loadout = options.get("loadouts", {}).get(str(selected))
                if not loadout and (options.get("lolalytics_import") or {}).get("enabled"):
                    loadout = await self.import_loadout(selected, me.get("assignedPosition", ""), options["lolalytics_import"])
                if loadout:
                    await self.apply_loadout(selected, loadout, me.get("assignedPosition", ""), options.get("flash_side", "left"))
            await self.automate(data)

    async def import_loadout(self, champion, role, settings):
        """No own loadout: take the Lolalytics page (rank/patch/build as configured) for the assigned lane."""
        name = self.names.get(champion, str(champion))
        try:
            build = await asyncio.to_thread(fetch_build, name, role, settings["tier"], settings["patch"], settings["build"])
            loadout = to_loadout(build, self.runes, self.settings.snapshot().get("flash_side", "left"))
        except (OSError, ValueError, KeyError, AttributeError) as error:
            LOG.info("Lolalytics-Import für %s fehlgeschlagen: %s", name, error)
            self.emit({"type": "notice", "text": f"Lolalytics-Runen für {name} nicht geladen"})
            return None
        LOG.info("Lolalytics-Runen für %s (%s) importiert", name, role or "Standard-Lane")
        return loadout

    async def apply_loadout(self, champion, loadout, role="", flash_side="left"):
        """After lock-in: own rune page 'Autopicker <Champion>' + summoner spells, like the client would do."""
        self.loadout_done.add(champion)
        if self.runes is not None and not self.runes.validate(loadout):
            LOG.info("Gespeicherte Runen für %s passen nicht mehr zum aktuellen Patch; Seite wird nicht gesetzt", champion)
            self.emit({"type": "notice", "text": f"Runen für {self.names.get(champion, champion)} veraltet – bitte neu wählen"})
            loadout = {**loadout, "perks": None}
        name = f"Autopicker {self.names.get(champion, champion)}"
        status, pages = await self.request("GET", "/lol-perks/v1/pages")
        pages = pages if isinstance(pages, list) else []
        editable = [p for p in pages if isinstance(p, dict) and p.get("isEditable", True) and p.get("isDeletable", True)]
        for page in [p for p in editable if str(p.get("name", "")).startswith("Autopicker")]:
            await self.request("DELETE", f"/lol-perks/v1/pages/{page['id']}")
        remaining = [p for p in editable if not str(p.get("name", "")).startswith("Autopicker")]
        _, inventory = await self.request("GET", "/lol-perks/v1/inventory")
        owned = inventory.get("ownedPageCount") if isinstance(inventory, dict) else None
        if isinstance(owned, int) and owned > 0 and len(remaining) >= owned:
            oldest = min(remaining, key=lambda p: p.get("lastModified", 0))
            status, _ = await self.request("DELETE", f"/lol-perks/v1/pages/{oldest['id']}")
            LOG.info("Runenseiten voll: älteste Seite '%s' ersetzt (HTTP %s)", oldest.get("name"), status)
        if loadout.get("perks"):
            status, page = await self.request("POST", "/lol-perks/v1/pages", page_body(name, loadout))
            LOG.info("Runenseite '%s' angelegt: HTTP %s", name, status)
            if status < 300 and isinstance(page, dict) and page.get("id") is not None:
                status, _ = await self.request("PUT", "/lol-perks/v1/currentpage", page["id"])
                LOG.info("Runenseite aktiviert: HTTP %s", status)
        spells = spells_for_role(loadout, role, flash_side)
        await self.set_spells(spells)
        self.emit({"type": "notice", "text": f"Runen & Zauber gesetzt: {self.names.get(champion, champion)}"})

    async def set_spells(self, spells):
        """PATCH my-selection, then verify in the session; retried a few times because the client ignores early PATCHes."""
        for attempt in range(1, 5):
            status, _ = await self.request("PATCH", SELECT + "/my-selection", {"spell1Id": spells[0], "spell2Id": spells[1]})
            await asyncio.sleep(0.4)
            _, session = await self.request("GET", SELECT)
            me = own_player(session) if isinstance(session, dict) else {}
            current = [me.get("spell1Id"), me.get("spell2Id")]
            LOG.info("Beschwörerzauber %s/%s setzen (Versuch %s): HTTP %s, Client zeigt %s", spells[0], spells[1], attempt, status, current)
            if current == list(spells):
                return True
            if status in (401, 403, 404):
                break
        return False

    async def accept_ready(self, data):
        if not isinstance(data, dict) or not self.settings.snapshot()["auto_ready_enabled"] or self.ready_accepted:
            return
        if data.get("state") != "InProgress" or str(data.get("playerResponse", "")).lower() != "none":
            return
        # Refresh before mutation: ignore stale queued WebSocket events.
        _, current = await self.request("GET", READY)
        if not isinstance(current, dict) or current.get("state") != "InProgress" or str(current.get("playerResponse", "")).lower() != "none":
            return
        status, _ = await self.request("POST", READY + "/accept")
        if status < 300:
            self.ready_accepted = True
            self.emit({"type": "ready_accepted"})

    async def prehover(self, session, options):
        # Pick intent (planning phase): PATCH championId on the own pick action, like the League client itself does.
        if not options["auto_pick_champs"]:
            return
        me = own_player(session)
        if me.get("championId") or me.get("championPickIntent"):
            return
        mine = [a for a in actions(session) if a.get("actorCellId") == session.get("localPlayerCellId")
                and a.get("type") == "pick" and not a.get("completed")]
        if not mine or any(a.get("championId") for a in mine):
            return
        if time.monotonic() - self.attempted.get("hover", 0) < 1.0:
            return
        self.attempted["hover"] = time.monotonic()
        champion = choose(session, options, "pick")
        if not champion:
            return
        for action in mine:
            status, _ = await self.request("PATCH", f"{SELECT}/actions/{action['id']}", {"championId": champion, "completed": False})
            LOG.info("Pick-Intent %s auf Aktion %s (Timer %s, aktiv %s): HTTP %s", champion, action["id"],
                     (session.get("timer") or {}).get("phase"), action.get("isInProgress"), status)

    async def automate(self, session):
        options = self.settings.snapshot()
        if not options["auto_pick_enabled"]:
            return
        action = active_action(session)
        # PLANNING ("Absicht verkünden") never locks: only declare intent, even if the LCU flags the action in progress.
        if not action or (session.get("timer") or {}).get("phase") == "PLANNING":
            await self.prehover(session, options)
            return
        identifier = action["id"]
        if time.monotonic() - self.attempted.get(identifier, 0) < 1.0:
            return
        self.attempted[identifier] = time.monotonic()
        # Fresh state guards against stale queued events; retried every second until the LCU marks it completed.
        _, fresh = await self.request("GET", SELECT)
        if isinstance(fresh, dict):
            current = active_action(fresh)
            if not current or current["id"] != identifier or current.get("type") != action.get("type"):
                return
            session = fresh
        champion = choose(session, options, action["type"])
        if not champion:
            LOG.info("Kein %s-Champion verfügbar (Aktion %s)", action["type"], identifier)
            return
        path = f"{SELECT}/actions/{identifier}"
        status, _ = await self.request("PATCH", path, {"championId": champion, "completed": True})
        LOG.info("%s %s: Hover HTTP %s", action["type"].capitalize(), champion, status)
        if status >= 300:
            # At least show the hover if the client refuses completing right now; retried next second.
            await self.request("PATCH", path, {"championId": champion, "completed": False})
            return
        await asyncio.sleep(0.12)
        if not self.settings.snapshot()["auto_pick_enabled"]:
            return
        status, _ = await self.request("POST", path + "/complete")
        LOG.info("%s %s: Bestätigung HTTP %s", action["type"].capitalize(), champion, status)
        if status < 300:
            self.completed.add(identifier)
