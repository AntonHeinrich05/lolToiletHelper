"""Bounded active-game polling, independent of the client connection."""
import json
import ssl
import threading
import urllib.request
from .selection import live_matchup


class LiveWorker(threading.Thread):
    def __init__(self, settings, emit):
        super().__init__(daemon=True, name="LiveClient")
        self.settings, self.emit = settings, emit
        self.enabled = threading.Event()
        self.stopped = threading.Event()
        self.last = None

    def set_active(self, enabled):
        if enabled:
            self.enabled.set()
        else:
            self.enabled.clear()
            self.last = None

    def stop(self):
        self.stopped.set()

    def run(self):
        # This opener is used ONLY for the fixed loopback Live Client API.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
        failures = 0
        while not self.stopped.is_set():
            if not self.enabled.is_set():
                self.stopped.wait(1)
                continue
            port = self.settings.snapshot()["live_api_port"]
            try:
                with opener.open(f"https://127.0.0.1:{port}/liveclientdata/allgamedata", timeout=2) as response:
                    data = json.loads(response.read(2 ** 20))
                match = live_matchup(data)
                failures = 0
                if match and self.enabled.is_set() and match != self.last:
                    self.last = match
                    self.emit({"type": "live", **match})
            except (OSError, ValueError):
                failures = min(failures + 1, 5)
            self.stopped.wait(10 if self.last else min(1 + failures, 5))