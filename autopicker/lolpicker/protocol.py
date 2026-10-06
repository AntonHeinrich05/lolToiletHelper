"""Bounded native messaging framing for streams and loopback sockets."""
import json
import struct

MAX_FRAME = 256 * 1024


def exact(read, size):
    parts = bytearray()
    while len(parts) < size:
        part = read(size - len(parts))
        if not part:
            raise EOFError("Verbindung beendet")
        parts.extend(part)
    return bytes(parts)


def receive(read):
    size = struct.unpack("<I", exact(read, 4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Nachricht zu groß")
    obj = json.loads(exact(read, size).decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("JSON-Objekt erwartet")
    return obj


def frame(obj):
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not 0 < len(data) <= MAX_FRAME:
        raise ValueError("Nachricht zu groß")
    return struct.pack("<I", len(data)) + data