"""Browser-launched host. stdout is exclusively length-prefixed JSON."""
import os
import socket
import sys
import threading
from lolpicker.protocol import receive, frame
from lolpicker.storage import data_dir, read_json


def main():
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    config = read_json(data_dir() / "bridge-session.json", {})
    port, token = config.get("port"), config.get("token")
    if type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str):
        return
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
            sock.settimeout(None)
            sock.sendall(frame({"token": token}))

            def browser_to_app():
                try:
                    while True:
                        sock.sendall(frame(receive(sys.stdin.buffer.read)))
                except (OSError, EOFError, ValueError):
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            threading.Thread(target=browser_to_app, daemon=True).start()
            while True:
                message = receive(sock.recv)
                sys.stdout.buffer.write(frame(message))
                sys.stdout.buffer.flush()
    except (OSError, EOFError, ValueError):
        return


if __name__ == "__main__":
    main()