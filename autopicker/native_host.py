import os
import socket
import sys
import threading
import time

from lolpicker.protocol import receive, frame
from lolpicker.storage import data_dir, read_json


class NativeRelay:
    def __init__(self, reader, writer, directory, interval=0.25):
        self.reader, self.writer = reader, writer
        self.path = directory / 'bridge-session.json'
        self.interval = interval
        self.stopped = threading.Event()
        self.hello_ready = threading.Event()
        self.write_lock = threading.Lock()
        self.socket_lock = threading.RLock()
        self.sock = None
        self.hello = None

    def output(self, message):
        with self.write_lock:
            try:
                self.writer.write(frame(message))
                self.writer.flush()
            except (OSError, ValueError):
                self.stop()

    def stop(self):
        self.stopped.set()
        with self.socket_lock:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def input_loop(self):
        try:
            while not self.stopped.is_set():
                message = receive(self.reader.read)
                if message.get('event') == 'hello':
                    self.hello = message
                    self.hello_ready.set()
                    continue
                sent = False
                with self.socket_lock:
                    if self.sock:
                        try:
                            self.sock.sendall(frame(message))
                            sent = True
                        except OSError:
                            try:
                                self.sock.shutdown(socket.SHUT_RDWR)
                            except OSError:
                                pass
                if not sent and message.get('id'):
                    self.output({'reply_to': message['id'], 'ok': False, 'error': 'Autopicker verbindet sich gerade'})
        except (OSError, EOFError, ValueError):
            self.stop()

    def run(self):
        threading.Thread(target=self.input_loop, name='BrowserInput', daemon=True).start()
        self.output({'event': 'bridge_status', 'connected': False})
        while not self.stopped.is_set() and not self.hello_ready.wait(self.interval):
            pass
        previous = None
        config = {}
        retry_at = 0
        while not self.stopped.is_set():
            try:
                stat = self.path.stat()
                stamp = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
            except OSError:
                stamp = None
            if stamp != previous:
                previous = stamp
                config = read_json(self.path, {}) if stamp else {}
                retry_at = 0
            port, token = config.get('port'), config.get('token')
            valid = type(port) is int and 1 <= port <= 65535 and isinstance(token, str)
            if not valid or time.monotonic() < retry_at:
                self.stopped.wait(self.interval)
                continue
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
                    sock.settimeout(3)
                    sock.sendall(frame({'token': token}))
                    sock.sendall(frame(self.hello))
                    initial = receive(sock.recv)
                    if initial.get('event') != 'context':
                        raise ValueError('Ungültiger Handshake')
                    sock.settimeout(None)
                    with self.socket_lock:
                        self.sock = sock
                    self.output(initial)
                    while not self.stopped.is_set():
                        self.output(receive(sock.recv))
            except (OSError, EOFError, ValueError):
                pass
            finally:
                with self.socket_lock:
                    self.sock = None
            if not self.stopped.is_set():
                self.output({'event': 'bridge_status', 'connected': False})
                retry_at = time.monotonic() + 1
                self.stopped.wait(self.interval)


def main():
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    NativeRelay(sys.stdin.buffer, sys.stdout.buffer, data_dir()).run()


if __name__ == '__main__':
    main()