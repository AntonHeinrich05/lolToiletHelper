"""Windows RegisterHotKey, not a global keyboard hook or key logger."""
import ctypes
import queue
import sys
import threading
from ctypes import wintypes

MODS = {"alt": 1, "ctrl": 2, "shift": 4, "win": 8, "cmd": 8}
SPECIAL = {"space": 32, "enter": 13, "tab": 9, "backspace": 8,
           "delete": 46, "insert": 45, "home": 36, "end": 35,
           "page_up": 33, "page_down": 34, "left": 37, "up": 38,
           "right": 39, "down": 40}


def parse_combo(combo):
    if not isinstance(combo, str) or not combo:
        raise ValueError("Kein Kürzel gesetzt")
    parts = [p.strip().strip("<>").lower() for p in combo.split("+")]
    mods = 0
    for part in parts[:-1]:
        if part not in MODS or mods & MODS[part]:
            raise ValueError("Ungültige Modifier")
        mods |= MODS[part]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif key in SPECIAL:
        vk = SPECIAL[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 111 + int(key[1:])
    else:
        raise ValueError("Buchstaben, Ziffern, F-Tasten oder Navigationstasten verwenden")
    if vk == 123:
        raise ValueError("F12 ist für Windows-Debugger reserviert")
    if not mods and not 112 <= vk <= 135:
        raise ValueError("Mindestens Alt, Strg, Shift oder Win verwenden")
    return mods, vk


def combo_from_event(event, windows=None):
    """Windows Tk keycode is the virtual key: Shift+1 = VK_1, never '!'."""
    if windows is None:
        windows = sys.platform == "win32"
    vk = event.keycode if windows else None
    if vk is None:
        key = event.keysym.lower()
        if key in ("exclam", "!"):
            key = "1"
        if len(key) == 1 and key.isascii() and key.isalnum():
            vk = ord(key.upper())
        elif key.startswith("f") and key[1:].isdigit():
            vk = 111 + int(key[1:])
        else:
            vk = SPECIAL.get(key)
    if vk in (16, 17, 18, 20, 91, 92, 144, 160, 161, 162, 163, 164, 165) or vk is None:
        return None
    mods = []
    # Use actual modifier state on Windows; avoid Tk's layout-dependent Alt bits.
    if windows and sys.platform == "win32":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        flags = {"ctrl": user32.GetKeyState(17) & 0x8000,
                 "alt": user32.GetKeyState(18) & 0x8000,
                 "shift": user32.GetKeyState(16) & 0x8000,
                 "win": (user32.GetKeyState(91) | user32.GetKeyState(92)) & 0x8000}
    else:
        flags = {"ctrl": event.state & 4, "alt": event.state & (0x20000 | 8), "shift": event.state & 1}
    mods.extend(f"<{k}>" for k, active in flags.items() if active)
    if 48 <= vk <= 57 or 65 <= vk <= 90:
        key = chr(vk).lower()
    elif 112 <= vk <= 135:
        key = f"<f{vk - 111}>"
    else:
        key = next((f"<{name}>" for name, code in SPECIAL.items() if code == vk), "")
    if not key:
        raise ValueError("Diese Taste wird nicht unterstützt")
    combo = "+".join(mods + [key])
    parse_combo(combo)
    return combo


def display_combo(combo):
    return combo.replace("<", "").replace(">", "").replace("+", " + ").upper() or "Nicht belegt"


class Hotkeys:
    """Dedicated Win32 message thread; Tk must not consume WM_HOTKEY first.

    Registrations and removal happen on their owning thread. Only callback
    dispatch runs on Tk, through an ordinary bounded Python queue.
    """
    def __init__(self, root, callback):
        self.root, self.callback = root, callback
        self.bindings, self.ids = {}, {}
        self.suspended, self.closed = False, False
        self.generation = 0
        self.commands = queue.Queue()
        self.events = queue.Queue(maxsize=32)
        self.worker = None
        self.user32 = ctypes.WinDLL("user32", use_last_error=True) if sys.platform == "win32" else None
        if self.user32:
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self.worker = threading.Thread(target=self._message_loop, name="WindowsHotkeys", daemon=True)
            self.worker.start()
            self.root.after(50, self.poll)

    def _clear(self):
        if self.user32 and not self.closed:
            self._submit("clear")

    def _clear_native(self):
        if self.user32:
            for identifier in self.ids:
                self.user32.UnregisterHotKey(None, identifier)
        self.ids.clear()
        self.generation += 1
        msg = wintypes.MSG()
        while self.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
            pass  # queued events from the previous bindings are invalid now

    def _register(self, bindings):
        for i, (action, combo) in enumerate(bindings.items(), 1):
            if not combo:
                continue
            mods, vk = parse_combo(combo)
            if not self.user32.RegisterHotKey(None, i, mods | 0x4000, vk):
                raise ValueError(f"{display_combo(combo)} wird bereits verwendet oder ist reserviert")
            self.ids[i] = action

    def apply(self, bindings):
        parsed = [parse_combo(c) for c in bindings.values() if c]
        if len(set(parsed)) != len(parsed):
            raise ValueError("Dieses Kürzel ist bereits einer anderen Aktion zugeordnet")
        if not self.user32:
            raise ValueError("Globale Kürzel sind nur unter Windows verfügbar")
        self._submit("apply", bindings.copy())

    def _apply_native(self, bindings):
        old = self.bindings.copy()
        self._clear_native()
        try:
            self._register(bindings)
        except ValueError as error:
            self._clear_native()
            try:
                self._register(old)
            except ValueError:
                self._clear_native()
                self.bindings = {}
                raise ValueError(f"{error}; bisherige Kürzel konnten nicht wiederhergestellt werden") from error
            raise
        self.bindings = bindings.copy()

    def _submit(self, operation, bindings=None):
        if self.closed:
            return
        done, result, cancelled = threading.Event(), [], threading.Event()
        self.commands.put((operation, bindings, done, result, cancelled))
        if not done.wait(3):
            cancelled.set()
            raise ValueError("Windows-Kürzel antworten nicht; Anwendung neu starten")
        if result:
            raise ValueError(result[0])

    def _message_loop(self):
        msg = wintypes.MSG()
        # Create the thread's message queue before the first registration.
        self.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 0)
        while True:
            try:
                operation, bindings, done, result, cancelled = self.commands.get(timeout=0.025)
                try:
                    if not cancelled.is_set():
                        if operation == "apply":
                            self._apply_native(bindings)
                        else:
                            self._clear_native()
                except ValueError as error:
                    result.append(str(error))
                finally:
                    done.set()
                if operation == "close":
                    return
            except queue.Empty:
                pass
            while self.user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                action = self.ids.get(msg.wParam)
                if action:
                    try:
                        self.events.put_nowait((self.generation, action))
                    except queue.Full:
                        pass

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                generation, action = self.events.get_nowait()
            except queue.Empty:
                break
            if generation == self.generation and not self.suspended:
                self.callback(action)
        self.root.after(50, self.poll)

    def close(self):
        if self.user32 and not self.closed:
            try:
                self._submit("close")
            except ValueError:
                pass
        self.closed = True
        if self.worker:
            self.worker.join(timeout=0.5)