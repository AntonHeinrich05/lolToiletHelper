"""UI-independent application coordinator; one bounded browser command worker."""
import logging
from pathlib import Path
import queue
import threading
from .bridge import BrowserBridge
from .browser_windows import ForegroundMonitor, close_browser_windows, focus_browser_window
from .lcu import LCUWorker
from .live import LiveWorker
from .runes import RuneData
from .selection import effective_lists
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
        # Lobby/queue: first champion of the list that is really in use (assigned role, else the selected list).
        picks = effective_lists(self.settings.snapshot(), self.role)["auto_pick_champs"]
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
                    self.close_browsers(clients)
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

    def close_browsers(self, clients):
        """Weak-PC mode / Alt+Shift+4. Scope from settings: only Lolalytics tabs (extension, Win32 fallback by window
        title) or whole browsers (Win32 WM_CLOSE on every browser window, extension as fallback)."""
        log = logging.getLogger(__name__)
        scope = self.settings.snapshot()["close_scope"]
        tabs, windows, errors = 0, 0, []
        if scope == "browser":
            windows = close_browser_windows(only_lolalytics=False)
            if not windows:
                for client in clients:
                    try:
                        windows += int(self.bridge.command("close_windows", client).get("windows", 0) or 0)
                    except (ValueError, OSError) as error:
                        errors.append(str(error))
            log.info("Browser geschlossen (ganze Fenster): %s, Erweiterungs-Fehler: %s", windows, errors)
            text = f"Browser geschlossen: {windows}" if windows else "Kein Browserfenster gefunden"
        else:
            for client in clients:
                try:
                    tabs += int(self.bridge.command("close_lolalytics", client).get("closed", 0) or 0)
                except (ValueError, OSError) as error:
                    errors.append(str(error))
            if not tabs:
                windows = close_browser_windows(only_lolalytics=True)
            log.info("Lolalytics-Tabs geschlossen: %s Tabs (%s Browser verbunden), %s Fenster per Titel, Fehler: %s",
                     tabs, len(clients), windows, errors)
            text = (f"Lolalytics-Tabs geschlossen: {tabs or windows}" if tabs or windows
                    else "Keine Lolalytics-Tabs gefunden" + ("" if clients else " – kein Browser verbunden (Erweiterung?)"))
        if errors and not (tabs or windows):
            text += f" – {errors[0]}"
        self.emit({"type": "notice", "text": text})
        self.emit({"type": "browsers_closed", "count": tabs or windows})

    def changed(self):
        logging.getLogger("lolpicker").setLevel(logging.DEBUG if self.settings.snapshot()["debug_mode"] else logging.INFO)
        self.bridge.broadcast_context()

    def close(self):
        self.stop_event.set()
        self.lcu.stop()
        self.live.stop()
        self.foreground.stop()
        self.bridge.close()