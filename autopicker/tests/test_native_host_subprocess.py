"""Native host framing subprocess smoke test (browser <-> bridge forwarding)."""
import json
import queue
import socket
import subprocess
import sys
import threading


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


# native_host.py: stdio framing and bidirectional forwarding
def test_native_host_forwards_frames_between_stdio_and_bridge(localappdata, bundle_dir):
    data_dir = localappdata / "LoLAutopicker"
    data_dir.mkdir(parents=True, exist_ok=True)
    token = "test-token-123"

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
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
        conn, _ = server.accept()
        conn.settimeout(3)

        auth = receive(conn.recv)
        assert auth["token"] == token

        conn.sendall(frame({"event": "context", "champion": "aatrox"}))
        out = _recv_with_timeout(proc.stdout.read)
        assert out["event"] == "context"

        proc.stdin.write(frame({"event": "hello", "client_id": "abc", "name": "browser"}))
        proc.stdin.flush()
        incoming = receive(conn.recv)
        assert incoming["event"] == "hello"
        assert incoming["client_id"] == "abc"

        conn.close()
    finally:
        server.close()
        proc.terminate()
        proc.wait(timeout=5)
