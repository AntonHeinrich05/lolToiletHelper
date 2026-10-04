"""Reconnectable local LCU client. No lcu-driver ready callback containing an endless loop."""
import asyncio
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import threading
import time
import aiohttp
import psutil
from .selection import active_action, choose, own_player, roster, draft_opponent

LOG = logging.getLogger(__name__)
PHASE = "/lol-gameflow/v1/gameflow-phase"
READY = "/lol-matchmaking/v1/ready-check"
SELECT = "/lol-champ-select/v1/session"


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


def discover(configured=""):
    candidates = [Path(configured)] if configured else []
    for process in psutil.process_iter(["name", "exe"]):
        try:
            if (process.info["name"] or "").lower() in ("leagueclient.exe", "leagueclientux.exe") and process.info["exe"]:
                base = Path(process.info["exe"]).parent
                candidates.extend([base / "lockfile", base.parent / "lockfile"])
        except (psutil.Error, OSError):
            continue
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
        self.completed = set()
        self.attempted = {}
        self.loop = None
        self.main_task = None
        self.lock = None

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

    async def main(self):
        self.loop, self.main_task = asyncio.get_running_loop(), asyncio.current_task()
        self.lock = asyncio.Lock()
        delay = 0.5
        while not self.stopped.is_set():
            credentials = await asyncio.to_thread(discover, self.settings.snapshot()["lockfile_path"])
            if credentials is None:
                await asyncio.sleep(2)
                continue
            self.phase, self.ready_accepted = "None", False
            self.queue_id = 0
            self.completed.clear()
            self.attempted.clear()
            try:
                timeout = aiohttp.ClientTimeout(total=3)
                async with aiohttp.ClientSession(auth=aiohttp.BasicAuth("riot", credentials.password), timeout=timeout, trust_env=False) as http:
                    self.http = http
                    self.base = f"https://127.0.0.1:{credentials.port}"
                    async with http.ws_connect(f"wss://127.0.0.1:{credentials.port}/", ssl=False,
                                               heartbeat=15, max_msg_size=2 ** 21) as ws:
                        # URI topics avoid receiving the entire client's high-volume event stream.
                        for path in (PHASE, READY, SELECT, "/lol-lobby/v2/lobby"):
                            await ws.send_json([5, "OnJsonApiEvent" + path.replace("/", "_")])
                        delay = 0.5
                        self.emit({"type": "status", "connected": True})
                        tasks = [asyncio.create_task(self.snapshot_loop()), asyncio.create_task(self.event_loop(ws))]
                        try:
                            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                            for task in done:
                                task.result()
                        finally:
                            for task in tasks:
                                task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
            except (aiohttp.ClientError, OSError, ValueError, asyncio.TimeoutError):
                LOG.info("LCU-Verbindung getrennt; Zugang wird neu eingelesen")
            finally:
                self.emit({"type": "status", "connected": False})
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8)

    async def request(self, method, path, body=None):
        # SSL exception is restricted to the discovered loopback LCU, not Internet traffic.
        async with self.http.request(method, self.base + path, json=body, ssl=False) as response:
            if response.status in (401, 403):
                raise ConnectionError("LCU-Anmeldung erneuern")
            if response.status >= 400:
                await response.read()
                return response.status, None
            text = await response.text()
            return response.status, json.loads(text) if text else None

    async def snapshot_loop(self):
        while True:
            async with self.lock:
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
                    _, data = await self.request("GET", "/lol-lobby/v2/lobby")
                    await self.handle("/lol-lobby/v2/lobby", data)
            # Fallback only; WebSocket accepts immediately on arrival, not on this timer.
            await asyncio.sleep(0.5 if self.phase in ("ReadyCheck", "ChampSelect") else 5)

    async def event_loop(self, ws):
        async for message in ws:
            if message.type == aiohttp.WSMsgType.TEXT:
                payload = json.loads(message.data)
                if isinstance(payload, list) and len(payload) >= 3 and payload[0] == 8 and isinstance(payload[2], dict):
                    event = payload[2]
                    async with self.lock:
                        if event.get("eventType") != "Delete":
                            await self.handle(event.get("uri"), event.get("data"))
            elif message.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                break

    async def handle(self, path, data):
        if path == PHASE and isinstance(data, str):
            if data != self.phase:
                self.phase = data
                self.ready_accepted = False
                if data != "ChampSelect":
                    self.completed.clear()
                    self.attempted.clear()
                if data in ("ChampSelect", "GameStart", "InProgress", "Reconnect"):
                    _, game = await self.request("GET", "/lol-gameflow/v1/session")
                    if isinstance(game, dict):
                        self.queue_id = game.get("gameData", {}).get("queue", {}).get("id", self.queue_id)
                LOG.debug("Spielphase: %s", data)
                self.emit({"type": "phase", "phase": data, "queue_id": self.queue_id})
            if data == "ReadyCheck":
                _, ready = await self.request("GET", READY)
                await self.accept_ready(ready)
        elif path == READY and isinstance(data, dict):
            await self.accept_ready(data)
        elif path == "/lol-lobby/v2/lobby" and isinstance(data, dict):
            self.queue_id = data.get("gameConfig", {}).get("queueId", 0)
        elif path == SELECT and isinstance(data, dict) and "localPlayerCellId" in data:
            self.queue_id = data.get("queueId", self.queue_id)
            me = own_player(data)
            self.emit({"type": "draft", "champion_id": me.get("championId", 0) or me.get("championPickIntent", 0),
                       "role": me.get("assignedPosition", ""), "roster": roster(data),
                       "opponent": draft_opponent(data), "queue_id": self.queue_id})
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
            self.emit({"type": "notice", "text": "Bereitschaftsanfrage angenommen"})

    async def automate(self, session):
        options = self.settings.snapshot()
        action = active_action(session)
        if not options["auto_pick_enabled"] or not action or action["id"] in self.completed:
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