import ctypes
from ctypes import wintypes
import sys
import threading

import psutil

BROWSERS = {'opera.exe', 'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe',
            'vivaldi.exe', 'chromium.exe', 'waterfox.exe', 'librewolf.exe'}


def api():
    if sys.platform != 'win32':
        return None
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    return user


def process_name(user, hwnd):
    if not hwnd:
        return ''
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except (psutil.Error, OSError):
        return ''


def close_browser_windows():
    user = api()
    if not user:
        return 0
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    windows = []

    @callback_type
    def collect(hwnd, _):
        if user.IsWindowVisible(hwnd) and process_name(user, hwnd) in BROWSERS:
            windows.append(hwnd)
        return True

    user.EnumWindows(collect, 0)
    return sum(bool(user.PostMessageW(hwnd, 0x0010, 0, 0)) for hwnd in windows)


class ForegroundMonitor(threading.Thread):
    def __init__(self, settings, emit):
        super().__init__(daemon=True, name='LeagueForeground')
        self.settings, self.emit = settings, emit
        self.stopped = threading.Event()

    def stop(self):
        self.stopped.set()

    def run(self):
        user = api()
        if not user:
            return
        previous = False
        while not self.stopped.is_set():
            enabled = self.settings.snapshot()['weak_pc_mode']
            current = enabled and process_name(user, user.GetForegroundWindow()) == 'league of legends.exe'
            if current and not previous:
                self.emit({'type': 'game_foreground'})
            previous = current
            self.stopped.wait(0.4 if enabled else 1)