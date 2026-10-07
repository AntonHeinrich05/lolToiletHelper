"""Single instance and private local storage; no elevation or Defender changes."""
import ctypes
import subprocess
import sys
from ctypes import wintypes


class SingleInstance:
    def __init__(self, directory):
        self.handle = None
        self.file = None
        if sys.platform == "win32":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            self.kernel.CreateMutexW.restype = wintypes.HANDLE
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.handle = self.kernel.CreateMutexW(None, False, "Local\\LoLAutopicker2")
            self.acquired = bool(self.handle) and ctypes.get_last_error() != 183
        else:
            import fcntl
            directory.mkdir(parents=True, exist_ok=True)
            self.file = open(directory / "instance.lock", "w")
            try:
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.acquired = True
            except OSError:
                self.acquired = False

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        if self.file:
            self.file.close()


def private_directory(directory):
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        directory.chmod(0o700)
        return
    # Limit the application's own data directory, never antivirus/system directories.
    who = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    import csv
    sid = next(csv.reader(who.stdout.splitlines()))[-1]
    if not sid.startswith("S-1-"):
        raise OSError("Benutzer-SID konnte nicht ermittelt werden")
    subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                   check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def bundle_dir():
    from pathlib import Path
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))