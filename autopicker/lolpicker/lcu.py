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
from .selection import actions, active_action, available, choose, own_player, roster, draft_opponent

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
    def __init__(self, settings, emit):
        super().__init__(daemon=True, name="LCU")
        self.settings, self.emit = settings, emit
        self.stopped = threading.Event()
        self.phase, self.queue_id = "None", 0
        self.ready_accepted = False
        self.hovered = False
        self.completed = set()
        self.attempted = {}
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
        self.ready_accepted, self.hovered = False, False
        self.completed.clear()
        self.attempted.clear()

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
                await response.read()
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
                    self.hovered = False
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
            states = {}
            for champion in options["auto_pick_champs"]:
                if champion == selected:
                    states[champion] = "hovered"
                elif not available(data, champion):
                    states[champion] = "banned"
                elif enemies.intersection(options["bad_matchups"].get(str(champion), [])):
                    states[champion] = "bad_matchup"
                else:
                    states[champion] = "ok"
            self.emit({"type": "pick_status", "status": states})
            await self.automate(data)

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
        # Declare pick intent early, like the original tool, so teammates see the planned champion.
        if self.hovered or not options["auto_pick_champs"]:
            return
        me = own_player(session)
        if me.get("championId") or me.get("championPickIntent"):
            return
        mine = next((a for a in actions(session) if a.get("actorCellId") == session.get("localPlayerCellId")
                     and a.get("type") == "pick" and not a.get("completed")), None)
        if not mine or mine.get("championId"):
            return
        key = ("hover", mine["id"])
        if time.monotonic() - self.attempted.get(key, 0) < 2:
            return
        self.attempted[key] = time.monotonic()
        champion = choose(session, options, "pick")
        if not champion:
            return
        status, _ = await self.request("PATCH", f"{SELECT}/actions/{mine['id']}", {"championId": champion})
        if status < 300:
            self.hovered = True

    async def automate(self, session):
        options = self.settings.snapshot()
        if not options["auto_pick_enabled"]:
            return
        action = active_action(session)
        if not action:
            await self.prehover(session, options)
            return
        if action["id"] in self.completed:
            return
        identifier = action["id"]
        if time.monotonic() - self.attempted.get(identifier, 0) < 0.6:
            return
        self.attempted[identifier] = time.monotonic()
        # Reject stale event data, dodged lobbies and previous turns before PATCH.
        _, fresh = await self.request("GET", SELECT)
        if not isinstance(fresh, dict):
            return
        current = active_action(fresh)
        if not current or current["id"] != identifier or current.get("type") != action.get("type"):
            return
        resource = "pickable-champion-ids" if action["type"] == "pick" else "bannable-champion-ids"
        _, allowed = await self.request("GET", f"/lol-champ-select/v1/{resource}")
        if not isinstance(allowed, list):
            return  # fail closed rather than lock an unowned/unavailable champion
        fresh["pickableChampionIds" if action["type"] == "pick" else "bannableChampionIds"] = allowed
        champion = choose(fresh, options, action["type"])
        if not champion:
            return
        path = f"{SELECT}/actions/{identifier}"
        status, _ = await self.request("PATCH", path, {"championId": champion, "completed": False})
        if status >= 300:
            return
        _, latest = await self.request("GET", SELECT)
        latest_action = active_action(latest) if isinstance(latest, dict) else None
        if not latest_action or latest_action["id"] != identifier or latest_action.get("championId") != champion:
            return
        if not self.settings.snapshot()["auto_pick_enabled"]:
            return
        status, _ = await self.request("POST", path + "/complete")
        if status < 300:
            self.completed.add(identifier)
            self.hovered = True
