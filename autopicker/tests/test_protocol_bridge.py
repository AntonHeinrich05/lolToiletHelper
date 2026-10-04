"""Framing and BrowserBridge transport/auth regression tests."""
import socket
import threading
import time

import pytest

from lolpicker.bridge import BrowserBridge
from lolpicker.protocol import frame, receive, MAX_FRAME


# protocol.py: framed read/write including partial and oversized payload handling
def test_protocol_receive_partial_chunks_and_reject_oversized():
    payload = frame({"ok": True, "value": 1})
    chunks = [payload[:2], payload[2:5], payload[5:9], payload[9:]]

    def reader(n):
        nonlocal chunks
        if not chunks:
            return b""
        part = chunks[0][:n]
        chunks[0] = chunks[0][n:]
        if not chunks[0]:
            chunks.pop(0)
        return part

    assert receive(reader)["ok"] is True

    oversized = (MAX_FRAME + 1).to_bytes(4, "little") + b"x"
    tail = [oversized]

    def bad_reader(n):
        if not tail:
            return b""
        part = tail[0][:n]
        tail[0] = tail[0][n:]
        if not tail[0]:
            tail.pop(0)
        return part

    with pytest.raises(ValueError):
        receive(bad_reader)


def _connect_to_bridge(bridge):
    port = bridge.server.getsockname()[1]
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    sock.settimeout(2)
    return sock


# bridge.py: localhost auth, request/reply, duplicate-id cache and disconnect cleanup
def test_bridge_rejects_invalid_token(data_directory):
    bridge = BrowserBridge(data_directory, lambda *_: {}, lambda _m: None, lambda: {"live_tracking": False, "champion": ""})
    try:
        sock = _connect_to_bridge(bridge)
        sock.sendall(frame({"token": "wrong"}))
        time.sleep(0.1)
        with pytest.raises((OSError, EOFError, ValueError, ConnectionResetError, socket.timeout)):
            receive(sock.recv)
        sock.close()
    finally:
        bridge.close()


def test_bridge_valid_handshake_and_duplicate_request_reply(data_directory):
    calls = []

    def on_message(client_id, message):
        calls.append((client_id, message))
        return {"echo": message.get("event", "cmd")}

    bridge = BrowserBridge(data_directory, on_message, lambda _m: None, lambda: {"live_tracking": True, "champion": "aatrox"})
    try:
        sock = _connect_to_bridge(bridge)
        sock.sendall(frame({"token": bridge.token}))
        sock.sendall(frame({"event": "hello", "client_id": "client-1234", "name": "TestBrowser"}))
        context = receive(sock.recv)
        assert context["event"] == "context"

        request = {"id": "same-id", "event": "save", "champion": "aatrox", "kind": "base", "url": "https://lolalytics.com/lol/aatrox/build/?tier=all"}
        sock.sendall(frame(request))
        first = receive(sock.recv)
        sock.sendall(frame(request))
        second = receive(sock.recv)

        assert first["ok"] is True and second["ok"] is True
        assert first == second
        assert len(calls) == 1
        sock.close()
    finally:
        bridge.close()


def test_bridge_command_roundtrip_and_disconnect_cleanup(data_directory):
    bridge = BrowserBridge(data_directory, lambda *_: {}, lambda _m: None, lambda: {"live_tracking": False, "champion": ""})
    try:
        sock = _connect_to_bridge(bridge)
        sock.sendall(frame({"token": bridge.token}))
        sock.sendall(frame({"event": "hello", "client_id": "client-rpc", "name": "RPC"}))
        _ = receive(sock.recv)  # context

        def responder():
            msg = receive(sock.recv)
            sock.sendall(frame({"reply_to": msg["id"], "ok": True, "closed": 1}))

        thread = threading.Thread(target=responder, daemon=True)
        thread.start()
        reply = bridge.command("close", client_id="client-rpc")
        assert reply["closed"] == 1

        # now test pending command interrupted by disconnect
        errors = []

        def requester():
            try:
                bridge.command("open", client_id="client-rpc", url="https://lolalytics.com/lol/aatrox/build/?tier=all")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        pending = threading.Thread(target=requester, daemon=True)
        pending.start()
        msg = receive(sock.recv)
        assert msg["command"] == "open"
        sock.close()  # disconnect before reply
        pending.join(timeout=3)
        assert errors and "Verbindung" in errors[0]
    finally:
        bridge.close()
