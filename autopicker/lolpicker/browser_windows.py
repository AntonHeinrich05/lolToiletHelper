import ctypes
from ctypes import wintypes
import logging
import sys
import threading
import time

import psutil

LOG = logging.getLogger(__name__)
BROWSERS = {'opera.exe', 'opera_gx.exe', 'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe',
            'vivaldi.exe', 'chromium.exe', 'waterfox.exe', 'librewolf.exe'}
GAME_CLASS = 'riotwindowclass'
GAME_TITLE = 'league of legends (tm) client'


def api():
    if sys.platform != 'win32':
        return None
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.BringWindowToTop.argtypes = [wintypes.HWND]
    user.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    user.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_void_p]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.PostMessageW.restype = wintypes.BOOL
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


def window_text(user, hwnd, getter):
    buffer = ctypes.create_unicode_buffer(256)
    getter(hwnd, buffer, 256)
    return buffer.value.lower()


def is_game_window(user, hwnd):
    """The game itself (not the client): Riot window class/title works even if the process is protected."""
    if not hwnd:
        return False
    if window_text(user, hwnd, user.GetClassNameW) == GAME_CLASS:
        return True
    if GAME_TITLE in window_text(user, hwnd, user.GetWindowTextW):
        return True
    return process_name(user, hwnd) == 'league of legends.exe'


def browser_windows(user):
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    windows = []

    @callback_type
    def collect(hwnd, _):
        if user.IsWindowVisible(hwnd) and window_text(user, hwnd, user.GetWindowTextW) and process_name(user, hwnd) in BROWSERS:
            windows.append(hwnd)  # EnumWindows yields z-order: the most recently used window first
        return True

    user.EnumWindows(collect, 0)
    return windows


def force_foreground(user, hwnd):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    current = kernel.GetCurrentThreadId()
    foreground = user.GetForegroundWindow()
    threads = {user.GetWindowThreadProcessId(h, None) for h in (foreground, hwnd) if h} - {0, current}
    user.AllowSetForegroundWindow(0xFFFFFFFF)
    # A short Alt tap lets Windows accept SetForegroundWindow from a background process.
    user.keybd_event(0x12, 0, 0, None)
    user.keybd_event(0x12, 0, 2, None)
    for thread in threads:
        user.AttachThreadInput(current, thread, True)
    try:
        if user.IsIconic(hwnd):
            user.ShowWindow(hwnd, 9)
        user.BringWindowToTop(hwnd)
        user.SetForegroundWindow(hwnd)
    finally:
        for thread in threads:
            user.AttachThreadInput(current, thread, False)
    return user.GetForegroundWindow() == hwnd


def focus_browser_window(hint='', timeout=1.5):
    """Bring the browser window showing Lolalytics (title hint) to the front; falls back to the top browser window."""
    user = api()
    if not user:
        return False
    deadline = time.monotonic() + timeout
    target = None
    while time.monotonic() < deadline:
        windows = browser_windows(user)
        for hwnd in windows:
            title = window_text(user, hwnd, user.GetWindowTextW)
            if 'lolalytics' in title or (hint and hint in title):
                target = hwnd
                break
        if target or not windows:
            break
        target = windows[0]
        time.sleep(0.15)
        if 'lolalytics' in window_text(user, target, user.GetWindowTextW):
            break
    if not target:
        LOG.info('Kein Browserfenster zum Fokussieren gefunden')
        return False
    ok = force_foreground(user, target)
    LOG.info('Browser in den Vordergrund: %s (%s)', 'ok' if ok else 'verweigert', window_text(user, target, user.GetWindowTextW)[:60])
    return ok


def close_browser_windows(only_lolalytics=True):
    """WM_CLOSE to browser top-level windows (no focus change). only_lolalytics: windows whose title shows Lolalytics;
    otherwise every browser window ('Ganze Browser'). Returns the number of windows asked to close; 0 without Win32."""
    user = api()
    if not user:
        return 0
    count = 0
    for hwnd in browser_windows(user):
        title = window_text(user, hwnd, user.GetWindowTextW).lower()
        if only_lolalytics and 'lolalytics' not in title:
            continue
        if user.PostMessageW(hwnd, 0x0010, 0, 0):
            count += 1
            LOG.info('Browserfenster geschlossen (WM_CLOSE): %s', title[:60])
    return count


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
            current = enabled and is_game_window(user, user.GetForegroundWindow())
            if current and not previous:
                LOG.info('Spiel im Vordergrund erkannt (Schwacher-PC-Modus): Lolalytics-Tabs werden geschlossen')
                self.emit({'type': 'game_foreground'})
            previous = current
            self.stopped.wait(0.4 if enabled else 1)
