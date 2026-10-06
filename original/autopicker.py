import tkinter as tk
import threading
import queue
import asyncio
import webbrowser
import sys
import os
import json
import time
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pynput import keyboard
from pynput.keyboard import Controller as KbController, Key as KbKey
from lcu_driver import Connector

# =============================================================
# Windows-only: Win32-API via ctypes (robustes HWND-Tracking)
# =============================================================
import ctypes
from ctypes import wintypes

_IS_WINDOWS = sys.platform.startswith('win')

if _IS_WINDOWS:
    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _WM_CLOSE = 0x0010
    _SW_RESTORE = 9
    _GW_OWNER = 4
    _VK_CONTROL = 0x11
    _VK_W = 0x57
    _VK_MENU = 0x12     # Alt
    _VK_SHIFT = 0x10
    _KEYEVENTF_KEYUP = 0x0002

    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.IsWindow.restype = wintypes.BOOL
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    _user32.PostMessageW.restype = wintypes.BOOL
    _user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint,
                                     wintypes.WPARAM, wintypes.LPARAM]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetForegroundWindow.argtypes = []
    _user32.AttachThreadInput.restype = wintypes.BOOL
    _user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                 ctypes.POINTER(wintypes.DWORD)]
    _user32.BringWindowToTop.restype = wintypes.BOOL
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.keybd_event.restype = None
    _user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte,
                                    wintypes.DWORD, ctypes.c_void_p]
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _kernel32.GetCurrentThreadId.argtypes = []


def _get_window_title(hwnd):
    if not _IS_WINDOWS:
        return ""
    try:
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def _enum_top_level_hwnds():
    """Schnappschuss aller sichtbaren Top-Level-Fenster mit Titel."""
    hwnds = set()
    if not _IS_WINDOWS:
        return hwnds

    def _cb(hwnd, lparam):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True
            # Nur echte Top-Level-Fenster (kein Owner)
            if _user32.GetWindow(hwnd, _GW_OWNER):
                return True
            if _user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            hwnds.add(int(hwnd))
        except Exception:
            pass
        return True

    try:
        _user32.EnumWindows(_EnumWindowsProc(_cb), 0)
    except Exception:
        pass
    return hwnds


def _hwnd_alive(hwnd):
    if not _IS_WINDOWS or not hwnd:
        return False
    try:
        return bool(_user32.IsWindow(hwnd))
    except Exception:
        return False


def _hwnd_focus(hwnd):
    """Aggressives Foreground-Bringen via AttachThreadInput-Trick.
    Standard SetForegroundWindow scheitert oft, wenn unser Prozess nicht im
    Vordergrund ist - der Trick haengt unseren Thread an den FG-Thread,
    dann darf Windows den Fokus tauschen.
    """
    if not _IS_WINDOWS or not hwnd:
        return False
    try:
        fg = _user32.GetForegroundWindow()
        if fg == hwnd:
            try:
                _user32.ShowWindow(hwnd, _SW_RESTORE)
            except Exception:
                pass
            return True
        cur_tid = _kernel32.GetCurrentThreadId()
        fg_tid = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        if fg_tid and fg_tid != cur_tid:
            try:
                attached = bool(_user32.AttachThreadInput(cur_tid, fg_tid, True))
            except Exception:
                attached = False
        try:
            _user32.ShowWindow(hwnd, _SW_RESTORE)
            _user32.BringWindowToTop(hwnd)
            _user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                try:
                    _user32.AttachThreadInput(cur_tid, fg_tid, False)
                except Exception:
                    pass
        # Bestaetigen
        try:
            return _user32.GetForegroundWindow() == hwnd
        except Exception:
            return True
    except Exception:
        return False


def _send_ctrl_w_winapi():
    """Sendet Ctrl+W via keybd_event - geht an das aktuelle Vordergrund-Fenster,
    umgeht die pynput-Listener-Kette."""
    if not _IS_WINDOWS:
        return False
    try:
        _user32.keybd_event(_VK_CONTROL, 0, 0, None)
        _user32.keybd_event(_VK_W,       0, 0, None)
        time.sleep(0.02)
        _user32.keybd_event(_VK_W,       0, _KEYEVENTF_KEYUP, None)
        _user32.keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, None)
        return True
    except Exception:
        return False


def _release_modifiers_winapi():
    """Stellt via keybd_event sicher, dass Alt/Shift/Ctrl 'oben' sind."""
    if not _IS_WINDOWS:
        return
    for vk in (_VK_MENU, _VK_SHIFT, _VK_CONTROL):
        try:
            _user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, None)
        except Exception:
            pass


def _hwnd_close(hwnd):
    """Schliesst das Fenster ueber WM_CLOSE - kein Fokus noetig."""
    if not _IS_WINDOWS or not hwnd:
        return False
    try:
        return bool(_user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0))
    except Exception:
        return False


# =============================================================
# UI Automation (optional) - liest die Adressleiste eines Browsers
# OHNE Fokuswechsel / Tastatur / Clipboard. Pures Lesen via COM.
# Benoetigt 'comtypes' (pip install comtypes). Ist es nicht
# installiert, faellt die Funktion still aus (keine Tracking-Updates).
# =============================================================
_UIA_AVAILABLE = False
_UIA = None
_UIA_ERR = None
if _IS_WINDOWS:
    try:
        import comtypes  # noqa: F401
        import comtypes.client as _cc  # type: ignore
        # Generiert ./gen/ Module beim ersten Lauf - das ist normal.
        _UIA_TYPELIB = _cc.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import (  # type: ignore
            CUIAutomation, IUIAutomation,
            UIA_ValueValuePropertyId,
            UIA_ControlTypePropertyId,
            UIA_NamePropertyId,
            UIA_EditControlTypeId,
            TreeScope_Descendants,
        )
        _UIA = _cc.CreateObject(CUIAutomation, interface=IUIAutomation)
        _UIA_AVAILABLE = True
    except Exception as _e:  # noqa: BLE001
        _UIA_ERR = str(_e)
        _UIA_AVAILABLE = False


def _uia_read_browser_url(hwnd):
    """Liest die URL aus der Adressleiste des Browserfensters per UI Automation.
    Kein Fokus, kein Clipboard, kein Tastendruck. Gibt None zurueck, falls
    nicht ermittelbar (z. B. comtypes fehlt, falsches Fenster, ...).
    """
    if not _UIA_AVAILABLE or not hwnd:
        return None
    try:
        root = _UIA.ElementFromHandle(hwnd)
        if not root:
            return None
        # Bedingung: ControlType == Edit
        cond = _UIA.CreatePropertyCondition(UIA_ControlTypePropertyId,
                                            UIA_EditControlTypeId)
        edits = root.FindAll(TreeScope_Descendants, cond)
        if not edits:
            return None
        # Heuristik: Adressleiste hat im Namen 'Adress' / 'URL' / 'address'
        # und ihr Value beginnt mit http
        best = None
        for i in range(edits.Length):
            el = edits.GetElement(i)
            try:
                name = (el.CurrentName or '').lower()
            except Exception:
                name = ''
            try:
                val = el.GetCurrentPropertyValue(UIA_ValueValuePropertyId) or ''
            except Exception:
                val = ''
            if not isinstance(val, str):
                continue
            if val.startswith('http'):
                # Adress-Edit erkennen
                if ('adress' in name or 'address' in name or 'url' in name
                        or 'standort' in name or 'omnibox' in name):
                    return val
                if best is None:
                    best = val
        return best
    except Exception:
        return None


def _foreground_title():
    if not _IS_WINDOWS:
        return ""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return ""
        return _get_window_title(hwnd)
    except Exception:
        return ""


# =============================================================
# Prozessname des Vordergrund-Fensters lesen (League Client vs. Game
# unterscheiden). LeagueClientUx.exe = Client/Launcher,
# "League of Legends.exe" = laufendes Spiel.
# =============================================================
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

if _IS_WINDOWS:
    try:
        _kernel32.OpenProcess.restype = wintypes.HANDLE
        _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                          wintypes.DWORD]
        _kernel32.CloseHandle.restype = wintypes.BOOL
        _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        _kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)
        ]
    except Exception:
        pass


def _foreground_process_name():
    """Gibt den Basename der EXE des aktuellen Vordergrund-Prozesses zurueck
    (z. B. 'League of Legends.exe', 'LeagueClientUx.exe', 'chrome.exe').
    Leerstring, wenn nicht ermittelbar.
    """
    if not _IS_WINDOWS:
        return ""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        h = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION,
                                  False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            ok = _kernel32.QueryFullProcessImageNameW(h, 0, buf,
                                                     ctypes.byref(size))
            if not ok:
                return ""
            return os.path.basename(buf.value or "")
        finally:
            try:
                _kernel32.CloseHandle(h)
            except Exception:
                pass
    except Exception:
        return ""


# =============================================================
# Default-Browser EXE finden + URL in NEUEM Fenster oeffnen.
# Grund: Wenn der Browser bereits offen ist, oeffnet webbrowser.open()
# den Link i. d. R. nur als Tab im bestehenden Fenster. Wir bekommen
# dadurch KEIN eigenes HWND -> Schliessen + URL-Tracking versagen.
# Loesung: subprocess + browser-spezifisches "--new-window" Flag.
# =============================================================
def _find_default_browser_exe():
    """Liest den Default-Browser aus der Windows-Registry und gibt den
    absoluten Pfad zur EXE zurueck. Gibt None zurueck wenn nicht ermittelbar."""
    if not _IS_WINDOWS:
        return None
    try:
        import winreg  # nur unter Windows verfuegbar
    except ImportError:
        return None
    try:
        # 1) Benutzer-Wahl fuer https
        progid = None
        try:
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\Shell\Associations\URLAssociations\https\UserChoice'
            ) as k:
                progid, _ = winreg.QueryValueEx(k, 'ProgId')
        except OSError:
            progid = None
        # 2) Falls keine UserChoice -> http versuchen
        if not progid:
            try:
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r'Software\Microsoft\Windows\Shell\Associations\URLAssociations\http\UserChoice'
                ) as k:
                    progid, _ = winreg.QueryValueEx(k, 'ProgId')
            except OSError:
                progid = None
        if not progid:
            return None
        # 3) ProgId -> shell\open\command
        try:
            with winreg.OpenKey(
                    winreg.HKEY_CLASSES_ROOT,
                    rf'{progid}\shell\open\command') as k:
                cmd, _ = winreg.QueryValueEx(k, None)
        except OSError:
            return None
        if not cmd:
            return None
        # 4) erste Komponente aus dem Command-String holen
        cmd = cmd.strip()
        if cmd.startswith('"'):
            end = cmd.find('"', 1)
            if end > 0:
                exe = cmd[1:end]
            else:
                exe = cmd[1:]
        else:
            # bis zum ersten Space
            exe = cmd.split(' ', 1)[0]
        exe = os.path.expandvars(exe)
        if os.path.isfile(exe):
            return exe
        return None
    except Exception:
        return None


def _browser_kind_from_exe(exe_path):
    """Liefert eine Kennung fuer den Browser (chrome/edge/firefox/brave/opera/vivaldi/arc)
    anhand des EXE-Pfads. Wird fuer das passende --new-window Flag gebraucht."""
    if not exe_path:
        return None
    n = os.path.basename(exe_path).lower()
    if 'firefox' in n:        return 'firefox'
    if 'chrome' in n:         return 'chrome'
    if 'msedge' in n or 'edge' in n: return 'edge'
    if 'brave' in n:          return 'brave'
    if 'opera' in n:          return 'opera'
    if 'vivaldi' in n:        return 'vivaldi'
    if 'arc' in n:            return 'arc'
    if 'chromium' in n:       return 'chromium'
    return 'unknown'


def _open_url_new_window(url):
    """Oeffnet URL in einem NEUEN Browserfenster. Gibt (True, popen_obj) zurueck
    wenn ein spezifisches Browser-EXE genutzt wurde (zuverlaessiges neues
    Fenster). Bei Fehlschlag (False, None). Praeferiert Default-Browser, sonst
    probiert bekannte Browser-Pfade der Reihe nach durch.
    """
    if not _IS_WINDOWS or not url:
        return (False, None)
    import subprocess
    exe = _find_default_browser_exe()
    candidates = []
    if exe:
        candidates.append(exe)
    pf  = os.environ.get('ProgramFiles', r'C:\Program Files')
    pf86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    la  = os.environ.get('LocalAppData',
                         os.path.expanduser(r'~\AppData\Local'))
    for p in [
        rf'{pf}\Google\Chrome\Application\chrome.exe',
        rf'{pf86}\Google\Chrome\Application\chrome.exe',
        rf'{la}\Google\Chrome\Application\chrome.exe',
        rf'{pf}\Microsoft\Edge\Application\msedge.exe',
        rf'{pf86}\Microsoft\Edge\Application\msedge.exe',
        rf'{pf}\BraveSoftware\Brave-Browser\Application\brave.exe',
        rf'{pf86}\BraveSoftware\Brave-Browser\Application\brave.exe',
        rf'{pf}\Mozilla Firefox\firefox.exe',
        rf'{pf86}\Mozilla Firefox\firefox.exe',
    ]:
        if p not in candidates and os.path.isfile(p):
            candidates.append(p)

    for exe_path in candidates:
        kind = _browser_kind_from_exe(exe_path)
        if kind == 'firefox':
            args = [exe_path, '-new-window', url]
        elif kind in ('chrome', 'edge', 'brave', 'opera', 'vivaldi',
                      'chromium', 'arc', 'unknown'):
            args = [exe_path, '--new-window', url]
        else:
            args = [exe_path, url]
        try:
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            proc = subprocess.Popen(
                args,
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return (True, proc)
        except Exception:
            continue
    return (False, None)


def _hwnd_pid(hwnd):
    """Gibt die PID des Fensters zurueck (oder 0)."""
    if not _IS_WINDOWS or not hwnd:
        return 0
    try:
        pid = wintypes.DWORD(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return 0


# === State-Datei fuer Persistenz der zuletzt geoeffneten URL (Build/Items merken) ===
def _state_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
    return os.path.join(base, "lol_tool_state.json")


LOL_TITLE_HINTS = ("League of Legends",)
# EXE-Name des LAUFENDEN SPIELS (nicht des Clients/Launchers).
# Wir wollen Auto-Close nur waehrend des aktiven Matches, nicht im
# Client / Lobby / Champ-Select.
LOL_GAME_EXE = "League of Legends.exe"

# Browser-Erkennung (fuer "alle Browser schliessen")
BROWSER_TITLE_KEYWORDS = ('chrome', 'firefox', 'edge', 'brave', 'opera',
                          'vivaldi', 'mozilla', 'arc', 'chromium')

# Debug-Log-Datei (wird nur befuellt, wenn Debug-Modus AN)
def _debug_log_path():
    base = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
    return os.path.join(base, "lol_tool_debug.log")

# Standard-Hotkeys (anpassbar im Settings-Fenster, gespeichert in der Config)
DEFAULT_HOTKEYS = {
    'toggle_overlay':      '<alt>+q',
    'open_lolalytics':     '<alt>+<shift>+1',
    'open_vs':             '<alt>+<shift>+2',
    'close_tab':           '<alt>+<shift>+3',
    'close_all_browsers':  '<alt>+<shift>+4',
}

HOTKEY_LABELS = {
    'toggle_overlay':      'Overlay ein/aus',
    'open_lolalytics':     'Lolalytics oeffnen',
    'open_vs':             'VS-Matchup oeffnen',
    'close_tab':           'Tab schliessen',
    'close_all_browsers':  'Alle Browser schliessen',
}

# Alt-Layout (vor Einfuehrung des VS-Buttons). Wird genutzt um beim Laden
# alter Configs eine sanfte Migration zu machen, ohne User-Anpassungen
# zu zerstoeren.
_LEGACY_HOTKEYS_V8 = {
    'toggle_overlay':      '<alt>+q',
    'open_lolalytics':     '<alt>+<shift>+1',
    'close_tab':           '<alt>+<shift>+2',
    'close_all_browsers':  '<alt>+<shift>+3',
}


# Queue-IDs ohne Lane-Konzept -> VS-Button bleibt aus (ARAM + Arena).
# 450, 2400 = ARAM / ARAM-Varianten; 1700, 1710, 1750 = Arena.
VS_DISABLED_QUEUES = {450, 2400, 1700, 1710, 1750}


def setup_autostart():
    startup_dir = os.path.join(os.environ['APPDATA'],
                               r'Microsoft\Windows\Start Menu\Programs\Startup')
    bat_path = os.path.join(startup_dir, 'LoLHelper.bat')
    if os.path.exists(bat_path):
        return
    target_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
    with open(bat_path, 'w') as f:
        f.write(f'@echo off\nstart "" "{target_path}"')


class LCUBackend(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.connector = Connector()

    def run(self):
        @self.connector.ready
        async def on_connect(connection):
            self.app.data_queue.put({"type": "status", "connected": True})
            phase_cache = None
            select_cache = (0, '', ())
            lobby_cache = None
            auto_pick_done = False
            auto_ban_done = False
            self._preselected_champ = None   # NEU: Preselection-Tracking

            while True:
                try:
                    phase_resp = await connection.request('get', '/lol-gameflow/v1/gameflow-phase')
                    phase = await phase_resp.json()
                    if phase != phase_cache:
                        if phase_cache == 'ChampSelect' and phase != 'ChampSelect':
                            auto_pick_done = False
                            auto_ban_done = False
                            self._preselected_champ = None   # zurücksetzen beim Verlassen
                        phase_cache = phase
                        self.app.data_queue.put({"type": "phase", "phase": phase})
                    if phase == 'Lobby':
                        lobby_resp = await connection.request('get', '/lol-lobby/v2/lobby')
                        lobby = await lobby_resp.json()
                        queue_id = lobby.get('gameConfig', {}).get('queueId', 0)
                        members = len(lobby.get('members', []))
                        if (queue_id, members) != lobby_cache:
                            lobby_cache = (queue_id, members)
                            self.app.data_queue.put({"type": "lobby", "queue_id": queue_id, "members": members})
                    elif phase == 'ReadyCheck':
                        if self.app.auto_ready_enabled:
                            await connection.request('post', '/lol-matchmaking/v1/ready-check/accept')
                    elif phase == 'ChampSelect':
                        session_resp = await connection.request('get', '/lol-champ-select/v1/session')
                        session = await session_resp.json()
                        my_cell = session.get('localPlayerCellId')
                        my_champ = 0
                        my_role = ''
                        for p in session.get('myTeam', []):
                            if p.get('cellId') == my_cell:
                                my_champ = p.get('championId', 0)
                                my_role = p.get('assignedPosition', '')
                                break
                        queue_id = session.get('queueId', 0)

                        # ---------- Gegner-Roster (Rolle -> Champ) ----------
                        # Wir bauen die Liste hier vor, weil wir sie sowohl
                        # fuer den VS-Button (Lane-Gegner) als auch fuer die
                        # bisherige Smart-Indicator/BM-Logik brauchen.
                        actions = session.get('actions', [])
                        enemy_cells = {p.get('cellId') for p in session.get('theirTeam', [])}
                        enemy_roster = []
                        for p in session.get('theirTeam', []):
                            c = p.get('championId', 0) or 0
                            # Wenn championId in theirTeam noch 0 ist, im
                            # Action-Stream nach Hover/Pick fuer diese Zelle
                            # suchen (gibt der Gegner Champ frueh preis).
                            if not c:
                                for ag in actions:
                                    for action in ag:
                                        if (action.get('actorCellId') == p.get('cellId')
                                                and action.get('type') == 'pick'
                                                and action.get('championId', 0)):
                                            c = action['championId']
                                            break
                                    if c:
                                        break
                            enemy_roster.append({
                                'cell_id': p.get('cellId'),
                                'champion_id': c,
                                'role': (p.get('assignedPosition') or '').lower(),
                            })
                        opp_champs = {e['champion_id'] for e in enemy_roster
                                      if e['champion_id']}
                        # plus alle gehoverten gegnerischen Picks (nicht in
                        # myTeam, also in enemy_cells)
                        for ag in actions:
                            for action in ag:
                                if (action.get('actorCellId') in enemy_cells
                                        and action.get('type') == 'pick'
                                        and action.get('championId', 0)):
                                    opp_champs.add(action['championId'])

                        # Cache-Key: Wenn sich auch das Gegner-Roster aendert,
                        # nochmal pushen (damit VS-Button reagiert).
                        enemy_sig = tuple(sorted(
                            (e['role'], e['champion_id']) for e in enemy_roster
                        ))
                        if (my_champ, my_role, enemy_sig) != select_cache:
                            select_cache = (my_champ, my_role, enemy_sig)
                            self.app.data_queue.put({
                                "type": "champ_select",
                                "champion_id": my_champ,
                                "role": my_role,
                                "queue_id": queue_id,
                                "enemy_roster": enemy_roster,
                                "my_cell_id": my_cell,
                                "my_team_cells": [p.get('cellId') for p in session.get('myTeam', [])
                                                  if p.get('cellId') is not None],
                            })
                        for ag in actions:
                            for action in ag:
                                if (action.get('actorCellId') in enemy_cells
                                        and action.get('type') == 'pick'
                                        and action.get('championId', 0)):
                                    opp_champs.add(action['championId'])

                        if self.app.auto_pick_enabled and my_cell is not None:
                            # ---------- KORREKTE TURN-DETECTION ----------
                            # Nur agieren wenn:
                            #   1) timer.phase ist eine aktive Phase (BAN_PICK / FINALIZATION)
                            #   2) eine MEINER Actions isInProgress=true und nicht completed
                            # → funktioniert in allen Modi (Solo/Duo, Draft, Blind, Arena),
                            #   weil wir nicht hardcoden sondern dem LCU-Server vertrauen.

                            # ==================== PRESELECTION (Early Hover) ====================
                            if self.app.auto_pick_champs and not auto_pick_done and my_champ == 0:
                                chosen = None
                                bm = self.app.bad_matchups

                                # 1. Priorität: erster Champ ohne Bad-Matchup
                                for cid in self.app.auto_pick_champs:
                                    if not cid:
                                        continue
                                    bad = set(bm.get(str(cid), []))
                                    if bad & opp_champs:
                                        continue
                                    if self.is_champion_available(session, cid):
                                        chosen = cid
                                        break

                                # 2. Fallback: alle haben BM-Konflikt → ersten verfügbaren nehmen
                                if chosen is None:
                                    for cid in self.app.auto_pick_champs:
                                        if cid and self.is_champion_available(session, cid):
                                            chosen = cid
                                            break

                                # Hover nur setzen, wenn nicht bereits der richtige Champion gehovert ist
                                if chosen is not None:
                                    already_hovered = False
                                    for action_group in actions:
                                        for action in action_group:
                                            if (action.get('actorCellId') == my_cell 
                                                    and action.get('type') == 'pick'
                                                    and action.get('championId') == chosen
                                                    and action.get('completed')):
                                                already_hovered = True
                                                break
                                        if already_hovered:
                                            break

                                    if not already_hovered:
                                        for action_group in actions:
                                            for action in action_group:
                                                if action.get('actorCellId') == my_cell and action.get('type') == 'pick':
                                                    await connection.request(
                                                        'patch',
                                                        f'/lol-champ-select/v1/session/actions/{action["id"]}',
                                                        json={'championId': chosen, 'completed': True}
                                                    )
                                                    break
                                            else:
                                                continue
                                            break
                                    # NEU: Tracken, welcher Champ gerade vorgehovert ist
                                    self._preselected_champ = chosen

                            timer = session.get('timer', {}) or {}
                            timer_phase = timer.get('phase', '')

                            if timer_phase in ('BAN_PICK', 'FINALIZATION'):
                                # Suche MEINE aktive Action
                                my_active = None
                                for ag in actions:
                                    for action in ag:
                                        if (action.get('isInProgress')
                                                and action.get('actorCellId') == my_cell
                                                and not action.get('completed', False)):
                                            my_active = action
                                            break
                                    if my_active:
                                        break

                                if my_active is not None:
                                    action_id = my_active['id']
                                    action_type = my_active.get('type', '')

                                    # ============== BAN ==============
                                    if action_type == 'ban' and self.app.auto_ban_champs and not auto_ban_done:
                                        chosen = None

                                        # Ersten verfügbaren Ban finden
                                        for cid in self.app.auto_ban_champs:
                                            if cid and self.is_champion_available(session, cid):
                                                chosen = cid
                                                break

                                        if chosen is not None:
                                            # Schritt 1: Hover setzen + completed=True
                                            r1 = await connection.request(
                                                'patch',
                                                f'/lol-champ-select/v1/session/actions/{action_id}',
                                                json={
                                                    'championId': chosen,
                                                    'completed': True
                                                }
                                            )

                                            if r1.status < 300:
                                                # Kurz warten damit der Client synced
                                                await asyncio.sleep(0.12)

                                                # Schritt 2: Ban bestätigen
                                                r2 = await connection.request(
                                                    'post',
                                                    f'/lol-champ-select/v1/session/actions/{action_id}/complete'
                                                )

                                                if r2.status < 300:
                                                    auto_ban_done = True

                                    # ============== PICK ==============
                                    elif action_type == 'pick' and self.app.auto_pick_champs and not auto_pick_done:
                                        chosen = None
                                        bm = self.app.bad_matchups

                                        # 1. Versuch: Pick ohne BM-Conflict
                                        for cid in self.app.auto_pick_champs:
                                            if not cid:
                                                continue
                                            bad = set(bm.get(str(cid), []))
                                            if bad & opp_champs:
                                                continue
                                            if self.is_champion_available(session, cid):
                                                chosen = cid
                                                break

                                        # 2. Fallback: alle haben BM-Conflict → ersten verfügbaren nehmen
                                        if chosen is None:
                                            for cid in self.app.auto_pick_champs:
                                                if cid and self.is_champion_available(session, cid):
                                                    chosen = cid
                                                    break

                                        if chosen is not None:
                                            # Schritt 1: Hover + completed setzen
                                            r1 = await connection.request(
                                                'patch',
                                                f'/lol-champ-select/v1/session/actions/{action_id}',
                                                json={'championId': chosen, 'completed': True}
                                            )

                                            if r1.status < 300:
                                                # 100–150ms warten, damit der Client den Hover übernimmt
                                                await asyncio.sleep(0.12)

                                                # Schritt 2: Lock-In
                                                r2 = await connection.request(
                                                    'post',
                                                    f'/lol-champ-select/v1/session/actions/{action_id}/complete'
                                                )

                                                if r2.status < 300:
                                                    auto_pick_done = True

                            # Smart-Indicator: Status pro Auto-Pick (immer, auch wenn nicht dran)
                            status_map = {}
                            for cid in self.app.auto_pick_champs:
                                if not self.is_champion_available(session, cid):
                                    status_map[cid] = 'banned'
                                elif set(self.app.bad_matchups.get(str(cid), [])) & opp_champs:
                                    status_map[cid] = 'bad_matchup'
                                else:
                                    status_map[cid] = 'ok'

                            # NEU: Preselection-Hover in Status-Map einpflegen
                            if my_champ == 0 and self._preselected_champ is not None:
                                preselected = self._preselected_champ
                                # Nur überschreiben, wenn der Champ aktuell 'ok' ist
                                if status_map.get(preselected) == 'ok':
                                    status_map[preselected] = 'hovered'

                            self.app.data_queue.put({"type": "pick_status", "status": status_map})
                    await asyncio.sleep(1)
                except Exception as e:
                    self.app.data_queue.put({"type": "error", "text": str(e)})
                    await asyncio.sleep(5)
        self.connector.start()

    @staticmethod
    def is_champion_available(session, champ_id):
        for team in ('myTeam', 'theirTeam'):
            for p in session.get(team, []):
                if p.get('championId') == champ_id:
                    return False
        bans = session.get('bans', {})
        for ban in bans.get('myTeamBans', []) + bans.get('theirTeamBans', []):
            if ban == champ_id:
                return False
        return True

    @staticmethod
    def is_already_banned(session, champ_id):
        """Prüft NUR ob der Champion gebannt ist (nicht ob jemand ihn gehovert hat)."""
        bans = session.get('bans', {})
        for ban in bans.get('myTeamBans', []) + bans.get('theirTeamBans', []):
            if ban == champ_id:
                return True
        for ag in session.get('actions', []):
            for action in ag:
                if (action.get('type') == 'ban'
                        and action.get('completed', False)
                        and action.get('championId') == champ_id):
                    return True
        return False


CHAMPION_NAMES = {
    1: "Annie", 2: "Olaf", 3: "Galio", 4: "Twisted Fate", 5: "Xin Zhao", 6: "Urgot", 7: "LeBlanc",
    8: "Vladimir", 9: "Fiddlesticks", 10: "Kayle", 11: "Master Yi", 12: "Alistar", 13: "Ryze",
    14: "Sion", 15: "Sivir", 16: "Soraka", 17: "Teemo", 18: "Tristana", 19: "Warwick", 20: "Nunu",
    21: "Miss Fortune", 22: "Ashe", 23: "Tryndamere", 24: "Jax", 25: "Morgana", 26: "Zilean",
    27: "Singed", 28: "Evelynn", 29: "Twitch", 30: "Karthus", 31: "Cho'Gath", 32: "Amumu",
    33: "Rammus", 34: "Anivia", 35: "Shaco", 36: "Dr. Mundo", 37: "Sona", 38: "Kassadin",
    39: "Irelia", 40: "Janna", 41: "Gangplank", 42: "Corki", 43: "Karma", 44: "Taric", 45: "Veigar",
    48: "Trundle", 50: "Swain", 51: "Caitlyn", 53: "Blitzcrank", 54: "Malphite", 55: "Katarina",
    56: "Nocturne", 57: "Maokai", 58: "Renekton", 59: "Jarvan IV", 60: "Elise", 61: "Orianna",
    62: "Wukong", 63: "Brand", 64: "Lee Sin", 67: "Vayne", 68: "Rumble", 69: "Cassiopeia",
    72: "Skarner", 74: "Heimerdinger", 75: "Nasus", 76: "Nidalee", 77: "Udyr", 78: "Poppy",
    79: "Gragas", 80: "Pantheon", 81: "Ezreal", 82: "Mordekaiser", 83: "Yorick", 84: "Akali",
    85: "Kennen", 86: "Garen", 89: "Leona", 90: "Malzahar", 91: "Talon", 92: "Riven", 96: "Kog'Maw",
    98: "Shen", 99: "Lux", 101: "Xerath", 102: "Shyvana", 103: "Ahri", 104: "Graves", 105: "Fizz",
    106: "Volibear", 107: "Rengar", 110: "Varus", 111: "Nautilus", 112: "Viktor", 113: "Sejuani",
    114: "Fiora", 115: "Ziggs", 117: "Lulu", 119: "Draven", 120: "Hecarim", 121: "Kha'Zix",
    122: "Darius", 126: "Jayce", 127: "Lissandra", 131: "Diana", 133: "Quinn", 134: "Syndra",
    136: "Aurelion Sol", 141: "Kayn", 142: "Zoe", 143: "Zyra", 145: "Kai'Sa", 147: "Seraphine",
    150: "Gnar", 154: "Zac", 157: "Yasuo", 161: "Vel'Koz", 163: "Taliyah", 164: "Camille",
    166: "Akshan", 201: "Braum", 202: "Jhin", 203: "Kindred", 895: "Nilah", 222: "Jinx",
    223: "Tahm Kench", 233: "Briar", 234: "Viego", 235: "Senna", 236: "Lucian", 238: "Zed",
    240: "Kled", 245: "Ekko", 246: "Qiyana", 254: "Vi", 266: "Aatrox", 267: "Nami", 268: "Azir",
    350: "Yuumi", 360: "Samira", 412: "Thresh", 420: "Illaoi", 421: "Rek'Sai", 427: "Ivern",
    429: "Kalista", 432: "Bard", 497: "Rakan", 498: "Xayah", 516: "Ornn", 517: "Sylas",
    518: "Neeko", 523: "Aphelios", 526: "Rell", 555: "Pyke", 711: "Vex", 777: "Yone", 800: "Mel",
    804: "Yunara", 875: "Sett", 876: "Lillia", 887: "Gwen", 888: "Renata", 200: "Bel'Veth",
    897: "K'Sante", 902: "Milio", 904: "Zaahen", 950: "Naafiri", 901: "Smolder", 893: "Aurora",
    799: "Ambessa", 910: "Hwei", 221: "Zeri",
}
NAME_TO_ID = {n: i for i, n in CHAMPION_NAMES.items()}
NORM_NAMES = {n.lower().replace(' ', '').replace("'", ''): (n, c) for n, c in NAME_TO_ID.items()}


def find_matches(text):
    """Suchpriorität: 1-2 Zeichen → nur startswith; ab 3 → startswith zuerst, dann substring.
    Alphabetisch sortiert.
    """
    text = text.lower().replace(' ', '').replace("'", '')
    if not text:
        return []
    starts = sorted(
        n for norm, (n, _) in NORM_NAMES.items() if norm.startswith(text)
    )
    if len(text) <= 2:
        return starts
    contains = sorted(
        n for norm, (n, _) in NORM_NAMES.items()
        if text in norm and not norm.startswith(text)
    )
    return starts + contains

PICK_BORDER = "#2ecc71"
BAN_BORDER = "#e74c3c"
BAD_BORDER = "#f1c40f"   # gelb für Bad-Matchups
DRAG_BORDER = "#3a8fd4"
ROW_BG = "#0b0f16"
PICK_PLACEHOLDER = "Auto Picks ..."
BAN_PLACEHOLDER = "Auto Bans ..."
BAD_PLACEHOLDER = "Bad Matchup ..."
PLACEHOLDER_FG = "#6a6a6a"
ACTIVE_FG = "#ffffff"

# Schriftgrößen
FONT_ROW = ("Segoe UI", 7, "bold")
FONT_ROW_SMALL = ("Segoe UI", 6, "bold")
FONT_ENTRY = ("Segoe UI", 7)
FONT_ENTRY_SMALL = ("Segoe UI", 6)


# =============================================================
# Champion-Zeile (Pick / Ban)
# =============================================================
class ChampRow:
    def __init__(self, app, parent, list_type):
        self.app = app
        self.list_type = list_type  # 'pick' oder 'ban'
        self.champ_id = None
        self.border_color = PICK_BORDER if list_type == 'pick' else BAN_BORDER

        self.outer = tk.Frame(parent, bg=self.border_color, bd=1, relief="solid")
        self.inner = tk.Frame(self.outer, bg=ROW_BG)
        self.inner.pack(fill=tk.X, padx=1, pady=1)
        self.lbl = tk.Label(self.inner, text="", bg=ROW_BG, fg="#f0e6d2", font=FONT_ROW)
        self.lbl.pack(side=tk.LEFT)

        # X-Button
        self.del_btn = tk.Label(self.inner, text="✕", bg=ROW_BG, fg="#c8aa6e",
                                font=("Segoe UI", 7), cursor="hand2")
        self.del_btn.pack(side=tk.RIGHT, padx=(2, 0))
        self.del_btn.bind("<Enter>", lambda e: self.del_btn.config(fg="#f0e6d2"))
        self.del_btn.bind("<Leave>", lambda e: self.del_btn.config(fg="#c8aa6e"))
        self.del_btn.bind("<Button-1>", lambda e: self.app._delete_row(self))

        # "..." Button NUR bei Picks (für Bad-Matchups)
        self.dots_btn = None
        if list_type == 'pick':
            self.dots_btn = tk.Label(self.inner, text="…", bg=ROW_BG, fg="#c8aa6e",
                                     font=("Segoe UI", 8, "bold"), cursor="hand2")
            self.dots_btn.pack(side=tk.RIGHT, padx=(2, 0))
            self.dots_btn.bind("<Enter>", lambda e: self.dots_btn.config(fg="#f0e6d2"))
            self.dots_btn.bind("<Leave>", lambda e: self.dots_btn.config(fg="#c8aa6e"))
            self.dots_btn.bind("<Button-1>", lambda e: self.app._toggle_bad_matchups(self))

        # Drag-Bindings + Doppelklick auf outer/inner/lbl (NICHT auf Buttons)
        for w in (self.outer, self.inner, self.lbl):
            w.bind("<ButtonPress-1>", lambda e, r=self: self.app._dnd_start(e, r))
            w.bind("<B1-Motion>", lambda e, r=self: self.app._dnd_motion(e, r))
            w.bind("<ButtonRelease-1>", lambda e, r=self: self.app._dnd_release(e, r))
            w.bind("<Double-Button-1>", lambda e, r=self: self.app._edit_row(r))

        self.edit_entry = None
        self.is_initial_edit_replace = False
        self.edit_list_frame = None
        self.edit_listbox = None

    def set_data(self, champ_id, display_index):
        self.champ_id = champ_id
        name = CHAMPION_NAMES.get(champ_id, "Unbekannt")
        self.lbl.config(text=f"{display_index}. {name}")

    def set_index(self, display_index):
        if self.champ_id is not None:
            name = CHAMPION_NAMES.get(self.champ_id, "Unbekannt")
            self.lbl.config(text=f"{display_index}. {name}")

    def set_dragged(self, dragged):
        self.outer.config(bg=DRAG_BORDER if dragged else self.border_color)

    def destroy(self):
        self.outer.destroy()


# =============================================================
# Bad-Matchup-Zeile (kompakt, gelb, kein Index)
# =============================================================
class BadMatchupRow:
    def __init__(self, app, parent, owner_champ_id):
        self.app = app
        self.owner_champ_id = owner_champ_id  # zu welchem Auto-Pick gehört diese BM
        self.champ_id = None
        self.border_color = BAD_BORDER

        self.outer = tk.Frame(parent, bg=self.border_color, bd=1, relief="solid")
        self.inner = tk.Frame(self.outer, bg=ROW_BG)
        self.inner.pack(fill=tk.X, padx=1, pady=1)
        self.lbl = tk.Label(self.inner, text="", bg=ROW_BG, fg="#f0e6d2", font=FONT_ROW_SMALL)
        self.lbl.pack(side=tk.LEFT, padx=(2, 2))
        self.del_btn = tk.Label(self.inner, text="✕", bg=ROW_BG, fg="#c8aa6e",
                                font=("Segoe UI", 6), cursor="hand2")
        self.del_btn.pack(side=tk.RIGHT, padx=(2, 2))
        self.del_btn.bind("<Enter>", lambda e: self.del_btn.config(fg="#f0e6d2"))
        self.del_btn.bind("<Leave>", lambda e: self.del_btn.config(fg="#c8aa6e"))
        self.del_btn.bind("<Button-1>", lambda e: self.app._delete_bm(self))

        # Drag + Doppelklick zum Edit
        for w in (self.outer, self.inner, self.lbl):
            w.bind("<ButtonPress-1>", lambda e, r=self: self.app._bm_dnd_start(e, r))
            w.bind("<B1-Motion>", lambda e, r=self: self.app._bm_dnd_motion(e, r))
            w.bind("<ButtonRelease-1>", lambda e, r=self: self.app._bm_dnd_release(e, r))
            w.bind("<Double-Button-1>", lambda e, r=self: self.app._edit_bm(r))

        self.edit_entry = None
        self.is_initial_edit_replace = False
        self.edit_list_frame = None
        self.edit_listbox = None

    def set_data(self, champ_id):
        self.champ_id = champ_id
        name = CHAMPION_NAMES.get(champ_id, "Unbekannt")
        self.lbl.config(text=name)

    def set_dragged(self, dragged):
        self.outer.config(bg=DRAG_BORDER if dragged else self.border_color)

    def destroy(self):
        self.outer.destroy()


# =============================================================
# Bad-Matchups-Panel (3 pro Reihe, max 6)
# =============================================================
class BadMatchupsPanel:
    MAX = 6
    PER_ROW = 3

    def __init__(self, app, parent, owner_row):
        self.app = app
        self.owner_row = owner_row  # ChampRow (Pick)
        self.owner_champ_id = owner_row.champ_id
        self.bm_rows = []  # list[BadMatchupRow]

        self.frame = tk.Frame(parent, bg=ROW_BG)
        # Suchfeld
        self.search_frame = tk.Frame(self.frame, bg=ROW_BG)
        self.search_frame.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.entry = tk.Entry(self.search_frame, bg="#1a2a3a", fg=PLACEHOLDER_FG,
                              insertbackground="#ffffff", font=FONT_ENTRY_SMALL,
                              relief="flat", borderwidth=0,
                              selectbackground="#1a2a3a", selectforeground=PLACEHOLDER_FG,
                              highlightthickness=0)
        self.entry.pack(fill=tk.X, padx=2, pady=1)
        self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)

        self.listbox = tk.Listbox(self.search_frame, bg="#0a1a2b", fg="#c8aa6e",
                                  font=FONT_ENTRY_SMALL, height=4, borderwidth=0,
                                  highlightthickness=0, selectbackground="#2a3a4a",
                                  selectforeground="#f0e6d2", activestyle='none',
                                  exportselection=False)
        self.listbox.pack_forget()

        # Grid-Container für die BM-Felder (3 pro Reihe)
        self.grid_frame = tk.Frame(self.frame, bg=ROW_BG)
        self.grid_frame.pack(fill=tk.X, padx=4, pady=(2, 2))

        # Bindings für das Suchfeld (analog zu Haupt-Suchfeld, aber mit eigenem Add)
        self.entry.bind('<KeyPress>', self._on_keypress)
        self.entry.bind('<KeyRelease>', self._on_keyrelease)
        self.entry.bind('<FocusIn>', self._on_focusin)
        self.entry.bind('<FocusOut>', self._on_focusout)
        self.entry.bind('<Button-1>', self._on_click)
        self.entry.bind('<Double-Button-1>', self._on_dblclick)
        self.entry.bind('<Return>', lambda e: self._confirm())
        self.entry.bind('<Down>', lambda e: self.app._listbox_navigate(self.listbox, 1))
        self.entry.bind('<Up>', lambda e: self.app._listbox_navigate(self.listbox, -1))
        self.listbox.bind('<Button-1>', self._on_listbox_click)
        self.listbox.bind('<Double-Button-1>', self._on_listbox_click)

        self._focusout_after = None

    def _on_keypress(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            if event.char and len(event.char) == 1 and event.char.isprintable():
                self.entry.delete(0, tk.END)
                self.entry.config(fg=ACTIVE_FG)
                self.entry.insert(0, event.char)
                self.entry.icursor(1)
                return "break"
            if event.keysym not in ('Tab', 'Escape'):
                return "break"
        return None

    def _on_keyrelease(self, event):
        if self.entry.get() == "":
            if not self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
                self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)
            self.listbox.pack_forget()
            return
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Escape'):
            return
        self._update_suggestions()

    def _on_focusin(self, event):
        if self._focusout_after is not None:
            try: self.app.root.after_cancel(self._focusout_after)
            except Exception: pass
            self._focusout_after = None
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.entry.icursor(0)
        elif self.entry.get().strip():
            self._update_suggestions()

    def _on_focusout(self, event):
        if self._focusout_after is not None:
            try: self.app.root.after_cancel(self._focusout_after)
            except Exception: pass
        self._focusout_after = self.app.root.after(150, self._hide_suggestions)

    def _hide_suggestions(self):
        self.listbox.pack_forget()
        if self.entry.get().strip() == "":
            self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)

    def _on_click(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.app.root.after_idle(lambda: self.entry.icursor(0))
        return None

    def _on_dblclick(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.entry.selection_clear()
            self.entry.icursor(0)
            return "break"
        return None

    def _update_suggestions(self):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.listbox.pack_forget()
            return
        self.listbox.delete(0, tk.END)
        matches = find_matches(self.entry.get())
        if not matches:
            self.listbox.pack_forget()
            return
        if matches:
            num = min(len(matches), 4)
            self.listbox.config(height=num)
            for m in matches[:num]:
                self.listbox.insert(tk.END, m)
            if not self.listbox.winfo_ismapped():
                self.listbox.pack(fill=tk.X, padx=2, pady=(0, 1))
        else:
            self.listbox.pack_forget()
        self.app._resize_window()

    def _on_listbox_click(self, event):
        try:
            idx = self.listbox.nearest(event.y)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)
        except Exception:
            pass
        if self._focusout_after is not None:
            try: self.app.root.after_cancel(self._focusout_after)
            except Exception: pass
            self._focusout_after = None
        self._confirm()
        return "break"

    def _confirm(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
        elif self.listbox.size() > 0:
            name = self.listbox.get(0)
        else:
            name = self.entry.get().strip()
        if name in NAME_TO_ID:
            self.app._add_bm(self, NAME_TO_ID[name])
            self.entry.delete(0, tk.END)
            self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)
            self.listbox.pack_forget()
            self.app._resize_window()

    def rebuild_grid(self):
        # Alle BMs aus dem Grid lösen (nicht destroyen!)
        for bm in self.bm_rows:
            try:
                bm.outer.grid_forget()
                bm.outer.pack_forget()
            except Exception:
                pass
        # Spaltengewichte gleichmäßig verteilen
        for c in range(self.PER_ROW):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="bm")
        # Neu im Grid platzieren (3 pro Reihe)
        for i, bm in enumerate(self.bm_rows):
            r = i // self.PER_ROW
            c = i % self.PER_ROW
            bm.outer.grid(in_=self.grid_frame, row=r, column=c,
                          sticky='ew', padx=1, pady=1)

    def add_row(self, champ_id):
        if len(self.bm_rows) >= self.MAX:
            return
        bm = BadMatchupRow(self.app, self.grid_frame, self.owner_champ_id)
        bm.set_data(champ_id)
        self.bm_rows.append(bm)
        self.rebuild_grid()

    def remove_row(self, bm_row):
        if bm_row in self.bm_rows:
            self.bm_rows.remove(bm_row)
            bm_row.destroy()
            self.rebuild_grid()

    def destroy(self):
        for bm in self.bm_rows:
            bm.destroy()
        self.frame.destroy()


# =============================================================
# Hauptanwendung
# =============================================================
class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.75)
        self.root.geometry("220x80+100+100")
        self.root.configure(bg=ROW_BG)
        self.root.withdraw()

        self._drag_x = 0
        self._drag_y = 0
        self.auto_ready_enabled = True
        self.current_champion = None
        self.current_role = ''
        self.current_queue_id = 0
        self.current_phase = None
        # Gegnerliste aus ChampSelect: Liste von Dicts
        # [{'cell_id': int, 'champion_id': int, 'role': str}, ...]
        # Wird vom LCU-Backend gepusht und ist die Quelle fuer den VS-Button.
        self.enemy_roster = []
        # Eigene cellId + Team-cellIds (sortiert) fuer Index-Fallback wenn
        # Rollen fehlen (z. B. Bot-Games, in denen Bots keine assignedPosition
        # haben).
        self.my_cell_id = None
        self.my_team_cells = []
        self.data_queue = queue.Queue()
        self.hidden = False

        self.auto_pick_enabled = False
        self.auto_pick_champs = []
        self.auto_ban_champs = []
        self.auto_pick_minimized = True
        self.bad_matchups = {}  # {str(champ_id): [opp_champ_id, ...]}
        self.pick_rows = []
        self.ban_rows = []
        self.editing_row = None  # ChampRow im Edit-Mode
        self.editing_bm = None   # BadMatchupRow im Edit-Mode
        self._dnd_state = None
        self._bm_dnd_state = None
        self._pick_focusout_after = None
        self._ban_focusout_after = None
        self._edit_focusout_after = None
        self.active_bm_panel = None  # BadMatchupsPanel oder None

        # === Tab-Management (HWND-basiert, Win32 API) ===
        self._kb = KbController()              # fuer optionalen URL-Capture-Trick
        self._tab_lock = threading.RLock()     # gegen Race-Conditions bei Open/Close
        self._open_hwnd = None                 # HWND des aktuell von uns geoeffneten Fensters
        self._lol_was_foreground = False
        self._lol_monitor_stop = threading.Event()
        # Persistente URL-Daten (z. B. gespeicherte Item-Parameter)
        self.tab_state = self._load_tab_state()
        # Hotkeys (im Settings-Fenster anpassbar, in Config gespeichert)
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self._hotkey_listener = None
        self._settings_window = None
        # Schwacher-PC-Modus: wenn AN -> Browser wird beim Reintabben in LoL
        # silent geschlossen. Default AUS - der User muss aktiv aktivieren,
        # damit Spieler mit starkem Rechner keine Faxen erleben.
        self.weak_pc_mode = False
        # Debug-Modus: schreibt Diagnoseinfos in lol_tool_debug.log
        self.debug_mode = False
        # URL-Tracking: laeuft im Hintergrund, liest die Adressleiste via UI Automation.
        self._url_tracker_stop = threading.Event()
        self._last_tracked_url = None
        # PID des zuletzt gestarteten Browser-Prozesses (fuer schnelle
        # HWND-Identifikation, falls der Tracker noch nicht durch ist).
        self._opened_browser_pid = None

        self.load_config()

        # ---------- Top-Bar (Window-Drag) ----------
        self.top_frame = tk.Frame(self.root, bg=ROW_BG, height=18)
        self.top_frame.pack(fill=tk.X, padx=4, pady=(3, 0))
        self.top_frame.bind("<Button-1>", self.start_drag)
        self.top_frame.bind("<B1-Motion>", self.drag)

        self.status_canvas = tk.Canvas(self.top_frame, width=6, height=6, bg=ROW_BG, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 3))
        self.status_dot = self.status_canvas.create_oval(0, 0, 6, 6, fill="#f0a830", outline="")
        self.status_canvas.bind("<Button-1>", self.start_drag)
        self.status_canvas.bind("<B1-Motion>", self.drag)

        self.status_label = tk.Label(self.top_frame, text="Verbinde...", bg=ROW_BG, fg="#b0a88a",
                                     font=("Segoe UI", 7))
        self.status_label.pack(side=tk.LEFT)
        self.status_label.bind("<Button-1>", self.start_drag)
        self.status_label.bind("<B1-Motion>", self.drag)

        self.exit_btn = tk.Label(self.top_frame, text="✕", bg=ROW_BG, fg="#c8aa6e",
                                 font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.exit_btn.pack(side=tk.RIGHT)
        self.exit_btn.bind("<Button-1>", lambda e: self.quit())
        self.exit_btn.bind("<Enter>", lambda e: self.exit_btn.config(fg="#f0e6d2"))
        self.exit_btn.bind("<Leave>", lambda e: self.exit_btn.config(fg="#c8aa6e"))

        self.min_btn = tk.Label(self.top_frame, text="–", bg=ROW_BG, fg="#c8aa6e",
                                font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.min_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self.min_btn.bind("<Button-1>", lambda e: self.hide_overlay())
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(fg="#f0e6d2"))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(fg="#c8aa6e"))

        # Settings-Button (oeffnet Hotkey-/Einstellungsfenster)
        self.settings_btn = tk.Label(self.top_frame, text="⋮", bg=ROW_BG, fg="#c8aa6e",
                                     font=("Segoe UI", 12, "bold"), cursor="hand2")
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 4))
        self.settings_btn.bind("<Button-1>", lambda e: self._open_settings())
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.config(fg="#f0e6d2"))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.config(fg="#c8aa6e"))

        self.phase_badge = tk.Label(self.top_frame, text="Client", bg="#1a2a3a", fg="#c8aa6e",
                                    font=("Segoe UI", 7, "bold"), padx=5, pady=0)
        self.phase_badge.pack(side=tk.RIGHT, padx=(0, 4))
        self.phase_badge.bind("<Button-1>", self.start_drag)
        self.phase_badge.bind("<B1-Motion>", self.drag)

        # ---------- Auto-Ready ----------
        self.auto_ready_var = tk.BooleanVar(value=True)
        self.auto_ready_check = tk.Checkbutton(self.root, text="Auto‑Ready", variable=self.auto_ready_var,
                                               command=self.toggle_auto_ready, bg=ROW_BG, fg="#d4b87a",
                                               selectcolor=ROW_BG, activebackground=ROW_BG,
                                               font=("Segoe UI", 7), relief="flat")
        self.auto_ready_check.pack(anchor=tk.W, padx=4, pady=(2, 0))

        # ---------- Auto-Pick&Ban ----------
        self.auto_pick_frame = tk.Frame(self.root, bg=ROW_BG)
        self.auto_pick_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.auto_pick_toggle_var = tk.BooleanVar(value=self.auto_pick_enabled)
        self.auto_pick_check = tk.Checkbutton(self.auto_pick_frame, text="Auto-Pick&Ban",
                                              variable=self.auto_pick_toggle_var, command=self.toggle_auto_pick,
                                              bg=ROW_BG, fg="#d4b87a", selectcolor=ROW_BG,
                                              activebackground=ROW_BG, font=("Segoe UI", 7), relief="flat")
        self.auto_pick_check.pack(side=tk.LEFT)
        self.auto_pick_min_btn = tk.Label(self.auto_pick_frame, text="+", bg=ROW_BG, fg="#c8aa6e",
                                          font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.auto_pick_min_btn.pack(side=tk.RIGHT)
        self.auto_pick_min_btn.bind("<Button-1>", lambda e: self.toggle_auto_pick_minimize())
        self.auto_pick_min_btn.bind("<Enter>", lambda e: self.auto_pick_min_btn.config(fg="#f0e6d2"))
        self.auto_pick_min_btn.bind("<Leave>", lambda e: self.auto_pick_min_btn.config(fg="#c8aa6e"))

        self.auto_pick_content_frame = tk.Frame(self.root, bg=ROW_BG)

        # Pick Suchfeld
        self.pick_search_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.pick_search_entry = self._make_search_entry(self.pick_search_frame, 'pick', PICK_PLACEHOLDER)
        self.pick_suggestions_listbox = self._make_suggestions_listbox(self.pick_search_frame, 'pick')
        self.pick_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.pick_champ_list_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)

        # Ban Suchfeld
        self.ban_search_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.ban_search_entry = self._make_search_entry(self.ban_search_frame, 'ban', BAN_PLACEHOLDER)
        self.ban_suggestions_listbox = self._make_suggestions_listbox(self.ban_search_frame, 'ban')
        self.ban_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.ban_champ_list_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)

        self.auto_pick_content_frame.pack(anchor=tk.W, fill=tk.X)
        self.auto_pick_content_frame.pack_forget()

        # ---------- LoLalytics ----------
        self.champ_frame = tk.Frame(self.root, bg=ROW_BG, height=16)
        self.champ_label = tk.Label(self.champ_frame, text="", bg=ROW_BG, fg="#f0e6d2", font=FONT_ROW)
        self.champ_label.pack(side=tk.LEFT, padx=(0, 3))
        self.lolalytics_btn = tk.Label(self.champ_frame, text="LoLalytics", bg="#1a5a8a", fg="#ffffff",
                                       font=FONT_ROW, padx=6, pady=0, cursor="hand2")
        self.lolalytics_btn.pack(side=tk.LEFT)
        self.lolalytics_btn.bind("<Button-1>", lambda e: self.open_lolalytics())
        self.lolalytics_btn.bind("<Enter>", lambda e: self.lolalytics_btn.config(bg="#1d7bb0"))
        self.lolalytics_btn.bind("<Leave>", lambda e: self.lolalytics_btn.config(bg="#1a5a8a"))

        # ---------- VS-Matchup ---------- (rot, daneben, nur bei Lane-Gegner)
        self.vs_btn = tk.Label(self.champ_frame, text="VS", bg="#a01818", fg="#ffffff",
                               font=FONT_ROW, padx=6, pady=0, cursor="hand2")
        # NICHT direkt packen - Sichtbarkeit ueber _refresh_vs_button_visibility
        self.vs_btn.bind("<Button-1>", lambda e: self.open_vs())
        self.vs_btn.bind("<Enter>", lambda e: self.vs_btn.config(bg="#c41f1f"))
        self.vs_btn.bind("<Leave>", lambda e: self.vs_btn.config(bg="#a01818"))
        self._vs_visible = False

        self.backend = LCUBackend(self)
        self.backend.start()
        self.start_hotkey_listener()
        self.root.after(200, self.process_queue)

        # Initiale Rows aufbauen
        for cid in self.auto_pick_champs:
            self.pick_rows.append(ChampRow(self, self.pick_champ_list_frame, 'pick'))
        for cid in self.auto_ban_champs:
            self.ban_rows.append(ChampRow(self, self.ban_champ_list_frame, 'ban'))
        self._refresh_row_data('pick')
        self._refresh_row_data('ban')

        self.update_min_btn_text()
        if self.auto_pick_enabled and not self.auto_pick_minimized:
            self.auto_pick_toggle_var.set(True)
            self.show_auto_pick_widgets()
            self._arrange_content()
        elif self.auto_pick_enabled:
            self.auto_pick_toggle_var.set(True)

        # Globaler Click-Listener für "klick außerhalb schließt BM-Panel"
        self.root.bind_all("<Button-1>", self._on_global_click, add='+')
        self._resize_window()

    # ---------- Suchfeld-Factory ----------
    def _make_search_entry(self, parent, list_type, placeholder):
        e = tk.Entry(parent, bg="#1a2a3a", fg=PLACEHOLDER_FG, insertbackground="#ffffff",
                     font=FONT_ENTRY, relief="flat", borderwidth=0,
                     selectbackground="#1a2a3a", selectforeground=PLACEHOLDER_FG,
                     highlightthickness=0)
        e.pack(fill=tk.X, padx=2, pady=1)
        self._set_placeholder(e, placeholder)
        e.bind('<KeyPress>', lambda ev: self._on_search_keypress(ev, list_type))
        e.bind('<KeyRelease>', lambda ev: self._on_search_keyrelease(ev, list_type))
        e.bind('<FocusIn>', lambda ev: self._on_search_focusin(list_type))
        e.bind('<FocusOut>', lambda ev: self._on_search_focusout(list_type))
        e.bind('<Button-1>', lambda ev: self._on_search_click(ev, list_type))
        e.bind('<Double-Button-1>', lambda ev: self._on_search_dblclick(ev, list_type))
        e.bind('<Return>', lambda ev: self._on_search_enter(list_type))
        e.bind('<Down>', lambda ev: self._on_search_arrow(list_type, 1))
        e.bind('<Up>', lambda ev: self._on_search_arrow(list_type, -1))
        return e

    def _make_suggestions_listbox(self, parent, list_type):
        lb = tk.Listbox(parent, bg="#0a1a2b", fg="#c8aa6e", font=FONT_ENTRY,
                        height=4, borderwidth=0, highlightthickness=0,
                        selectbackground="#2a3a4a", selectforeground="#f0e6d2",
                        activestyle='none', exportselection=False)
        lb.pack_forget()
        lb.bind('<Button-1>', lambda e: self._on_listbox_click(e, list_type))
        lb.bind('<Double-Button-1>', lambda e: self._on_listbox_click(e, list_type, True))
        return lb

    # ---------- Placeholder Helpers ----------
    def _is_placeholder(self, entry, placeholder):
        return entry.get() == placeholder and entry.cget('fg') == PLACEHOLDER_FG

    def _set_placeholder(self, entry, placeholder):
        entry.delete(0, tk.END)
        entry.insert(0, placeholder)
        entry.config(fg=PLACEHOLDER_FG)
        entry.icursor(0)

    def _placeholder_for(self, list_type):
        return PICK_PLACEHOLDER if list_type == 'pick' else BAN_PLACEHOLDER

    def _entry_for(self, list_type):
        return self.pick_search_entry if list_type == 'pick' else self.ban_search_entry

    def _listbox_for(self, list_type):
        return self.pick_suggestions_listbox if list_type == 'pick' else self.ban_suggestions_listbox

    def _rows_for(self, list_type):
        return self.pick_rows if list_type == 'pick' else self.ban_rows

    def _champs_for(self, list_type):
        return self.auto_pick_champs if list_type == 'pick' else self.auto_ban_champs

    def _list_frame_for(self, list_type):
        return self.pick_champ_list_frame if list_type == 'pick' else self.ban_champ_list_frame

    # ---------- Hotkey & Overlay ----------
    def start_hotkey_listener(self):
        # Hotkeys werden ueber self.hotkeys gebaut -> im Settings-Fenster anpassbar.
        self._apply_hotkeys()
        # Hintergrund-Thread der erkennt wann LoL in den Vordergrund kommt
        self._start_lol_foreground_monitor()
        # Hintergrund-Thread fuer Live-URL-Tracking (UI Automation, kein Fokus)
        self._start_url_tracker()

    def _apply_hotkeys(self):
        """(Re)baut den globalen Hotkey-Listener anhand von self.hotkeys."""
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

        handler_map = {
            'toggle_overlay':      self.on_hotkey,
            'open_lolalytics':     self.on_hotkey_open_lolalytics,
            'open_vs':             self.on_hotkey_open_vs,
            'close_tab':           self.on_hotkey_close_lolalytics,
            'close_all_browsers':  self.on_hotkey_close_all_browsers,
        }
        bindings = {}
        for action_id, combo in self.hotkeys.items():
            handler = handler_map.get(action_id)
            if handler and combo:
                bindings[combo] = handler
        if not bindings:
            return
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys(bindings)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            # Bei Konflikten (z. B. ungueltige Kombi) auf Defaults zurueckfallen
            print(f"[Hotkey] Fehler beim Setzen ({e}), fallback auf Defaults.")
            self.hotkeys = dict(DEFAULT_HOTKEYS)
            try:
                self._hotkey_listener = keyboard.GlobalHotKeys({
                    DEFAULT_HOTKEYS['toggle_overlay']:     self.on_hotkey,
                    DEFAULT_HOTKEYS['open_lolalytics']:    self.on_hotkey_open_lolalytics,
                    DEFAULT_HOTKEYS['open_vs']:            self.on_hotkey_open_vs,
                    DEFAULT_HOTKEYS['close_tab']:          self.on_hotkey_close_lolalytics,
                    DEFAULT_HOTKEYS['close_all_browsers']: self.on_hotkey_close_all_browsers,
                })
                self._hotkey_listener.daemon = True
                self._hotkey_listener.start()
            except Exception:
                pass

    def _open_settings(self):
        if self._settings_window is not None:
            try:
                self._settings_window.win.lift()
                self._settings_window.win.focus_force()
                return
            except Exception:
                self._settings_window = None
        self._settings_window = SettingsWindow(self)

    def on_hotkey(self):
        self.root.after(0, self.toggle_overlay)

    def toggle_overlay(self):
        if self.hidden:
            self.show_overlay()
        else:
            self.hide_overlay()

    def hide_overlay(self):
        self.hidden = True
        self.root.withdraw()

    def show_overlay(self):
        if self.hidden:
            self.root.deiconify()
            self.root.attributes('-topmost', True)
            self.root.lift()
            self.hidden = False

    # ---------- Layout ----------
    def _resize_window(self):
        if self.hidden:
            return
        self.root.update_idletasks()
        w = max(self.root.winfo_reqwidth(), 220)
        h = max(self.root.winfo_reqheight(), 80)
        self.root.geometry(f"{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def update_min_btn_text(self):
        self.auto_pick_min_btn.config(text="–" if (self.auto_pick_enabled and not self.auto_pick_minimized) else "+")

    def _ensure_champ_frame_at_bottom(self):
        if self.hidden:
            return
        if self.current_champion:
            self.champ_frame.pack_forget()
            self.champ_frame.pack(anchor=tk.W, padx=4, pady=(4, 6))

    def _arrange_content(self):
        # Close any BM panel before rearranging
        self.pick_search_frame.pack_forget()
        self.pick_champ_list_frame.pack_forget()
        self.ban_search_frame.pack_forget()
        self.ban_champ_list_frame.pack_forget()
        self.pick_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        if self.auto_pick_champs:
            self.pick_champ_list_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.ban_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        if self.auto_ban_champs:
            self.ban_champ_list_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self._ensure_champ_frame_at_bottom()
        # Re-pack BM panel below its owner if open
        if self.active_bm_panel is not None:
            self._pack_bm_panel(self.active_bm_panel)

    def toggle_auto_pick(self):
        self.auto_pick_enabled = self.auto_pick_toggle_var.get()
        self.save_config()
        if self.auto_pick_enabled:
            self.auto_pick_minimized = False
            self.show_auto_pick_widgets()
            self._arrange_content()
            self._refresh_row_data('pick')
            self._refresh_row_data('ban')
            self.pick_search_entry.focus_set()
        else:
            self._close_bm_panel()
            self.hide_auto_pick_widgets()
        self.update_min_btn_text()
        self._ensure_champ_frame_at_bottom()
        self._resize_window()

    def show_auto_pick_widgets(self):
        self.auto_pick_content_frame.pack(anchor=tk.W, fill=tk.X)
        self._set_placeholder(self.pick_search_entry, PICK_PLACEHOLDER)
        self._set_placeholder(self.ban_search_entry, BAN_PLACEHOLDER)
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()

    def hide_auto_pick_widgets(self):
        self._close_bm_panel()
        self.auto_pick_content_frame.pack_forget()
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()

    def toggle_auto_pick_minimize(self):
        if not self.auto_pick_enabled:
            self.auto_pick_toggle_var.set(True)
            self.toggle_auto_pick()
            return
        self.auto_pick_minimized = not self.auto_pick_minimized
        self.save_config()
        self.update_min_btn_text()
        if self.auto_pick_minimized:
            self.hide_auto_pick_widgets()
        else:
            self.show_auto_pick_widgets()
            self._arrange_content()
            self._refresh_row_data('pick')
            self._refresh_row_data('ban')
            self.pick_search_entry.focus_set()
        self._ensure_champ_frame_at_bottom()
        self._resize_window()

    # ---------- Row-Verwaltung ----------
    def _refresh_row_data(self, list_type):
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        while len(rows) < len(champs):
            rows.append(ChampRow(self, self._list_frame_for(list_type), list_type))
        while len(rows) > len(champs):
            extra = rows.pop()
            extra.destroy()
        for i, (row, cid) in enumerate(zip(rows, champs), 1):
            row.set_data(cid, i)
            row.outer.pack_forget()
            row.outer.pack(fill=tk.X, pady=1)

    def _add_champ(self, list_type, champ_id):
        champs = self._champs_for(list_type)
        if len(champs) >= 5 or champ_id in champs:
            return
        champs.append(champ_id)
        rows = self._rows_for(list_type)
        new_row = ChampRow(self, self._list_frame_for(list_type), list_type)
        new_row.set_data(champ_id, len(champs))
        new_row.outer.pack(fill=tk.X, pady=1)
        rows.append(new_row)
        self._arrange_content()
        self.save_config()
        self._resize_window()

    def _delete_row(self, row):
        list_type = row.list_type
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        if row not in rows:
            return
        idx = rows.index(row)
        if self.editing_row is row:
            self._cancel_edit(row)
        # BM-Panel schließen, wenn es zu dieser Row gehört
        if (self.active_bm_panel is not None
                and self.active_bm_panel.owner_row is row):
            self._close_bm_panel()
        rows.pop(idx)
        champs.pop(idx)
        row.destroy()
        for i, r in enumerate(rows, 1):
            r.set_index(i)
        if not champs:
            self._list_frame_for(list_type).pack_forget()
        self.save_config()
        self._resize_window()

    # ---------- Edit (Pick + Ban via Doppelklick) ----------
    def _edit_row(self, row):
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()
        if self.editing_row is not None and self.editing_row is not row:
            self._commit_edit(self.editing_row)
        if self.editing_row is row:
            return
        row.lbl.pack_forget()
        row.edit_entry = tk.Entry(row.inner, bg=ROW_BG, fg=ACTIVE_FG, insertbackground="#ffffff",
                                  font=FONT_ROW, relief="flat", borderwidth=0,
                                  selectbackground=ROW_BG, selectforeground=ACTIVE_FG,
                                  highlightthickness=0)
        old_name = CHAMPION_NAMES.get(row.champ_id, "")
        row.edit_entry.insert(0, old_name)
        row.edit_entry.icursor(0)
        # vor dem ersten RIGHT-Button (del_btn oder dots_btn) packen
        anchor_btn = row.dots_btn if row.dots_btn is not None else row.del_btn
        row.edit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, before=anchor_btn)
        row.is_initial_edit_replace = True

        row.edit_list_frame = tk.Frame(row.outer.master, bg=ROW_BG)
        row.edit_listbox = tk.Listbox(row.edit_list_frame, bg="#0a1a2b", fg="#c8aa6e",
                                      font=FONT_ENTRY, height=0, borderwidth=0,
                                      highlightthickness=0, selectbackground="#2a3a4a",
                                      selectforeground="#f0e6d2", activestyle='none',
                                      exportselection=False)
        row.edit_listbox.pack(fill=tk.X)
        row.edit_listbox.pack_forget()
        row.edit_list_frame.pack_forget()

        row.edit_entry.bind('<KeyPress>', lambda e, r=row: self._on_edit_keypress(e, r))
        row.edit_entry.bind('<KeyRelease>', lambda e, r=row: self._on_edit_keyrelease(e, r))
        row.edit_entry.bind('<Return>', lambda e, r=row: self._commit_edit(r))
        row.edit_entry.bind('<Escape>', lambda e, r=row: self._cancel_edit(r))
        row.edit_entry.bind('<Down>', lambda e, r=row: self._listbox_navigate(r.edit_listbox, 1))
        row.edit_entry.bind('<Up>', lambda e, r=row: self._listbox_navigate(r.edit_listbox, -1))
        row.edit_entry.bind('<FocusOut>', lambda e, r=row: self._on_edit_focusout(r))
        row.edit_listbox.bind('<Button-1>', lambda e, r=row: self._on_edit_listbox_click(e, r))
        row.edit_listbox.bind('<Double-Button-1>', lambda e, r=row: self._on_edit_listbox_click(e, r))
        row.edit_entry.focus_set()
        self.editing_row = row
        self._resize_window()

    def _on_edit_keypress(self, event, row):
        if row.is_initial_edit_replace and event.char and len(event.char) == 1 and event.char.isprintable():
            row.edit_entry.delete(0, tk.END)
            row.edit_entry.insert(0, event.char)
            row.edit_entry.icursor(1)
            row.is_initial_edit_replace = False
            return "break"
        if event.keysym in ('BackSpace', 'Delete'):
            row.is_initial_edit_replace = False
        return None

    def _on_edit_keyrelease(self, event, row):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Left', 'Right'):
            return
        row.edit_listbox.delete(0, tk.END)
        matches = find_matches(row.edit_entry.get())
        if not matches:
            row.edit_list_frame.pack_forget()
            self._resize_window()
            return
        if matches:
            num = min(len(matches), 4)
            row.edit_listbox.config(height=num)
            for m in matches[:num]:
                row.edit_listbox.insert(tk.END, m)
            if not row.edit_list_frame.winfo_ismapped():
                row.edit_list_frame.pack(after=row.outer, fill=tk.X, pady=(0, 2))
                row.edit_listbox.pack(fill=tk.X)
        else:
            row.edit_list_frame.pack_forget()
        self._resize_window()

    def _on_edit_focusout(self, row):
        if self._edit_focusout_after is not None:
            try: self.root.after_cancel(self._edit_focusout_after)
            except Exception: pass
        self._edit_focusout_after = self.root.after(150, lambda: self._commit_edit(row))

    def _on_edit_listbox_click(self, event, row):
        if self._edit_focusout_after is not None:
            try: self.root.after_cancel(self._edit_focusout_after)
            except Exception: pass
            self._edit_focusout_after = None
        try:
            idx = row.edit_listbox.nearest(event.y)
            row.edit_listbox.selection_clear(0, tk.END)
            row.edit_listbox.selection_set(idx)
            row.edit_listbox.activate(idx)
        except Exception: pass
        self._commit_edit(row)
        return "break"

    def _commit_edit(self, row):
        if self.editing_row is not row or row.edit_entry is None:
            return
        if self._edit_focusout_after is not None:
            try: self.root.after_cancel(self._edit_focusout_after)
            except Exception: pass
            self._edit_focusout_after = None
        sel = row.edit_listbox.curselection()
        if sel:
            name = row.edit_listbox.get(sel[0])
        elif row.edit_listbox.size() > 0:
            name = row.edit_listbox.get(0)
        else:
            name = row.edit_entry.get().strip()
        norm = name.lower().replace(' ', '').replace("'", '')
        new_id = NORM_NAMES.get(norm, (None, None))[1]
        champs = self._champs_for(row.list_type)
        rows = self._rows_for(row.list_type)
        idx = rows.index(row)
        old_id = row.champ_id
        if new_id is not None and (new_id == old_id or new_id not in champs):
            champs[idx] = new_id
            self.save_config()
        self._cancel_edit(row)
        row.set_data(champs[idx], idx + 1)

    def _cancel_edit(self, row):
        if row.edit_entry is None:
            return
        try: row.edit_entry.destroy()
        except Exception: pass
        row.edit_entry = None
        try:
            if row.edit_list_frame is not None:
                row.edit_list_frame.destroy()
        except Exception: pass
        row.edit_list_frame = None
        row.edit_listbox = None
        # Label vor erstem RIGHT-Button wieder einfügen
        anchor_btn = row.dots_btn if row.dots_btn is not None else row.del_btn
        row.lbl.pack(side=tk.LEFT, before=anchor_btn)
        if self.editing_row is row:
            self.editing_row = None
        self._resize_window()

    # ---------- Suchfeld-Events ----------
    def _on_search_keypress(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            if event.char and len(event.char) == 1 and event.char.isprintable():
                entry.delete(0, tk.END)
                entry.config(fg=ACTIVE_FG)
                entry.insert(0, event.char)
                entry.icursor(1)
                return "break"
            if event.keysym not in ('Tab', 'Escape'):
                return "break"
        return None

    def _on_search_keyrelease(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        listbox = self._listbox_for(list_type)
        # Empty-Check IMMER (auch nach Ctrl+A+Delete etc.)
        if entry.get() == "":
            if not self._is_placeholder(entry, placeholder):
                self._set_placeholder(entry, placeholder)
            listbox.pack_forget()
            self._resize_window()
            return
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Escape'):
            return
        self._update_suggestions(list_type)

    def _on_search_click(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            self.root.after_idle(lambda: entry.icursor(0))
        return None

    def _on_search_dblclick(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            entry.selection_clear()
            entry.icursor(0)
            return "break"
        return None

    def _on_search_focusin(self, list_type):
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try: self.root.after_cancel(pending)
            except Exception: pass
            setattr(self, attr, None)
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            entry.icursor(0)
            return
        if entry.get().strip():
            self._update_suggestions(list_type)

    def _on_search_focusout(self, list_type):
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try: self.root.after_cancel(pending)
            except Exception: pass
        setattr(self, attr, self.root.after(150, lambda: self._hide_suggestions(list_type)))

    def _hide_suggestions(self, list_type):
        self._listbox_for(list_type).pack_forget()
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if entry.get().strip() == "":
            self._set_placeholder(entry, placeholder)
        self._resize_window()

    def _update_suggestions(self, list_type):
        entry = self._entry_for(list_type)
        listbox = self._listbox_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            listbox.pack_forget()
            return
        listbox.delete(0, tk.END)
        matches = find_matches(entry.get())
        if not matches:
            listbox.pack_forget()
            self._resize_window()
            return
        if matches:
            num = min(len(matches), 4)
            listbox.config(height=num)
            for m in matches[:num]:
                listbox.insert(tk.END, m)
            if not listbox.winfo_ismapped():
                listbox.pack(anchor=tk.W, padx=4, pady=(0, 2))
        else:
            listbox.pack_forget()
        self._resize_window()

    def _on_search_enter(self, list_type):
        self._confirm_search(list_type)
        return "break"

    def _on_search_arrow(self, list_type, direction):
        self._listbox_navigate(self._listbox_for(list_type), direction)
        return "break"

    def _on_listbox_click(self, event, list_type, double=False):
        listbox = self._listbox_for(list_type)
        try:
            idx = listbox.nearest(event.y)
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(idx)
            listbox.activate(idx)
        except Exception: pass
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try: self.root.after_cancel(pending)
            except Exception: pass
            setattr(self, attr, None)
        self._confirm_search(list_type)
        return "break"

    def _confirm_search(self, list_type):
        listbox = self._listbox_for(list_type)
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        sel = listbox.curselection()
        if sel:
            name = listbox.get(sel[0])
        elif listbox.size() > 0:
            name = listbox.get(0)
        else:
            name = entry.get().strip()
        if name in NAME_TO_ID:
            self._add_champ(list_type, NAME_TO_ID[name])
            entry.delete(0, tk.END)
            self._set_placeholder(entry, placeholder)
            listbox.pack_forget()
            self._resize_window()

    def _listbox_navigate(self, listbox, direction):
        try:
            if listbox is None or not listbox.winfo_ismapped():
                return "break"
        except tk.TclError:
            return "break"
        size = listbox.size()
        if size == 0:
            return "break"
        current = listbox.curselection()
        if not current:
            new_idx = 0 if direction > 0 else size - 1
        else:
            new_idx = max(0, min(size - 1, current[0] + direction))
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(new_idx)
        listbox.activate(new_idx)
        listbox.see(new_idx)
        return "break"

    # ---------- Drag & Drop (Champion-Rows, Picks + Bans) ----------
    def _dnd_start(self, event, row):
        if self.editing_row is row:
            return
        rows = self._rows_for(row.list_type)
        if row not in rows:
            return
        self._dnd_state = {'row': row, 'moved': False, 'highlighted': False,
                           'list_type': row.list_type,
                           'start_x': event.x_root, 'start_y': event.y_root}

    def _dnd_motion(self, event, row):
        state = self._dnd_state
        if not state or state['row'] is not row:
            return
        if not state['highlighted']:
            dx = abs(event.x_root - state['start_x'])
            dy = abs(event.y_root - state['start_y'])
            if dx + dy < 3:
                return
            row.set_dragged(True)
            state['highlighted'] = True
        rows = self._rows_for(row.list_type)
        if row not in rows:
            return
        current_idx = rows.index(row)
        parent = self._list_frame_for(row.list_type)
        try:
            pointer_y = parent.winfo_pointery() - parent.winfo_rooty()
        except tk.TclError:
            return
        if current_idx + 1 < len(rows):
            below = rows[current_idx + 1]
            try:
                mid = below.outer.winfo_y() + below.outer.winfo_height() / 2
            except tk.TclError:
                return
            if pointer_y > mid:
                self._dnd_swap(row, current_idx, current_idx + 1)
                return
        if current_idx - 1 >= 0:
            above = rows[current_idx - 1]
            try:
                mid = above.outer.winfo_y() + above.outer.winfo_height() / 2
            except tk.TclError:
                return
            if pointer_y < mid:
                self._dnd_swap(row, current_idx, current_idx - 1)
                return

    def _dnd_swap(self, dragged_row, from_idx, to_idx):
        list_type = dragged_row.list_type
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        champs[from_idx], champs[to_idx] = champs[to_idx], champs[from_idx]
        rows[from_idx], rows[to_idx] = rows[to_idx], rows[from_idx]
        new_idx = rows.index(dragged_row)
        if new_idx == 0:
            dragged_row.outer.pack(fill=tk.X, pady=1, before=rows[1].outer)
        else:
            dragged_row.outer.pack(fill=tk.X, pady=1, after=rows[new_idx - 1].outer)
        for i, r in enumerate(rows, 1):
            r.set_index(i)
        dragged_row.set_dragged(True)
        self._dnd_state['moved'] = True
        self.root.update_idletasks()

    def _dnd_release(self, event, row):
        state = self._dnd_state
        if not state or state['row'] is not row:
            return
        if state.get('highlighted'):
            row.set_dragged(False)
        if state['moved']:
            self.save_config()
        self._dnd_state = None

    # ---------- Bad-Matchups Logik ----------
    def _toggle_bad_matchups(self, pick_row):
        if (self.active_bm_panel is not None
                and self.active_bm_panel.owner_row is pick_row):
            self._close_bm_panel()
            return
        if self.active_bm_panel is not None:
            self._close_bm_panel()
        panel = BadMatchupsPanel(self, self.pick_champ_list_frame, pick_row)
        for opp_cid in self.bad_matchups.get(str(pick_row.champ_id), []):
            panel.add_row(opp_cid)
        self.active_bm_panel = panel
        self._pack_bm_panel(panel)
        panel.entry.focus_set()
        self._resize_window()

    def _pack_bm_panel(self, panel):
        panel.frame.pack_forget()
        panel.frame.pack(after=panel.owner_row.outer, fill=tk.X, padx=4, pady=(1, 2))

    def _close_bm_panel(self):
        if self.active_bm_panel is None:
            return
        if self.editing_bm is not None:
            self._commit_bm_edit(self.editing_bm)
        self.active_bm_panel.destroy()
        self.active_bm_panel = None
        self._resize_window()

    def _add_bm(self, panel, opp_champ_id):
        owner_key = str(panel.owner_champ_id)
        cur = list(self.bad_matchups.get(owner_key, []))
        if len(cur) >= BadMatchupsPanel.MAX or opp_champ_id in cur:
            return
        cur.append(opp_champ_id)
        self.bad_matchups[owner_key] = cur
        self.save_config()
        panel.add_row(opp_champ_id)
        self._resize_window()

    def _delete_bm(self, bm_row):
        if self.active_bm_panel is None:
            return
        owner_key = str(self.active_bm_panel.owner_champ_id)
        cur = list(self.bad_matchups.get(owner_key, []))
        if bm_row.champ_id in cur:
            cur.remove(bm_row.champ_id)
            self.bad_matchups[owner_key] = cur
            self.save_config()
        self.active_bm_panel.remove_row(bm_row)
        self._resize_window()

    def _edit_bm(self, bm_row):
        if self.active_bm_panel is None:
            return
        if self.editing_bm is not None and self.editing_bm is not bm_row:
            self._commit_bm_edit(self.editing_bm)
        if self.editing_bm is bm_row:
            return
        bm_row.lbl.pack_forget()
        bm_row.edit_entry = tk.Entry(bm_row.inner, bg=ROW_BG, fg=ACTIVE_FG, insertbackground="#ffffff",
                                     font=FONT_ROW_SMALL, relief="flat", borderwidth=0,
                                     selectbackground=ROW_BG, selectforeground=ACTIVE_FG,
                                     highlightthickness=0, width=1)
        old_name = CHAMPION_NAMES.get(bm_row.champ_id, "")
        bm_row.edit_entry.insert(0, old_name)
        bm_row.edit_entry.icursor(0)
        bm_row.edit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, before=bm_row.del_btn)
        bm_row.is_initial_edit_replace = True

        if self.active_bm_panel is not None:
            bm_row.edit_list_frame = tk.Frame(self.active_bm_panel.frame, bg=ROW_BG)
        else:
            bm_row.edit_list_frame = tk.Frame(bm_row.outer.master, bg=ROW_BG)
        bm_row.edit_listbox = tk.Listbox(bm_row.edit_list_frame, bg="#0a1a2b", fg="#c8aa6e",
                                         font=FONT_ENTRY_SMALL, height=0, borderwidth=0,
                                         highlightthickness=0, selectbackground="#2a3a4a",
                                         selectforeground="#f0e6d2", activestyle='none',
                                         exportselection=False)
        bm_row.edit_listbox.pack(fill=tk.X)
        bm_row.edit_listbox.pack_forget()
        bm_row.edit_list_frame.pack_forget()

        bm_row.edit_entry.bind('<KeyPress>', lambda e, r=bm_row: self._on_bm_edit_keypress(e, r))
        bm_row.edit_entry.bind('<KeyRelease>', lambda e, r=bm_row: self._on_bm_edit_keyrelease(e, r))
        bm_row.edit_entry.bind('<Return>', lambda e, r=bm_row: self._commit_bm_edit(r))
        bm_row.edit_entry.bind('<Escape>', lambda e, r=bm_row: self._cancel_bm_edit(r))
        bm_row.edit_entry.bind('<Down>', lambda e, r=bm_row: self._listbox_navigate(r.edit_listbox, 1))
        bm_row.edit_entry.bind('<Up>', lambda e, r=bm_row: self._listbox_navigate(r.edit_listbox, -1))
        bm_row.edit_entry.bind('<FocusOut>', lambda e, r=bm_row: self.root.after(150, lambda: self._commit_bm_edit(r)))
        bm_row.edit_listbox.bind('<Button-1>', lambda e, r=bm_row: self._on_bm_edit_listbox_click(e, r))
        bm_row.edit_listbox.bind('<Double-Button-1>', lambda e, r=bm_row: self._on_bm_edit_listbox_click(e, r))
        bm_row.edit_entry.focus_set()
        self.editing_bm = bm_row
        self._resize_window()

    def _on_bm_edit_keypress(self, event, row):
        if row.is_initial_edit_replace and event.char and len(event.char) == 1 and event.char.isprintable():
            row.edit_entry.delete(0, tk.END)
            row.edit_entry.insert(0, event.char)
            row.edit_entry.icursor(1)
            row.is_initial_edit_replace = False
            return "break"
        if event.keysym in ('BackSpace', 'Delete'):
            row.is_initial_edit_replace = False
        return None

    def _on_bm_edit_keyrelease(self, event, row):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Left', 'Right'):
            return
        row.edit_listbox.delete(0, tk.END)
        matches = find_matches(row.edit_entry.get())
        if not matches:
            row.edit_list_frame.pack_forget()
            self._resize_window()
            return
        num = min(len(matches), 4)
        row.edit_listbox.config(height=num)
        for m in matches[:num]:
            row.edit_listbox.insert(tk.END, m)
        if not row.edit_list_frame.winfo_ismapped():
            if self.active_bm_panel is not None:
                row.edit_list_frame.pack(after=self.active_bm_panel.grid_frame,
                                         fill=tk.X, padx=4, pady=(0, 1))
            else:
                row.edit_list_frame.pack(fill=tk.X, pady=(0, 1))
            row.edit_listbox.pack(fill=tk.X)
        self._resize_window()

    def _on_bm_edit_listbox_click(self, event, row):
        try:
            idx = row.edit_listbox.nearest(event.y)
            row.edit_listbox.selection_clear(0, tk.END)
            row.edit_listbox.selection_set(idx)
            row.edit_listbox.activate(idx)
        except Exception: pass
        self._commit_bm_edit(row)
        return "break"

    def _commit_bm_edit(self, row):
        if self.editing_bm is not row or row.edit_entry is None:
            return
        sel = row.edit_listbox.curselection()
        if sel:
            name = row.edit_listbox.get(sel[0])
        elif row.edit_listbox.size() > 0:
            name = row.edit_listbox.get(0)
        else:
            name = row.edit_entry.get().strip()
        norm = name.lower().replace(' ', '').replace("'", '')
        new_id = NORM_NAMES.get(norm, (None, None))[1]
        if self.active_bm_panel is not None:
            owner_key = str(self.active_bm_panel.owner_champ_id)
            cur = list(self.bad_matchups.get(owner_key, []))
            if row.champ_id in cur:
                idx = cur.index(row.champ_id)
                old_id = row.champ_id
                if new_id is not None and (new_id == old_id or new_id not in cur):
                    cur[idx] = new_id
                    self.bad_matchups[owner_key] = cur
                    self.save_config()
                    row.set_data(new_id)
        self._cancel_bm_edit(row)

    def _cancel_bm_edit(self, row):
        if row.edit_entry is None:
            return
        try: row.edit_entry.destroy()
        except Exception: pass
        row.edit_entry = None
        try:
            if row.edit_list_frame is not None:
                row.edit_list_frame.destroy()
        except Exception: pass
        row.edit_list_frame = None
        row.edit_listbox = None
        row.lbl.pack(side=tk.LEFT, padx=(2, 2), before=row.del_btn)
        if self.editing_bm is row:
            self.editing_bm = None
        self._resize_window()

    # ---------- BM Drag & Drop ----------
    def _bm_dnd_start(self, event, bm_row):
        if self.editing_bm is bm_row or self.active_bm_panel is None:
            return
        if bm_row not in self.active_bm_panel.bm_rows:
            return
        self._bm_dnd_state = {'row': bm_row, 'moved': False, 'highlighted': False,
                              'start_x': event.x_root, 'start_y': event.y_root}

    def _bm_dnd_motion(self, event, bm_row):
        state = self._bm_dnd_state
        if not state or state['row'] is not bm_row or self.active_bm_panel is None:
            return
        if not state['highlighted']:
            dx = abs(event.x_root - state['start_x'])
            dy = abs(event.y_root - state['start_y'])
            if dx + dy < 3:
                return
            bm_row.set_dragged(True)
            state['highlighted'] = True
        panel = self.active_bm_panel
        bms = panel.bm_rows
        if bm_row not in bms:
            return
        cur = bms.index(bm_row)
        try:
            px = panel.grid_frame.winfo_pointerx()
            py = panel.grid_frame.winfo_pointery()
        except tk.TclError:
            return
        best = cur
        best_dist = None
        for i, other in enumerate(bms):
            try:
                ox = other.outer.winfo_rootx() + other.outer.winfo_width() / 2
                oy = other.outer.winfo_rooty() + other.outer.winfo_height() / 2
            except tk.TclError:
                continue
            d = (px - ox) ** 2 + (py - oy) ** 2
            if best_dist is None or d < best_dist:
                best_dist = d
                best = i
        if best != cur:
            bms[cur], bms[best] = bms[best], bms[cur]
            owner_key = str(panel.owner_champ_id)
            self.bad_matchups[owner_key] = [b.champ_id for b in bms]
            state['moved'] = True
            panel.rebuild_grid()
            bm_row.set_dragged(True)

    def _bm_dnd_release(self, event, bm_row):
        state = self._bm_dnd_state
        if not state or state['row'] is not bm_row:
            return
        if state.get('highlighted'):
            bm_row.set_dragged(False)
        if state['moved']:
            self.save_config()
        self._bm_dnd_state = None

    # ---------- Global Click (BM-Panel Close) ----------
    def _on_global_click(self, event):
        if self.active_bm_panel is None:
            return
        w = event.widget
        panel = self.active_bm_panel
        if self._widget_in(w, panel.frame):
            return
        if self._widget_in(w, panel.owner_row.outer):
            return
        if panel.owner_row.dots_btn is not None and w is panel.owner_row.dots_btn:
            return
        self._close_bm_panel()

    @staticmethod
    def _widget_in(widget, container):
        try:
            wpath = str(widget)
            cpath = str(container)
            return wpath == cpath or wpath.startswith(cpath + '.')
        except Exception:
            return False

    # ---------- Config ----------
    def config_path(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, 'lolhelper_config.json')

    def load_config(self):
        try:
            with open(self.config_path(), 'r') as f:
                c = json.load(f)
                self.auto_pick_enabled = c.get('auto_pick_enabled', False)
                self.auto_pick_champs = c.get('auto_pick_champs', [])
                self.auto_ban_champs = c.get('auto_ban_champs', [])
                self.auto_pick_minimized = c.get('auto_pick_minimized', True)
                self.bad_matchups = c.get('bad_matchups', {})
                saved_hotkeys = c.get('hotkeys') or {}
                # Migration: v8 Layout (ohne 'open_vs') -> v10 Layout.
                # Wenn der User die Defaults der v8-Aera noch benutzt, schieben
                # wir alles um eins nach hinten und tragen VS auf Alt+Shift+2 ein.
                # Hat der User selbst angepasst, lassen wir es unangetastet.
                if 'open_vs' not in saved_hotkeys:
                    matches_v8 = all(saved_hotkeys.get(k) == v
                                     for k, v in _LEGACY_HOTKEYS_V8.items()
                                     if k in saved_hotkeys)
                    if matches_v8:
                        saved_hotkeys = {
                            'toggle_overlay':      saved_hotkeys.get('toggle_overlay', DEFAULT_HOTKEYS['toggle_overlay']),
                            'open_lolalytics':     '<alt>+<shift>+1',
                            'open_vs':             '<alt>+<shift>+2',
                            'close_tab':           '<alt>+<shift>+3',
                            'close_all_browsers':  '<alt>+<shift>+4',
                        }
                self.hotkeys = {**DEFAULT_HOTKEYS, **saved_hotkeys}
                self.weak_pc_mode = bool(c.get('weak_pc_mode', False))
                self.debug_mode = bool(c.get('debug_mode', False))
        except (FileNotFoundError, json.JSONDecodeError):
            self.auto_pick_enabled = False
            self.auto_pick_champs = []
            self.auto_ban_champs = []
            self.auto_pick_minimized = True
            self.bad_matchups = {}
            self.hotkeys = dict(DEFAULT_HOTKEYS)
            self.weak_pc_mode = False
            self.debug_mode = False

    def save_config(self):
        with open(self.config_path(), 'w') as f:
            json.dump({'auto_pick_enabled': self.auto_pick_enabled,
                       'auto_pick_champs': self.auto_pick_champs,
                       'auto_ban_champs': self.auto_ban_champs,
                       'auto_pick_minimized': self.auto_pick_minimized,
                       'bad_matchups': self.bad_matchups,
                       'hotkeys': self.hotkeys,
                       'weak_pc_mode': self.weak_pc_mode,
                       'debug_mode': self.debug_mode}, f)

    # ---------- Debug-Logger ----------
    def _debug(self, msg):
        """Schreibt eine Zeile in lol_tool_debug.log, falls debug_mode AN ist.
        Best-Effort - schlaegt es fehl, wird der Aufruf einfach geschluckt."""
        if not self.debug_mode:
            return
        try:
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            with open(_debug_log_path(), 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass

    def quit(self):
        # NEU: Foreground-Monitor stoppen + Tab-State sichern
        try:
            self._lol_monitor_stop.set()
        except Exception:
            pass
        try:
            self._url_tracker_stop.set()
        except Exception:
            pass
        try:
            self._save_tab_state()
        except Exception:
            pass
        try:
            if self._settings_window is not None:
                self._settings_window.close()
        except Exception:
            pass
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
        except Exception:
            pass
        self.save_config()
        self.root.destroy()

    # ---------- Fenster-Drag ----------
    def start_drag(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def drag(self, event):
        self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def toggle_auto_ready(self):
        self.auto_ready_enabled = self.auto_ready_var.get()

    # ---------- LCU Queue ----------
    def process_queue(self):
        try:
            while True:
                msg = self.data_queue.get_nowait()
                if msg['type'] == 'status':
                    if msg['connected']:
                        self.status_label.config(text="Verbunden", fg="#d4b87a")
                        self.status_canvas.itemconfig(self.status_dot, fill="#2ecc71")
                        if not self.root.winfo_viewable() and not self.hidden:
                            self.root.deiconify()
                    else:
                        self.status_label.config(text="Getrennt", fg="#e74c3c")
                        self.status_canvas.itemconfig(self.status_dot, fill="#e74c3c")
                elif msg['type'] == 'phase':
                    phase = msg['phase']
                    self.current_phase = phase
                    display = 'Client' if phase in ('None', '', None) else phase
                    self.phase_badge.config(text=display)
                    if display == 'ReadyCheck':
                        self.phase_badge.config(bg="#4a3a1a", fg="#f0a830")
                    elif display == 'ChampSelect':
                        self.phase_badge.config(bg="#1a3b4a", fg="#3a8fd4")
                    elif display == 'InProgress':
                        self.phase_badge.config(bg="#2e3a2e", fg="#2ecc71")
                    else:
                        self.phase_badge.config(bg="#1a2a3a", fg="#c8aa6e")
                    if phase in ('None', '', None, 'Lobby'):
                        self.champ_frame.pack_forget()
                        self.current_champion = None
                        self.current_role = ''
                        self.enemy_roster = []
                        self.my_cell_id = None
                        self.my_team_cells = []
                        self.champ_label.config(text="")
                        # Smart-Indicator zurücksetzen: alle Picks wieder grün
                        for row in self.pick_rows:
                            row.border_color = PICK_BORDER
                            row.outer.config(bg=PICK_BORDER)
                        if self.hidden and phase == 'Lobby':
                            self.show_overlay()
                    # VS-Button-Sichtbarkeit bei jedem Phase-Wechsel pruefen.
                    # Wichtig: bei phase=='InProgress' greift erst der Index-
                    # Fallback (Bot-Games), deshalb darf der Refresh nicht
                    # auf 'Lobby/None' beschraenkt sein.
                    self._refresh_vs_button_visibility()
                elif msg['type'] == 'champ_select':
                    cid = msg['champion_id']
                    role = msg['role']
                    self.current_queue_id = msg.get('queue_id', 0)
                    self.enemy_roster = msg.get('enemy_roster', []) or []
                    self.my_cell_id = msg.get('my_cell_id')
                    self.my_team_cells = msg.get('my_team_cells', []) or []
                    if cid:
                        name = CHAMPION_NAMES.get(cid, f"Champion {cid}")
                        self.current_champion = name
                        self.current_role = role
                        self.champ_label.config(text=f"{name} ({role})" if role and role.strip() else name)
                        self._ensure_champ_frame_at_bottom()
                        self._resize_window()
                    # VS-Button-Sichtbarkeit nachfuehren
                    self._refresh_vs_button_visibility()
                elif msg['type'] == 'pick_status':
                    # Smart-Indicator: Pick-Rahmen je nach Status einfärben
                    if self.current_phase == 'ChampSelect':
                        status = msg['status']
                        for row in self.pick_rows:
                            st = status.get(row.champ_id, 'ok')
                            if st == 'banned':
                                row.border_color = "#33ff00"  # grau
                            elif st == 'bad_matchup':
                                row.border_color = "#ffd900" #BAD_BORDER  # gelb
                            elif st == 'hovered':
                                 row.border_color = "#3a8fd4"  # blau - zeigt an dass dieser Champ vorgehovert ist
                            else:
                                row.border_color = "#818181" #PICK_BORDER  # grün
                            # Nur wenn nicht gerade Drag-Highlight aktiv
                            if self._dnd_state is None or self._dnd_state.get('row') is not row:
                                row.outer.config(bg=row.border_color)
        except queue.Empty:
            pass
        self.root.after(200, self.process_queue)

    # ==================================================================
    # ============ Tab-/Browser-Management (HWND-basiert) ==============
    # ==================================================================

    # ---------- State persistieren ----------
    def _load_tab_state(self):
        try:
            with open(_state_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return {}

    def _save_tab_state(self):
        try:
            with open(_state_path(), 'w', encoding='utf-8') as f:
                json.dump(self.tab_state, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    # ---------- URL-Bauer ----------
    def _build_lolalytics_url(self):
        """Baut die Lolalytics-URL fuer den aktuellen Champion.
        Fallback: kein aktiver Champion (Lobby) -> ersten Auto-Pick aus der Liste verwenden.
        """
        name = self.current_champion
        role = self.current_role
        queue_id = self.current_queue_id

        # Fallback: kein Champion gepickt (z. B. Lobby) -> erster Auto-Pick (Top der Liste)
        if not name:
            first_id = next((cid for cid in self.auto_pick_champs if cid), None)
            if first_id:
                name = CHAMPION_NAMES.get(first_id)
                role = ''        # Rolle in der Lobby unbekannt
                queue_id = 0

        if not name:
            return None

        name_clean = name.lower().replace(' ', '').replace("'", "").replace('.', '')
        if queue_id in (1700, 1710, 1750):
            base = f"https://lolalytics.com/lol/{name_clean}/arena/build/"
        elif queue_id in (2400, 450):
            base = f"https://lolalytics.com/lol/{name_clean}/aram/build/"
        else:
            base = f"https://lolalytics.com/lol/{name_clean}/build/"
        params = []
        if role and role.strip():
            lane = {'top': 'top', 'jungle': 'jungle', 'middle': 'mid',
                    'bottom': 'bottom', 'utility': 'support'}.get(role, '')
            if lane:
                params.append(f'lane={lane}')
        params.append('tier=all')
        return base + '?' + '&'.join(params)

    # ---------- VS-Matchup: Lane-Gegner ermitteln + URL bauen ----------
    def _find_lane_opponent(self):
        """Sucht den Gegner auf der eigenen Lane.

        Logik (priorisiert):
          0) ARAM/Arena -> kein Lane-Konzept, immer (0, '').
          1) **Strikter Rollen-Match** (assignedPosition): eigene Rolle
             'middle' -> Gegner mit Rolle 'middle'. Funktioniert in Draft/
             Ranked, wo beide Teams Positionen zugewiesen bekommen.
          2) **InProgress-Index-Fallback**: Bot-Games / Blind Pick - der
             Gegner hat oft kein assignedPosition. Im laufenden Spiel sind
             die cellIds typischerweise lane-sortiert, also nehmen wir den
             gegnerischen Eintrag am gleichen Index wie unseren eigenen
             Spieler. Nur im InProgress, weil in ChampSelect (rotierender
             Pick) die cellId-Reihenfolge noch nicht der Lane entspricht.
        Rueckgabe: (champion_id, role_str) oder (0, '').
        """
        if not self.enemy_roster:
            return (0, '')
        # Queue-Filter: ARAM + Arena haben keinen Lane-Gegner
        if self.current_queue_id in VS_DISABLED_QUEUES:
            return (0, '')
        my_role = (self.current_role or '').lower().strip()
        # Tier 1: Strikter Rollen-Match
        if my_role:
            for e in self.enemy_roster:
                if e.get('role') == my_role and e.get('champion_id'):
                    return (int(e['champion_id']), e['role'])
        # Tier 2: In-Game-Fallback ueber cellId-Index
        if (self.current_phase == 'InProgress'
                and self.my_cell_id is not None
                and self.my_team_cells):
            my_team_sorted = sorted(c for c in self.my_team_cells if c is not None)
            if self.my_cell_id in my_team_sorted:
                my_idx = my_team_sorted.index(self.my_cell_id)
                enemy_sorted = sorted(
                    [e for e in self.enemy_roster if e.get('cell_id') is not None],
                    key=lambda e: e['cell_id'],
                )
                if my_idx < len(enemy_sorted):
                    e = enemy_sorted[my_idx]
                    if e.get('champion_id'):
                        return (int(e['champion_id']), e.get('role', '') or my_role)
        return (0, '')

    def _build_vs_url(self):
        """Baut die Lolalytics-VS-URL: /lol/<my>/vs/<opp>/build/?lane=...&tier=all"""
        my = self.current_champion
        if not my:
            return None
        opp_id, opp_role = self._find_lane_opponent()
        if not opp_id:
            return None
        opp_name = CHAMPION_NAMES.get(opp_id)
        if not opp_name:
            return None
        def _slug(n):
            return n.lower().replace(' ', '').replace("'", "").replace('.', '')
        my_slug = _slug(my)
        opp_slug = _slug(opp_name)
        # Queue-spezifische Pfade gibt es fuer VS nicht (kein /arena/vs/...).
        base = f"https://lolalytics.com/lol/{my_slug}/vs/{opp_slug}/build/"
        params = []
        role = (self.current_role or '').lower().strip()
        lane = {'top': 'top', 'jungle': 'jungle', 'middle': 'mid',
                'bottom': 'bottom', 'utility': 'support'}.get(role, '')
        if lane:
            params.append(f'lane={lane}')
        params.append('tier=all')
        return base + '?' + '&'.join(params)

    def _refresh_vs_button_visibility(self):
        """Zeigt/versteckt den VS-Button basierend darauf, ob wir einen
        Lane-Gegner identifizieren konnten. Setzt zudem das Button-Label
        auf 'VS <Gegner>' bzw. zurueck auf 'VS' wenn unbekannt.
        So erscheint der Button erst wenn die Info wirklich verfuegbar ist
        (typischerweise Ende Champ-Select / In-Game)."""
        try:
            opp_id, _ = self._find_lane_opponent()
            should_show = bool(opp_id) and bool(self.current_champion)
            if should_show:
                opp_name = CHAMPION_NAMES.get(opp_id, '')
                label = f"VS {opp_name}" if opp_name else "VS"
                if self.vs_btn.cget('text') != label:
                    self.vs_btn.config(text=label)
                if not self._vs_visible:
                    self.vs_btn.pack(side=tk.LEFT, padx=(4, 0))
                    self._vs_visible = True
                self._resize_window()
            elif self._vs_visible:
                self.vs_btn.pack_forget()
                self._vs_visible = False
                # Label zuruecksetzen, damit es beim naechsten Show
                # keinen alten Gegner-Namen kurz aufblitzen laesst.
                self.vs_btn.config(text="VS")
                self._resize_window()
        except Exception:
            pass

    def _merge_url_with_saved_params(self, fresh_url, kind='base'):
        """Merged gespeicherte Query-Parameter (z. B. &item=1_3153) in die frische URL.
        Champion/Lane aus der frischen URL haben Vorrang.

        WICHTIG: Build-/Item-/Rune-Parameter werden NUR uebernommen, wenn die
        Seiten-Identitaet (Champion + ggf. Gegner) der gespeicherten URL und
        der frischen URL exakt uebereinstimmt. Sonst wuerden Item-Parameter
        von Champion A faelschlich auf Champion B weitergetragen.

        kind='base' -> liest aus tab_state['lolalytics']
        kind='vs'   -> liest aus tab_state['lolalytics_vs']
        """
        state_key = 'lolalytics_vs' if kind == 'vs' else 'lolalytics'
        saved = (self.tab_state.get(state_key) or {}).get('url')
        if not saved or not fresh_url:
            return fresh_url
        try:
            sp = urlparse(saved)
            fp = urlparse(fresh_url)
            saved_id = self._page_identity(saved)
            fresh_id = self._page_identity(fresh_url)
            # Andere Seite (anderer Champ ODER anderer Gegner) -> keine
            # alten Build-Params uebernehmen
            if saved_id != fresh_id:
                return fresh_url
            saved_q = dict(parse_qsl(sp.query, keep_blank_values=True))
            fresh_q = dict(parse_qsl(fp.query, keep_blank_values=True))
            merged = {**saved_q, **fresh_q}      # fresh hat Vorrang
            new_q = urlencode(merged, doseq=True)
            return urlunparse(fp._replace(query=new_q))
        except Exception:
            return fresh_url

    # ---------- Seiten-Identitaet ----------
    def _page_identity(self, url):
        """Extrahiert eine vergleichbare Identitaet aus einer Lolalytics-URL:
          - Basis-Seite:   ('base', '<champ>')
          - VS-Matchup:    ('vs',   '<champ>', '<gegner>')
        So koennen wir entscheiden ob ein offenes Fenster wirklich dieselbe
        Seite zeigt - selbst wenn der Champion-Slug identisch ist (z. B.
        Leblanc-Build vs. Leblanc-VS-Olaf-Matchup).
        """
        try:
            parts = [x for x in (urlparse(url).path or '').split('/') if x]
            if (len(parts) >= 4 and parts[0].lower() == 'lol'
                    and parts[2].lower() == 'vs'):
                return ('vs', parts[1].lower(), parts[3].lower())
            if len(parts) >= 2 and parts[0].lower() == 'lol':
                return ('base', parts[1].lower())
        except Exception:
            pass
        return None

    # ---------- HWND-Diff-Helfer ----------
    def _find_lolalytics_hwnd(self):
        """Sucht ueber ALLE Top-Level-Fenster ein offenes Lolalytics-Fenster.

        Mehrstufige Heuristik (erstes Resultat gewinnt):
          1) Fenster, dessen Titel 'lolalytics' enthaelt (schneller Pfad)
          2) Fenster, dessen Prozess unsere zuletzt-gestartete Browser-PID
             ist (auch ohne lolalytics im Titel - z. B. waehrend Cold-Start
             oder nachdem die Seite Item-/Build-Anpassungen vorgenommen hat
             und Lolalytics aus dem Titel verschwunden ist).
          3) Browser-Fenster (Title-Kw chrome/edge/...), deren Adressleiste
             via UI Automation 'lolalytics.com' enthaelt - der zuverlaessigste
             Weg, scheitert nur ohne comtypes.
        """
        # 1) Titel-Match
        for hwnd in _enum_top_level_hwnds():
            try:
                title = _get_window_title(hwnd).lower()
                if 'lolalytics' in title:
                    return hwnd
            except Exception:
                pass
        # 2) PID-Match (unser gerade gestarteter Browser)
        target_pid = self._opened_browser_pid
        if target_pid:
            for hwnd in _enum_top_level_hwnds():
                try:
                    if _hwnd_pid(hwnd) == target_pid:
                        t = _get_window_title(hwnd)
                        if t:    # Titel != leer (Fenster fertig gezeichnet)
                            return hwnd
                except Exception:
                    pass
        # 3) UIA-URL-Match ueber alle Browser-Fenster
        if _UIA_AVAILABLE:
            for hwnd in _enum_top_level_hwnds():
                try:
                    t = _get_window_title(hwnd).lower()
                    if not t:
                        continue
                    if not any(k in t for k in BROWSER_TITLE_KEYWORDS):
                        continue
                    url = _uia_read_browser_url(hwnd) or ''
                    if 'lolalytics.com' in url.lower():
                        return hwnd
                except Exception:
                    pass
        return None

    def _wait_for_new_hwnd(self, before, timeout=5.0):
        """Wartet bis zu `timeout` Sekunden auf ein NEUES Top-Level-Fenster
        (Diff gegen Schnappschuss). Bevorzugt 'lolalytics' im Titel,
        dann Browser-Heuristik, sonst irgendein neues Fenster mit Titel.
        """
        browser_kw = ('chrome', 'firefox', 'edge', 'brave', 'opera',
                      'vivaldi', 'mozilla', 'arc')
        deadline = time.time() + timeout
        last_browser_candidate = None
        last_any_candidate = None
        while time.time() < deadline:
            current = _enum_top_level_hwnds()
            new = current - before
            for hwnd in new:
                t = _get_window_title(hwnd).lower()
                if not t:
                    continue
                if 'lolalytics' in t:
                    return hwnd
                if any(k in t for k in browser_kw):
                    last_browser_candidate = hwnd
                last_any_candidate = hwnd
            if last_browser_candidate is not None:
                # Browser-Fenster da -> noch kurz auf 'lolalytics'-Titel warten
                time.sleep(0.15)
                t = _get_window_title(last_browser_candidate).lower()
                if 'lolalytics' in t:
                    return last_browser_candidate
            time.sleep(0.1)
        return last_browser_candidate or last_any_candidate

    # ---------- Tab oeffnen ----------
    def open_lolalytics(self):
        self._open_lolalytics_tab()

    def open_vs(self):
        self._open_vs_tab()

    def _open_lolalytics_tab(self):
        # Frische URL bauen + gespeicherte Parameter (Items/Runen) mergen.
        # Fallback bei fehlendem Champion: letzte gespeicherte URL nehmen.
        fresh = self._build_lolalytics_url()
        if not fresh:
            saved = (self.tab_state.get('lolalytics') or {}).get('url')
            if not saved:
                return
            final_url = saved
        else:
            final_url = self._merge_url_with_saved_params(fresh, kind='base')
        self._open_managed_lolalytics_url(final_url, kind='base')

    def _open_vs_tab(self):
        # VS funktioniert nur wenn wir einen Lane-Gegner kennen. Der Button
        # ist in dem Fall ohnehin ausgeblendet; ueber Hotkey kann er aber
        # auch leer ausgeloest werden -> still abbrechen.
        fresh = self._build_vs_url()
        if not fresh:
            return
        final_url = self._merge_url_with_saved_params(fresh, kind='vs')
        self._open_managed_lolalytics_url(final_url, kind='vs')

    def _open_managed_lolalytics_url(self, final_url, kind):
        """Gemeinsame Fenster-Logik fuer Lolalytics-Buttons (Basis + VS).
        - Findet ein existierendes Lolalytics-Fenster und vergleicht die
          Seiten-Identitaet (Champion + ggf. Gegner). Selbe Seite -> nur
          fokussieren. Andere Seite -> silent schliessen + neues Fenster.
        - Persistiert die URL pro Seitentyp (basis vs vs).
        """
        with self._tab_lock:
            want_id = self._page_identity(final_url)

            # Schon ein lolalytics-Fenster offen? (entweder unseres oder
            # eines das wir finden koennen). -> "im gleichen Fenster bleiben"
            existing = self._open_hwnd if (self._open_hwnd and _hwnd_alive(self._open_hwnd)) else None
            if not existing:
                existing = self._find_lolalytics_hwnd()
            if existing:
                # Aktuelle URL des bestehenden Fensters per UI Automation lesen
                cur_url = _uia_read_browser_url(existing) or ''
                # Sanity-Check: ist das wirklich ein lolalytics-Fenster?
                # (HWND koennte stale sein - Browser hat das Fenster
                # zwischenzeitlich anderweitig verwendet). Wenn weder URL
                # noch Titel passen -> als "nicht offen" behandeln.
                title_low = (_get_window_title(existing) or '').lower()
                is_lola = ('lolalytics.com' in cur_url.lower()
                           or 'lolalytics' in title_low)
                if not is_lola:
                    # Stale HWND verwerfen und nochmal sauber suchen
                    self._open_hwnd = None
                    existing = self._find_lolalytics_hwnd()
                    if existing:
                        cur_url = _uia_read_browser_url(existing) or ''
            if existing:
                cur_id = self._page_identity(cur_url)
                self._debug(f"open[{kind}]: existing hwnd={existing} cur_id={cur_id} want_id={want_id}")
                if cur_id and want_id and cur_id == want_id:
                    # Gleiche Seite -> NUR fokussieren, keine Nav, kein Flash.
                    self._open_hwnd = existing
                    _hwnd_focus(existing)
                    return
                # Andere Seite -> altes Fenster silent schliessen und gleich
                # darunter ein neues mit korrekter URL oeffnen. So bleibt es
                # "ein" Lolalytics-Fenster zur Zeit.
                try:
                    _hwnd_close(existing)
                except Exception:
                    pass
                self._open_hwnd = None
                # Kurz warten, damit das HWND in _enum_top_level_hwnds() weg
                # ist - sonst greift unser HWND-Diff darunter daneben.
                time.sleep(0.18)

            # State persistieren (separater Slot fuer base und vs)
            state_key = 'lolalytics_vs' if kind == 'vs' else 'lolalytics'
            self.tab_state[state_key] = {
                'url': final_url,
                'ts': time.time(),
            }
            self._save_tab_state()

            # Schnappschuss VOR dem Oeffnen
            before = _enum_top_level_hwnds()

            # NEUES FENSTER oeffnen (deterministischer als open_new_tab).
            # WICHTIG: webbrowser.open_new() oeffnet bei laufendem Browser
            # oft nur einen Tab im bestehenden Fenster -> kein eigenes HWND
            # -> Tab-Schliessen + URL-Tracking gehen kaputt. Daher direkt
            # subprocess mit --new-window Flag des Default-Browsers.
            opened_new_win = False
            popen_proc = None
            try:
                opened_new_win, popen_proc = _open_url_new_window(final_url)
            except Exception:
                opened_new_win, popen_proc = (False, None)
            self._opened_browser_pid = popen_proc.pid if popen_proc else None
            self._debug(f"open[{kind}]: new_window={opened_new_win} pid={self._opened_browser_pid} url={final_url}")
            if not opened_new_win:
                try:
                    webbrowser.open_new(final_url)
                except Exception:
                    try:
                        webbrowser.open(final_url)
                    except Exception:
                        return

            # Auf neues HWND warten (im Hintergrund, blockiert die UI nicht).
            # Timeout grosszuegig (10s), denn Browser-Cold-Start kann dauern.
            threading.Thread(target=self._track_new_hwnd,
                             args=(before,), daemon=True).start()

    def _track_new_hwnd(self, before):
        """Laeuft im Hintergrund-Thread: ermittelt das neue HWND und speichert es."""
        new_hwnd = self._wait_for_new_hwnd(before, timeout=10.0)
        # Fallback: Browser hat evtl. nur ein Tab in bestehendem Fenster geoeffnet
        # -> kein neuer Top-Level. Dann suchen wir per Titel.
        if not new_hwnd:
            new_hwnd = self._find_lolalytics_hwnd()
        self._debug(f"track_new_hwnd: result={new_hwnd}")
        if not new_hwnd:
            return
        with self._tab_lock:
            if self._open_hwnd is None or not _hwnd_alive(self._open_hwnd):
                self._open_hwnd = new_hwnd
                self.root.after(0, lambda h=new_hwnd: _hwnd_focus(h))

    # ---------- Tab schliessen ----------
    def _release_held_modifiers(self):
        """Gibt die Modifier-Tasten frei, die der User von der Hotkey-Kombi
        evtl. noch haelt - sonst sieht der Browser bei Ctrl+W in Wirklichkeit
        Ctrl+Alt+Shift+W und ignoriert es."""
        for k in (KbKey.alt_l, KbKey.alt_r, KbKey.alt,
                  KbKey.shift_l, KbKey.shift_r, KbKey.shift,
                  KbKey.ctrl_l, KbKey.ctrl_r, KbKey.ctrl):
            try:
                self._kb.release(k)
            except Exception:
                pass

    def _close_lolalytics_tab(self):
        """Schliesst den lolalytics-Tab zuverlaessig - auch wenn HWND-Tracking
        versagt hat (Title-Fallback) und auch wenn der Browser fokussiert ist
        (AttachThreadInput-Trick + Win32-Tastatursimulation umgeht GlobalHotKeys).
        Wenn der Browser NICHT im Vordergrund ist, wird silent geschlossen
        (kein Fokus-Steal, kein Bildschirm-Flash).
        """
        with self._tab_lock:
            # 1) Zielfenster bestimmen: getracktes HWND oder per Titel suchen.
            #    Wenn das HWND-Tracking noch nicht fertig ist (Browser startet
            #    gerade), warten wir bis zu 1.5s in 100ms-Schritten -> sonst
            #    laeuft Alt+Shift+2 direkt nach Alt+Shift+1 ins Leere.
            target = self._open_hwnd if (self._open_hwnd and _hwnd_alive(self._open_hwnd)) else None
            if not target:
                target = self._find_lolalytics_hwnd()
            if not target:
                # Tracker evtl. noch nicht durch -> 400ms in 40ms-Schritten
                # warten. Mit dem PID-Fallback in _find_lolalytics_hwnd
                # sollte das fast nie passieren.
                deadline = time.time() + 0.4
                while time.time() < deadline and not target:
                    time.sleep(0.04)
                    if self._open_hwnd and _hwnd_alive(self._open_hwnd):
                        target = self._open_hwnd
                        break
                    target = self._find_lolalytics_hwnd()
            self._open_hwnd = None
            self._debug(f"close_lolalytics_tab target={target}")

            # Wenn wir gar kein Lolalytics-Fenster finden -> nichts zu tun
            if not target:
                return

            # 1b) Silent URL-Refresh via UI Automation (ohne Fokus)
            try:
                url = _uia_read_browser_url(target)
                if (url and isinstance(url, str)
                        and url.startswith('http')
                        and 'lolalytics.com' in url.lower()):
                    self.tab_state['lolalytics'] = {'url': url, 'ts': time.time()}
                    self._last_tracked_url = url
                    self._save_tab_state()
            except Exception:
                pass

            # 1c) Wenn der Browser nicht im Vordergrund ist -> KOMPLETT silent
            #     schliessen (WM_CLOSE, kein Fokuswechsel). So gibt es keinen
            #     Bildschirm-Flash, wenn der Tab z. B. via Hotkey aus dem
            #     Hintergrund geschlossen wird.
            try:
                fg_hwnd = _user32.GetForegroundWindow() if _IS_WINDOWS else 0
            except Exception:
                fg_hwnd = 0
            if not _IS_WINDOWS or int(fg_hwnd or 0) != int(target):
                try:
                    _hwnd_close(target)
                except Exception:
                    pass
                return

            # 2) Fenster zuverlaessig in den Vordergrund holen
            _hwnd_focus(target)
            time.sleep(0.28)

            # 3) Modifier freigeben (sonst Ctrl+Alt+Shift+W -> Ignored)
            _release_modifiers_winapi()
            try:
                self._release_held_modifiers()
            except Exception:
                pass
            time.sleep(0.05)

            # 4) URL einlesen (best effort - speichert User-Modifikationen am Build).
            #    Nur Fallback falls UI Automation nicht verfuegbar war.
            if not _UIA_AVAILABLE:
                try:
                    self._try_capture_url_focused()
                except Exception:
                    pass

            # 5) Sicherstellen, dass das Browser-Fenster wieder Fokus hat
            _hwnd_focus(target)
            time.sleep(0.10)
            _release_modifiers_winapi()
            time.sleep(0.03)

            # 6) Ctrl+W via Win32 keybd_event - umgeht pynput/Listener
            sent = _send_ctrl_w_winapi()

            # 7) Fallback (Nicht-Windows): pynput
            if not sent:
                try:
                    self._kb.press(KbKey.ctrl_l); self._kb.press('w')
                    self._kb.release('w');         self._kb.release(KbKey.ctrl_l)
                except Exception:
                    pass

            # 8) NOTBREMSE: Falls Ctrl+W nicht reagiert, nach 550ms WM_CLOSE.
            def _force_close(h=target):
                try:
                    if _hwnd_alive(h):
                        _hwnd_close(h)
                except Exception:
                    pass
            self.root.after(550, _force_close)

    def _try_capture_url_focused(self):
        """Setzt voraus, dass das richtige Fenster bereits fokussiert ist und
        die Modifier freigegeben sind. Liest die URL ueber die Adressleiste aus.
        Reines Best-Effort - schlaegt es fehl, ist das egal.
        """
        url = None
        try:
            self._kb.press(KbKey.ctrl_l); self._kb.press('l')
            self._kb.release('l');         self._kb.release(KbKey.ctrl_l)
            time.sleep(0.08)
            self._kb.press(KbKey.ctrl_l); self._kb.press('c')
            self._kb.release('c');         self._kb.release(KbKey.ctrl_l)
            time.sleep(0.10)
            try:
                url = self.root.clipboard_get()
            except Exception:
                url = None
            self._kb.press(KbKey.esc); self._kb.release(KbKey.esc)
            time.sleep(0.04)
        except Exception:
            url = None

        if (url and isinstance(url, str)
                and url.startswith('http')
                and 'lolalytics.com' in url.lower()):
            self.tab_state['lolalytics'] = {'url': url, 'ts': time.time()}
            self._save_tab_state()

    # ---------- Alle Browser schliessen ----------
    def _close_all_browsers(self):
        """Schliesst alle Top-Level-Fenster, deren Titel auf einen Browser passt."""
        with self._tab_lock:
            self._open_hwnd = None
            for hwnd in _enum_top_level_hwnds():
                title = _get_window_title(hwnd).lower()
                if not title:
                    continue
                if any(k in title for k in BROWSER_TITLE_KEYWORDS):
                    try:
                        _hwnd_close(hwnd)
                    except Exception:
                        pass

    # ---------- Hotkey-Handler ----------
    def on_hotkey_open_lolalytics(self):
        # Auf den Tk-Mainloop dispatchen, damit Tk-Aufrufe thread-safe sind.
        self.root.after(0, self._open_lolalytics_tab)

    def on_hotkey_open_vs(self):
        self.root.after(0, self._open_vs_tab)

    def on_hotkey_close_lolalytics(self):
        self.root.after(0, self._close_lolalytics_tab)

    def on_hotkey_close_all_browsers(self):
        self.root.after(0, self._close_all_browsers)

    # ---------- LoL Foreground Monitor (Auto-Close, wenn LoL aktiv wird) ----------
    def _start_lol_foreground_monitor(self):
        if not _IS_WINDOWS:
            return
        t = threading.Thread(target=self._lol_foreground_loop, daemon=True)
        t.start()

    def _is_lol_foreground(self):
        """True nur wenn das LAUFENDE SPIEL (League of Legends.exe) im
        Vordergrund ist. Der Client/Launcher (LeagueClientUx.exe) zaehlt
        absichtlich NICHT - dort soll das Tool nicht reinfunken.
        """
        exe = _foreground_process_name().lower()
        if not exe:
            return False
        return exe == LOL_GAME_EXE.lower()

    def _lol_foreground_loop(self):
        while not self._lol_monitor_stop.is_set():
            try:
                is_fg = self._is_lol_foreground()
                if is_fg and not self._lol_was_foreground:
                    # LoL-Game kommt in den Vordergrund -> Auto-Close ausloesen
                    self._debug("lol_game came to foreground")
                    self.root.after(0, self._on_lol_came_foreground)
                self._lol_was_foreground = is_fg
            except Exception:
                pass
            self._lol_monitor_stop.wait(0.6)

    def _on_lol_came_foreground(self):
        """Wird aufgerufen wenn DAS LAUFENDE SPIEL (nicht der Client!) in den
        Vordergrund kommt. Wenn 'Schwacher PC Modus' aktiv ist, fuehren wir
        einfach denselben Code wie Alt+Shift+3 aus (alle Browser silent
        schliessen). Kein Fokus-Stealing, kein Bildschirm-Flash.
        Default: AUS.
        """
        if not self.weak_pc_mode:
            return
        try:
            self._debug("auto-close: weak_pc_mode -> close_all_browsers")
            self._close_all_browsers()
        except Exception:
            pass
        # League-themed Toast oben links - sichtbar auch ueber LoL (gleiche
        # Topmost-Logik wie das Overlay selbst).
        try:
            self.root.after(120, self._show_weak_pc_popup)
        except Exception:
            pass

     
    # ---------- League-themed Toast Popup ----------
    # Witzige Botschaften (rotieren zufaellig). Kurz, gametypisch, nicht stoerend.
    _POPUP_LINES = (
    "Tab executed.",
    "Shutdown! Dein Tab war 700 Gold wert.",
    "Enemy Tab has been slain.",
    "Ace! Keine Tabs mehr übrig.",
    "Tab ohne Vision gehittet.",
    "Dein Tab wurde gegankt.",
    "Tab intet seit Minute 1.",
    "Tab hat FF15 gedrückt.",
    "Tab hat den Disconnect gespürt.",
    "Tab wurde reported.",
    
 
    "Tab hat versucht zu roamen… ",
    "Tab hat Baron versucht… ",
  
    "Tab hat keinen Stopwatch gekauft.",
    "Tab wurde von dir geoneshottet.",
    "Tab hat versucht zu splitpushen… ",
    "Tab wurde in der Champ Select getrollt.",

    "Tab vernichtet",
    "First Blood an deinen Tabs",
        
    "Tabs gekickt",
        
    "Fokus an. Tabs aus.",
       
    "Keine Tabs, Kein Tilt",

    "Tabs auf die Bench geschickt",
        
    "Ein Tab gefallen",
    )

    def _show_weak_pc_popup(self):
        """Mini-Toast oben links: 'Browser geschlossen'. ~1.2s, fade in/out,
        League-Farben (dunkles Hex + Gold). Wird immer als Topmost gezeichnet,
        sodass es ueber dem LoL-Fenster sichtbar bleibt (Borderless).
        """
        import random as _rand
        try:
            top = tk.Toplevel(self.root)
            top.overrideredirect(True)
            top.attributes('-topmost', True)
            try:
                top.attributes('-alpha', 0.0)
            except Exception:
                pass
            # Position oben links auf dem primaeren Monitor
            x, y = 28, 24
            top.geometry(f"+{x}+{y}")
            # League-Style: dunkles Hex-Blau + Gold-Border
            BG, GOLD, FG = "#0a1428", "#c8aa6e", "#f0e6d2"
            border = tk.Frame(top, bg=GOLD)
            border.pack()
            inner = tk.Frame(border, bg=BG, padx=14, pady=8)
            inner.pack(padx=2, pady=2)
            tk.Label(inner, text="\u25c6", bg=BG, fg=GOLD,
                     font=("Consolas", 12, "bold")).pack(side=tk.LEFT,
                                                          padx=(0, 8))
            tk.Label(inner, text=_rand.choice(self._POPUP_LINES),
                     bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
            # Zusaetzlich via Win32 Topmost setzen - hilft ueber LoL hinaus
            top.update_idletasks()
            if _IS_WINDOWS:
                try:
                    hwnd = int(top.winfo_id())
                    HWND_TOPMOST = -1
                    SWP_NOMOVE = 0x0002; SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010; SWP_SHOWWINDOW = 0x0040
                    _user32.SetWindowPos(
                        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                    )
                except Exception:
                    pass

            # Fade-in (8 Schritte a 18ms)
            def _fade_in(i=1, n=8):
                try:
                    top.attributes('-alpha', min(0.95, 0.95 * i / n))
                except Exception:
                    return
                if i < n:
                    top.after(18, lambda: _fade_in(i + 1, n))
            _fade_in()

            # Halten + Fade-out + Destroy (gesamt ~1.2s)
            def _fade_out(i=8):
                try:
                    top.attributes('-alpha', max(0.0, 0.95 * i / 8))
                except Exception:
                    pass
                if i > 0:
                    top.after(22, lambda: _fade_out(i - 1))
                else:
                    try:
                        top.destroy()
                    except Exception:
                        pass

            top.after(950, _fade_out)
        except Exception:
            pass

    def _close_all_lolalytics_silent(self):
        """Schliesst ALLE Top-Level-Fenster, deren Titel 'lolalytics' enthaelt,
        PLUS unser getracktes HWND (auch wenn der Titel sich geaendert hat).
        Komplett silent: kein Fokuswechsel, kein Bildschirm-Flash, nur WM_CLOSE.
        Vor dem Schliessen wird die zuletzt getrackte URL gesichert.
        """
        with self._tab_lock:
            targets = set()
            # 1) Getracktes Fenster (unsere Lolalytics-Instanz) zuerst
            if self._open_hwnd and _hwnd_alive(self._open_hwnd):
                targets.add(int(self._open_hwnd))
            # 2) Plus alle anderen Fenster mit 'lolalytics' im Titel
            for hwnd in _enum_top_level_hwnds():
                try:
                    title = _get_window_title(hwnd).lower()
                except Exception:
                    title = ''
                if title and 'lolalytics' in title:
                    targets.add(int(hwnd))

            for hwnd in targets:
                # Best-Effort URL-Refresh vor dem Schliessen (UIA, kein Fokus)
                try:
                    url = _uia_read_browser_url(hwnd)
                    if (url and isinstance(url, str)
                            and url.startswith('http')
                            and 'lolalytics.com' in url.lower()):
                        self.tab_state['lolalytics'] = {'url': url, 'ts': time.time()}
                        self._last_tracked_url = url
                except Exception:
                    pass
                try:
                    _hwnd_close(hwnd)
                except Exception:
                    pass
            self._open_hwnd = None
            try:
                self._save_tab_state()
            except Exception:
                pass

    # ---------- URL-Tracker (Hintergrund, UI Automation) ----------
    def _start_url_tracker(self):
        """Pollt die Adressleiste des getrackten Lolalytics-Fensters und
        speichert URL-Aenderungen automatisch. Kein Fokus, kein Clipboard.
        Erfordert 'comtypes' - sonst No-Op.
        """
        if not _IS_WINDOWS or not _UIA_AVAILABLE:
            return
        t = threading.Thread(target=self._url_tracker_loop, daemon=True)
        t.start()

    def _url_tracker_loop(self):
        # Erste Lesung schneller versuchen (Browser baut Seite gerade auf)
        first_attempt = True
        while not self._url_tracker_stop.is_set():
            try:
                hwnd = self._open_hwnd
                # Wenn unser getracktes HWND tot ist -> per Titel suchen
                if not (hwnd and _hwnd_alive(hwnd)):
                    hwnd = self._find_lolalytics_hwnd()
                    # Falls wir per Titel was finden, ueber bernehmen
                    if hwnd:
                        with self._tab_lock:
                            if not self._open_hwnd or not _hwnd_alive(self._open_hwnd):
                                self._open_hwnd = hwnd
                url = _uia_read_browser_url(hwnd) if hwnd else None
                if (url and isinstance(url, str)
                        and url.startswith('http')
                        and 'lolalytics.com' in url.lower()
                        and url != self._last_tracked_url):
                    self._last_tracked_url = url
                    self.tab_state['lolalytics'] = {'url': url, 'ts': time.time()}
                    self._debug(f"url_tracker: saved url={url}")
                    try:
                        self._save_tab_state()
                    except Exception:
                        pass
            except Exception:
                pass
            # Poll-Intervall: 1.5s ist ein guter Kompromiss aus
            # Reaktionszeit und CPU-Last.
            interval = 0.8 if first_attempt else 1.5
            first_attempt = False
            self._url_tracker_stop.wait(interval)

    def run(self):
        self.root.mainloop()


# =============================================================
# Settings-Fenster (Hotkeys anpassen)
# =============================================================
class SettingsWindow:
    """Schlankes Toplevel-Fenster im gleichen Dark-Stil wie das Overlay.
    Zeigt aktuelle Hotkeys an, erlaubt Rebinding per Klick + neue Tastenkombi.
    """

    BG       = ROW_BG
    BG_PANEL = "#11161f"
    BORDER   = "#1a2a3a"
    ACCENT   = "#c8aa6e"
    LABEL_FG = "#d4b87a"
    DIM_FG   = "#7a7259"
    BTN_BG   = "#1a2a3a"
    BTN_HOVER= "#23415e"
    REC_BG   = "#8a3a1a"

    def __init__(self, app):
        self.app = app
        self.root = app.root

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.attributes('-alpha', 0.96)
        self.win.configure(bg=self.BORDER)

        try:
            x = self.root.winfo_x() + 20
            y = self.root.winfo_y() + 30
        except Exception:
            x, y = 200, 200
        self.win.geometry(f"320x400+{x}+{y}")

        # Aeusserer Rahmen
        wrap = tk.Frame(self.win, bg=self.BG, bd=0)
        wrap.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Top-Bar (drag + close)
        top = tk.Frame(wrap, bg=self.BG, height=22)
        top.pack(fill=tk.X, padx=8, pady=(6, 0))
        title = tk.Label(top, text="⋮  Einstellungen", bg=self.BG, fg=self.ACCENT,
                         font=("Segoe UI", 9, "bold"))
        title.pack(side=tk.LEFT)
        close_lbl = tk.Label(top, text="✕", bg=self.BG, fg=self.ACCENT,
                             font=("Segoe UI", 10, "bold"), cursor="hand2")
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind("<Button-1>", lambda e: self.close())
        close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg="#f0e6d2"))
        close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg=self.ACCENT))

        self._drag_x = 0
        self._drag_y = 0
        for w in (top, title):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._drag)

        # Subline
        sub = tk.Label(wrap, text="Tastenkuerzel  -  klicke auf einen Hotkey um ihn neu zu binden",
                       bg=self.BG, fg=self.DIM_FG, font=("Segoe UI", 7))
        sub.pack(anchor=tk.W, padx=10, pady=(2, 6))

        # Hotkey-Liste
        list_frame = tk.Frame(wrap, bg=self.BG_PANEL, bd=1, relief="solid",
                              highlightthickness=0)
        list_frame.pack(fill=tk.X, padx=10, pady=2)
        list_frame.configure(highlightbackground=self.BORDER)

        self.row_buttons = {}
        order = ['toggle_overlay', 'open_lolalytics', 'open_vs', 'close_tab', 'close_all_browsers']
        for i, action_id in enumerate(order):
            self._build_row(list_frame, action_id, HOTKEY_LABELS.get(action_id, action_id),
                            top=(i == 0))

        # === Optionen-Sektion (Schwacher-PC-Modus + URL-Tracking-Status) ===
        opt_frame = tk.Frame(wrap, bg=self.BG_PANEL, bd=1, relief="solid",
                             highlightthickness=0)
        opt_frame.configure(highlightbackground=self.BORDER)
        opt_frame.pack(fill=tk.X, padx=10, pady=(8, 2))

        # Toggle: Schwacher PC Modus
        toggle_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        toggle_row.pack(fill=tk.X, padx=6, pady=(6, 3))
        tk.Label(toggle_row, text="Schwacher PC Modus",
                 bg=self.BG_PANEL, fg=self.LABEL_FG,
                 font=("Segoe UI", 8), anchor='w').pack(side=tk.LEFT)
        self.weak_btn = tk.Label(toggle_row,
                                 text=self._weak_label(self.app.weak_pc_mode),
                                 bg=self._weak_bg(self.app.weak_pc_mode),
                                 fg="#f0e6d2",
                                 font=("Consolas", 8, "bold"),
                                 padx=10, pady=2, cursor="hand2")
        self.weak_btn.pack(side=tk.RIGHT)
        self.weak_btn.bind("<Button-1>", lambda e: self._toggle_weak_pc())

        hint1 = tk.Label(opt_frame,
                         text="AN  =  beim Spielstart (im Match!) werden\n"
                              "         alle Browser lautlos geschlossen.\n"
                              "         Im Client/Lobby passiert NICHTS.",
                         bg=self.BG_PANEL, fg=self.DIM_FG, font=("Segoe UI", 7),
                         justify=tk.LEFT, anchor='w')
        hint1.pack(fill=tk.X, padx=8, pady=(0, 4))

        # Toggle: Debug-Modus (schreibt lol_tool_debug.log)
        dbg_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        dbg_row.pack(fill=tk.X, padx=6, pady=(2, 3))
        tk.Label(dbg_row, text="Debug-Modus (Log)",
                 bg=self.BG_PANEL, fg=self.LABEL_FG,
                 font=("Segoe UI", 8), anchor='w').pack(side=tk.LEFT)
        self.debug_btn = tk.Label(dbg_row,
                                  text=self._weak_label(self.app.debug_mode),
                                  bg=self._weak_bg(self.app.debug_mode),
                                  fg="#f0e6d2",
                                  font=("Consolas", 8, "bold"),
                                  padx=10, pady=2, cursor="hand2")
        self.debug_btn.pack(side=tk.RIGHT)
        self.debug_btn.bind("<Button-1>", lambda e: self._toggle_debug())
        dbg_hint = tk.Label(opt_frame,
                            text="AN  =  schreibt Diagnose-Log in\n"
                                 "         lol_tool_debug.log neben der EXE",
                            bg=self.BG_PANEL, fg=self.DIM_FG, font=("Segoe UI", 7),
                            justify=tk.LEFT, anchor='w')
        dbg_hint.pack(fill=tk.X, padx=8, pady=(0, 4))

        # URL-Tracking Status
        track_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        track_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(track_row, text="Live-URL-Tracking",
                 bg=self.BG_PANEL, fg=self.LABEL_FG,
                 font=("Segoe UI", 8), anchor='w').pack(side=tk.LEFT)
        if _UIA_AVAILABLE:
            status_txt = "AKTIV"
            status_bg = "#1f5a2e"
        else:
            status_txt = "INAKTIV"
            status_bg = "#5a2e1f"
        tk.Label(track_row, text=status_txt, bg=status_bg, fg="#f0e6d2",
                 font=("Consolas", 8, "bold"), padx=10, pady=2).pack(side=tk.RIGHT)
        if not _UIA_AVAILABLE:
            tip = tk.Label(opt_frame,
                           text="Tipp:  pip install comtypes  -> aktiviert\n"
                                "Live-Speicherung deiner Item-/Rune-Aenderungen",
                           bg=self.BG_PANEL, fg=self.DIM_FG, font=("Segoe UI", 7),
                           justify=tk.LEFT, anchor='w')
            tip.pack(fill=tk.X, padx=8, pady=(0, 6))

        # Footer
        foot = tk.Frame(wrap, bg=self.BG)
        foot.pack(fill=tk.X, padx=10, pady=(10, 8))

        reset_btn = tk.Label(foot, text="↺  Auf Standard zuruecksetzen",
                             bg=self.BG, fg="#5fa8d3",
                             font=("Segoe UI", 7, "underline"),
                             cursor="hand2")
        reset_btn.pack(side=tk.LEFT)
        reset_btn.bind("<Button-1>", lambda e: self._reset_defaults())
        reset_btn.bind("<Enter>", lambda e: reset_btn.config(fg="#a3d0ef"))
        reset_btn.bind("<Leave>", lambda e: reset_btn.config(fg="#5fa8d3"))

        hint = tk.Label(foot, text="ESC bricht Aufnahme ab", bg=self.BG,
                        fg=self.DIM_FG, font=("Segoe UI", 6))
        hint.pack(side=tk.RIGHT)

        # Recording-State
        self._recording = None  # action_id, das gerade neu gebunden wird
        self.win.bind("<KeyPress>", self._on_keypress, add="+")
        self.win.focus_set()

    # ---------- UI ----------
    def _build_row(self, parent, action_id, label, top=False):
        row = tk.Frame(parent, bg=self.BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=(6 if top else 3, 3))

        name = tk.Label(row, text=label, bg=self.BG_PANEL, fg=self.LABEL_FG,
                        font=("Segoe UI", 8), anchor='w')
        name.pack(side=tk.LEFT)

        hk_text = self._format_hotkey(self.app.hotkeys.get(action_id, ''))
        btn = tk.Label(row, text=hk_text, bg=self.BTN_BG, fg="#f0e6d2",
                       font=("Consolas", 8, "bold"), padx=8, pady=2,
                       cursor="hand2")
        btn.pack(side=tk.RIGHT)
        btn.bind("<Button-1>", lambda e, a=action_id: self._start_recording(a))
        btn.bind("<Enter>", lambda e, b=btn, a=action_id:
                 b.config(bg=self.BTN_HOVER) if self._recording != a else None)
        btn.bind("<Leave>", lambda e, b=btn, a=action_id:
                 b.config(bg=self.BTN_BG) if self._recording != a else None)

        self.row_buttons[action_id] = btn

    # ---------- Schwacher-PC-Modus Toggle ----------
    @staticmethod
    def _weak_label(on):
        return "AN" if on else "AUS"

    @staticmethod
    def _weak_bg(on):
        return "#1f5a2e" if on else "#5a2e1f"

    def _toggle_weak_pc(self):
        self.app.weak_pc_mode = not self.app.weak_pc_mode
        try:
            self.app.save_config()
        except Exception:
            pass
        self.weak_btn.config(text=self._weak_label(self.app.weak_pc_mode),
                             bg=self._weak_bg(self.app.weak_pc_mode))

    def _toggle_debug(self):
        self.app.debug_mode = not self.app.debug_mode
        try:
            self.app.save_config()
        except Exception:
            pass
        self.debug_btn.config(text=self._weak_label(self.app.debug_mode),
                              bg=self._weak_bg(self.app.debug_mode))
        # Beim Aktivieren: Marker-Zeile schreiben (verifiziert dass das Log
        # ueberhaupt funktioniert + zeigt Setup-Infos).
        if self.app.debug_mode:
            try:
                exe = _find_default_browser_exe() if _IS_WINDOWS else None
                kind = _browser_kind_from_exe(exe) if exe else None
                self.app._debug(
                    f"=== Debug-Modus aktiviert === "
                    f"OS=win:{_IS_WINDOWS} UIA={_UIA_AVAILABLE} "
                    f"browser={kind} exe={exe}")
            except Exception:
                pass

    @staticmethod
    def _format_hotkey(combo):
        if not combo:
            return '— nicht gesetzt —'
        out = (combo.replace('<alt>',   'Alt')
                    .replace('<shift>', 'Shift')
                    .replace('<ctrl>',  'Ctrl')
                    .replace('<cmd>',   'Cmd')
                    .replace('<enter>', 'Enter')
                    .replace('<space>', 'Space')
                    .replace('<tab>',   'Tab'))
        parts = []
        for p in out.split('+'):
            p = p.strip()
            # F-Tasten: <f1> -> F1
            if p.startswith('<') and p.endswith('>') and len(p) > 2 \
                    and p[1] == 'f' and p[2:-1].isdigit():
                parts.append('F' + p[2:-1])
            elif len(p) == 1:
                parts.append(p.upper())
            else:
                parts.append(p)
        return ' + '.join(parts)

    # ---------- Drag ----------
    def _start_drag(self, e):
        self._drag_x = e.x_root - self.win.winfo_x()
        self._drag_y = e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.win.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ---------- Recording ----------
    def _start_recording(self, action_id):
        # vorherige Aufnahme abbrechen
        if self._recording and self._recording in self.row_buttons:
            self.row_buttons[self._recording].config(
                text=self._format_hotkey(self.app.hotkeys.get(self._recording, '')),
                bg=self.BTN_BG)
        self._recording = action_id
        btn = self.row_buttons[action_id]
        btn.config(text='►  Taste druecken ...', bg=self.REC_BG)
        self.win.focus_set()

    def _on_keypress(self, event):
        if self._recording is None:
            return
        key = event.keysym
        if key in ('Alt_L', 'Alt_R', 'Shift_L', 'Shift_R',
                   'Control_L', 'Control_R', 'Super_L', 'Super_R',
                   'Caps_Lock', 'Num_Lock', 'Meta_L', 'Meta_R'):
            return
        # Esc -> Abbruch
        if key == 'Escape':
            btn = self.row_buttons[self._recording]
            btn.config(text=self._format_hotkey(self.app.hotkeys.get(self._recording, '')),
                       bg=self.BTN_BG)
            self._recording = None
            return

        state = event.state
        parts = []
        # state-Bits: 0x1 Shift, 0x4 Control, 0x20000 Alt (Windows)
        if state & 0x4:
            parts.append('<ctrl>')
        if state & 0x20000 or state & 0x8:
            parts.append('<alt>')
        if state & 0x1:
            parts.append('<shift>')

        special_map = {
            'Return':    '<enter>',
            'space':     '<space>',
            'Tab':       '<tab>',
            'BackSpace': '<backspace>',
            'Delete':    '<delete>',
            'Insert':    '<insert>',
            'Home':      '<home>',
            'End':       '<end>',
            'Prior':     '<page_up>',
            'Next':      '<page_down>',
            'Up':        '<up>',
            'Down':      '<down>',
            'Left':      '<left>',
            'Right':     '<right>',
        }
        if key in special_map:
            key_name = special_map[key]
        elif len(key) == 1:
            key_name = key.lower()
        elif key.startswith('F') and key[1:].isdigit():
            key_name = '<' + key.lower() + '>'
        else:
            key_name = key.lower()

        parts.append(key_name)
        combo = '+'.join(parts)

        # Doppelt vergeben? -> abbrechen
        for other_id, other_combo in self.app.hotkeys.items():
            if other_id != self._recording and other_combo == combo:
                btn = self.row_buttons[self._recording]
                btn.config(text='bereits vergeben!', bg="#7a1a1a")
                self.win.after(900, lambda a=self._recording: self._reset_button(a))
                self._recording = None
                return

        # Speichern + Listener neu aufbauen
        self.app.hotkeys[self._recording] = combo
        self.app.save_config()
        btn = self.row_buttons[self._recording]
        btn.config(text=self._format_hotkey(combo), bg=self.BTN_BG)
        self._recording = None
        self.app._apply_hotkeys()

    def _reset_button(self, action_id):
        if action_id in self.row_buttons:
            self.row_buttons[action_id].config(
                text=self._format_hotkey(self.app.hotkeys.get(action_id, '')),
                bg=self.BTN_BG)

    def _reset_defaults(self):
        self.app.hotkeys = dict(DEFAULT_HOTKEYS)
        self.app.save_config()
        self.app._apply_hotkeys()
        for action_id, btn in self.row_buttons.items():
            btn.config(text=self._format_hotkey(self.app.hotkeys.get(action_id, '')),
                       bg=self.BTN_BG)
        self._recording = None

    def close(self):
        self._recording = None
        try:
            self.win.destroy()
        except Exception:
            pass
        self.app._settings_window = None


if __name__ == "__main__":
    setup_autostart()
    app = OverlayApp()
    app.run()