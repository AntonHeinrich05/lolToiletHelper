"""Native host framing subprocess smoke test (browser <-> bridge forwarding)."""
import json
import queue
import socket
import subprocess
import sys
import time
import threading


from lolpicker.bridge import BrowserBridge
from lolpicker.protocol import frame, receive


def _recv_with_timeout(read_fn, timeout=3):
    out = queue.Queue(maxsize=1)

    def run():
        try:
            out.put(receive(read_fn))
        except Exception as exc:  # noqa: BLE001
            out.put(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    item = out.get(timeout=timeout)
    if isinstance(item, Exception):
        raise item
    return item


def _start_stdout_reader(proc):
    out = queue.Queue()

    def run():
        try:
            while True:
                out.put(receive(proc.stdout.read))
        except Exception as exc:  # noqa: BLE001
            out.put(exc)

    thread = threading.Thread(target=run, daemon=True, name="native-host-stdout")
    thread.start()
    return out


def _await_message(messages, predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.01, deadline - time.monotonic())
        item = messages.get(timeout=remaining)
        if isinstance(item, Exception):
            raise item
        if predicate(item):
            return item
    raise TimeoutError("Timed out waiting for native-host message")


# native_host.py: stdio framing and bidirectional forwarding
def test_native_host_forwards_frames_between_stdio_and_bridge(localappdata, bundle_dir):
    data_dir = localappdata / "LoLAutopicker"
    data_dir.mkdir(parents=True, exist_ok=True)
    token = "test-token-123"

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(4)
    port = server.getsockname()[1]
    (data_dir / "bridge-session.json").write_text(json.dumps({"port": port, "token": token, "version": 1}), encoding="utf-8")

    env = dict(**__import__("os").environ)
    env["LOCALAPPDATA"] = str(localappdata)
    env["PYTHONPATH"] = str(bundle_dir)

    proc = subprocess.Popen(
        [sys.executable, str(bundle_dir / "native_host.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        waiting = _recv_with_timeout(proc.stdout.read)
        assert waiting == {"event": "bridge_status", "connected": False}
        proc.stdin.write(frame({"event": "hello", "client_id": "test-browser-123", "name": "browser"}))
        proc.stdin.flush()
        conn, _ = server.accept()
        conn.settimeout(3)

        auth = receive(conn.recv)
        assert auth["token"] == token
        hello = receive(conn.recv)
        assert hello["event"] == "hello"

        conn.sendall(frame({"event": "context", "champion": "aatrox"}))
        out = _recv_with_timeout(proc.stdout.read)
        assert out["event"] == "context"

        proc.stdin.write(frame({"event": "save", "id": "test-save", "url": "https://lolalytics.com/lol/aatrox/build/"}))
        proc.stdin.flush()
        incoming = receive(conn.recv)
        assert incoming["event"] == "save"
        assert incoming["id"] == "test-save"

        conn.close()
    finally:
        server.close()
        proc.terminate()
        proc.wait(timeout=5)


# native_host.py + bridge.py: hello-first flow, initial disconnected status, then quick reconnect on session rewrite
def test_native_host_hello_first_then_bridge_start_and_fast_reconnect(localappdata, bundle_dir):
    data_dir = localappdata / "LoLAutopicker"
    data_dir.mkdir(parents=True, exist_ok=True)

    env = dict(**__import__("os").environ)
    env["LOCALAPPDATA"] = str(localappdata)
    env["PYTHONPATH"] = str(bundle_dir)

    proc = subprocess.Popen(
        [sys.executable, str(bundle_dir / "native_host.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    events = []
    bridge1 = None
    bridge2 = None
    messages = _start_stdout_reader(proc)
    try:
        first = _await_message(messages, lambda m: m.get("event") == "bridge_status", timeout=4)
        assert first == {"event": "bridge_status", "connected": False}

        hello = {"event": "hello", "client_id": "test-browser-123", "name": "browser"}
        proc.stdin.write(frame(hello))
        proc.stdin.flush()

        def _emit(message):
            events.append(message)

        t0 = time.monotonic()
        bridge1 = BrowserBridge(
            data_dir,
            on_message=lambda _client_id, _message: {},
            emit=_emit,
            context=lambda: {"live_tracking": False, "champion": "aatrox"},
        )
        context1 = _await_message(messages, lambda m: m.get("event") == "context", timeout=4)
        initial_latency = time.monotonic() - t0
        assert context1["event"] == "context"

        bridge1.close()
        _await_message(messages, lambda m: m.get("event") == "bridge_status" and m.get("connected") is False, timeout=4)

        t1 = time.monotonic()
        bridge2 = BrowserBridge(
            data_dir,
            on_message=lambda _client_id, _message: {},
            emit=_emit,
            context=lambda: {"live_tracking": True, "champion": "kennen"},
        )
        context2 = _await_message(messages, lambda m: m.get("event") == "context" and m.get("champion") == "kennen", timeout=4)
        reconnect_latency = time.monotonic() - t1

        assert context2["live_tracking"] is True
        assert proc.poll() is None
        assert initial_latency < 4
        assert reconnect_latency < 2.5
        print(f'NativeRelay: initial={initial_latency:.3f}s, reconnect={reconnect_latency:.3f}s, same_process=True')
    finally:
        if bridge2:
            bridge2.close()
        if bridge1:
            bridge1.close()
        proc.terminate()
        proc.wait(timeout=5)
