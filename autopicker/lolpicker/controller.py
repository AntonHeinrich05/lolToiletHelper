"""UI-independent application coordinator; one bounded browser command worker."""
import logging
from pathlib import Path
import queue
import threading
from .bridge import BrowserBridge
from .browser_windows import ForegroundMonitor, focus_browser_window
from .lcu import LCUWorker
from .live import LiveWorker
from .runes import RuneData
from .storage import Settings, data_dir, read_json
from .urls import UrlStore, build_url, slug, NO_LANE


class Controller:
    def __init__(self, directory=None, bundle=None, start_workers=True):
        self.directory = Path(directory or data_dir())
        self.bundle = Path(bundle or Path(__file__).resolve().parents[1])
        self.settings = Settings(self.directory, self.bundle)
        self.urls = UrlStore(self.directory / "urls.json", self.bundle / "lol_tool_state.json")
        self.catalog = {int(k): v for k, v in read_json(self.bundle / "assets/champions.json", {}).items()}
        self.events = queue.Queue(maxsize=128)
        self.commands = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.champion, self.role, self.phase, self.opponent = "", "", "None", None
        self.queue_id, self.live_confirmed = 0, False
        self.command_lock = threading.Lock()
        self.inflight = set()
        self.last_live_url = None
        self.bridge = BrowserBridge(self.directory, self.on_browser, self.emit, self.context)
        self.runes = RuneData(self.directory)
        self.lcu = LCUWorker(self.settings, self.emit, self.catalog, self.runes)
        self.live = LiveWorker(self.settings, self.emit)
        self.foreground = ForegroundMonitor(self.settings, self.emit)
        threading.Thread(target=self.browser_worker, daemon=True, name="BrowserCommands").start()
        if start_workers:
            self.lcu.start()
            self.live.start()
            self.foreground.start()
            self.runes.start()

    def emit(self, message):
        try:
            self.events.put_nowait(message)
        except queue.Full:
            # A stuck UI cannot grow RAM indefinitely. Next authoritative snapshot recovers state.
            logging.getLogger(__name__).warning("UI-Ereigniswarteschlange voll")

    def context(self):
        return {"live_tracking": self.settings.snapshot()["live_tracking"], "champion": slug(self.current_champion())}

    def current_champion(self):
        if self.champion:
            return self.champion
        picks = self.settings.snapshot()["auto_pick_champs"]
        return self.catalog.get(picks[0], "") if picks else ""

    def on_browser(self, client_id, message):
        event = message.get("event")
        if event == "save":
            expected = message.get("champion")
            if not isinstance(expected, str) or not expected:
                raise ValueError("Champion fehlt")
            kind = message.get("kind")
            if kind not in ("base", "vs"):
                raise ValueError("Ungültiger Tab-Typ")
            if not self.urls.remember(message.get("url"), expected, kind):
                raise ValueError("Anderer Champion")
            return {"saved": True}
        if event == "select_browser":
            if not self.settings.update(preferred_browser=client_id):
                raise OSError("Speichern fehlgeschlagen")
            self.emit({"type": "notice", "text": "Browser ausgewählt"})
            return {}
        raise ValueError("Unbekanntes Ereignis")

    def handle(self, message):
        kind = message["type"]
        if kind == "phase":
            self.phase = message["phase"]
            self.queue_id = message.get("queue_id", self.queue_id)
            self.live.set_active(self.phase in ("InProgress", "GameStart", "Reconnect"))
            if self.phase in ("None", "Lobby", "Matchmaking", "EndOfGame", "WaitingForStats", "PreEndOfGame"):
                self.champion, self.role, self.opponent = "", "", None
                self.live_confirmed, self.last_live_url = False, None
            self.bridge.broadcast_context()
        elif kind == "status" and message["connected"]:
            self.bridge.broadcast_context()
        elif kind == "game_foreground" and self.settings.snapshot()["weak_pc_mode"]:
            self.enqueue("close_lolalytics", all_clients=True)
        elif kind == "draft" and self.phase not in ("InProgress", "GameStart", "Reconnect"):
            self.champion = self.catalog.get(message["champion_id"], "")
            self.role, self.queue_id = message["role"], message["queue_id"]
            enemy = message["opponent"]
            self.opponent = {"champion": self.catalog.get(enemy["champion_id"], ""), "role": enemy["role"], "source": "draft"} if enemy else None
            self.live_confirmed = False
            self.bridge.broadcast_context()
        elif kind == "live" and self.phase in ("InProgress", "GameStart", "Reconnect") and self.queue_id not in NO_LANE:
            self.champion, self.role = message["champion"], message["role"]
            self.opponent = {"champion": message["opponent"], "role": message["opponent_role"], "source": "live"}
            self.live_confirmed = True
            self.last_live_url = self.vs_url()
            self.enqueue("correct_vs", all_clients=True, url=self.last_live_url, champion=slug(self.champion))
            self.bridge.broadcast_context()
        elif kind == "browsers" and self.last_live_url:
            self.enqueue("correct_vs", all_clients=True, url=self.last_live_url, champion=slug(self.champion))

    def vs_url(self):
        if not self.opponent or not self.champion or self.queue_id in NO_LANE:
            return None
        return build_url(self.champion, self.role, self.queue_id, self.opponent["champion"], self.opponent["role"])

    def open(self, kind="base"):
        fresh = self.vs_url() if kind == "vs" else build_url(self.current_champion(), self.role, self.queue_id)
        if not fresh:
            self.emit({"type": "notice", "text": "Noch kein verlässlicher Gegner bekannt" if kind == "vs" else "Zuerst einen Champion zur Pick-Liste hinzufügen"})
            return
        final = self.urls.restore(fresh, kind)
        if kind == "vs" and self.live_confirmed:
            final = self.urls.corrected_vs(final, fresh)
        self.enqueue("open", url=final, kind=kind)

    def enqueue(self, command, all_clients=False, **args):
        key = (command, str(sorted(args.items())), all_clients)
        with self.command_lock:
            if key in self.inflight:
                return  # coalesce key repeat/spam until acknowledged
            self.inflight.add(key)
        try:
            preferred = self.settings.snapshot()["preferred_browser"]
            self.commands.put_nowait((key, command, preferred, all_clients, args))
        except queue.Full:
            with self.command_lock:
                self.inflight.discard(key)
            self.emit({"type": "notice", "text": "Browser ist beschäftigt; bitte kurz warten"})

    def browser_worker(self):
        while not self.stop_event.is_set():
            try:
                key, command, preferred, all_clients, args = self.commands.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                clients = list(self.bridge.listing()) if all_clients else [preferred]
                if command == "close_lolalytics":
                    # Weak-PC mode / Alt+Shift+4: only Lolalytics tabs, in every connected browser; never other tabs.
                    count = 0
                    for client in clients:
                        count += int(self.bridge.command("close_lolalytics", client).get("closed", 0) or 0)
                    logging.getLogger(__name__).info("Lolalytics-Tabs geschlossen (alle Browser): %s", count)
                    self.emit({"type": "browsers_closed", "count": count})
                else:
                    for client in clients:
                        result = self.bridge.command(command, client, **args)
                        if command == "open":
                            # Hotkey path: the game keeps the foreground, so pull the browser window up ourselves.
                            focus_browser_window(slug(self.current_champion()))
                        if command.startswith("close"):
                            logging.getLogger(__name__).info("Lolalytics-Tabs geschlossen: %s", result.get("closed", 0))
            except (ValueError, OSError) as error:
                self.emit({"type": "notice", "text": str(error)})
            finally:
                with self.command_lock:
                    self.inflight.discard(key)

    def changed(self):
        logging.getLogger("lolpicker").setLevel(logging.DEBUG if self.settings.snapshot()["debug_mode"] else logging.INFO)
        self.bridge.broadcast_context()

    def close(self):
        self.stop_event.set()
        self.lcu.stop()
        self.live.stop()
        self.foreground.stop()
        self.bridge.close()