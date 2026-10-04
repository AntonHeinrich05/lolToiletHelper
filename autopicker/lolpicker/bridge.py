"""Authenticated native-host bridge. No HTTP/CORS listener or browser scraping."""
from collections import OrderedDict
from dataclasses import dataclass, field
import logging
import secrets
import socket
import threading
import uuid
from .protocol import receive, frame
from .storage import atomic_json, read_json

LOG = logging.getLogger(__name__)


@dataclass
class Channel:
    socket: socket.socket
    client_id: str
    name: str
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    pending: dict = field(default_factory=dict)
    seen: OrderedDict = field(default_factory=OrderedDict)

    def send(self, message):
        with self.send_lock:
            self.socket.sendall(frame(message))


class BrowserBridge:
    def __init__(self, directory, on_message, emit, context):
        self.path = directory / "bridge-session.json"
        self.on_message, self.emit, self.context = on_message, emit, context
        self.token = secrets.token_urlsafe(32)
        self.clients, self.lock = {}, threading.RLock()
        self.stopped = threading.Event()
        self.slots = threading.BoundedSemaphore(16)
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        self.server.settimeout(1)
        atomic_json(self.path, {"port": self.server.getsockname()[1], "token": self.token, "version": 1})
        threading.Thread(target=self.accept, name="BrowserBridge", daemon=True).start()

    def listing(self):
        with self.lock:
            return {key: channel.name for key, channel in self.clients.items()}

    def accept(self):
        while not self.stopped.is_set():
            try:
                conn, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self.slots.acquire(blocking=False):
                conn.close()
                continue
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        channel = None
        try:
            conn.settimeout(5)
            auth = receive(conn.recv)
            token = auth.get("token")
            if not isinstance(token, str) or not secrets.compare_digest(token, self.token):
                return
            hello = receive(conn.recv)
            client_id = hello.get("client_id", "")
            if hello.get("event") != "hello" or not isinstance(client_id, str) or not 8 <= len(client_id) <= 80:
                return
            channel = Channel(conn, client_id, str(hello.get("name", "Browser"))[:64])
            with self.lock:
                old = self.clients.get(client_id)
                self.clients[client_id] = channel
                if old:
                    old.socket.close()
            conn.settimeout(None)
            channel.send({"event": "context", **self.context()})
            self.emit({"type": "browsers", "clients": self.listing()})
            while not self.stopped.is_set():
                message = receive(conn.recv)
                if isinstance(message.get("reply_to"), str):
                    with self.lock:
                        pending = channel.pending.get(message["reply_to"])
                        if pending:
                            pending[1].update(message)
                            pending[0].set()
                    continue
                identifier = message.get("id")
                if not isinstance(identifier, str) or len(identifier) > 80:
                    continue
                if identifier in channel.seen:
                    channel.send(channel.seen[identifier])
                    continue
                try:
                    result = self.on_message(client_id, message)
                    answer = {"reply_to": identifier, "ok": True, **(result or {})}
                except (ValueError, OSError, TypeError):
                    answer = {"reply_to": identifier, "ok": False, "error": "Speichern fehlgeschlagen oder ungültige Nachricht"}
                channel.seen[identifier] = answer
                while len(channel.seen) > 128:
                    channel.seen.popitem(last=False)
                channel.send(answer)
        except (OSError, EOFError, ValueError, TypeError):
            pass
        finally:
            conn.close()
            if channel:
                with self.lock:
                    if self.clients.get(channel.client_id) is channel:
                        self.clients.pop(channel.client_id)
                    for done, response in channel.pending.values():
                        response.update(ok=False, error="Browser-Verbindung beendet")
                        done.set()
                self.emit({"type": "browsers", "clients": self.listing()})
            self.slots.release()

    def command(self, command, client_id="", **args):
        with self.lock:
            if client_id:
                channel = self.clients.get(client_id)
            else:
                channel = next(iter(self.clients.values()), None) if len(self.clients) == 1 else None
            if not channel:
                raise ValueError("Browser-Erweiterung verbinden und bei mehreren Browsern einen in Einstellungen auswählen")
            identifier, done, response = str(uuid.uuid4()), threading.Event(), {}
            channel.pending[identifier] = (done, response)
        try:
            channel.send({"id": identifier, "command": command, **args})
            if not done.wait(12):
                raise ValueError("Browser antwortet nicht. Verbindung prüfen; Tabs werden nicht erneut geöffnet.")
            if not response.get("ok"):
                raise ValueError(response.get("error", "Browser-Aktion fehlgeschlagen"))
            return response
        finally:
            with self.lock:
                channel.pending.pop(identifier, None)

    def broadcast_context(self):
        with self.lock:
            channels = list(self.clients.values())
        for channel in channels:
            try:
                channel.send({"event": "context", **self.context()})
            except OSError:
                pass

    def close(self):
        self.stopped.set()
        self.server.close()
        with self.lock:
            for channel in self.clients.values():
                try:
                    channel.socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                channel.socket.close()
        try:
            if read_json(self.path, {}).get("token") == self.token:
                self.path.unlink(missing_ok=True)
        except OSError:
            pass