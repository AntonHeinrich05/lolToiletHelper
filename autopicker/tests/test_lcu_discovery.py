"""lcu.py: credential discovery from LeagueClientUx command line, lockfile fallback and stale lockfiles."""
import os
from types import SimpleNamespace

import psutil

from lolpicker import lcu


def _fake_process(pid, name, cmdline=(), exe=""):
    return SimpleNamespace(info={"pid": pid, "name": name}, cmdline=lambda: list(cmdline), exe=lambda: exe)


def test_cmdline_of_ux_process_wins_over_lockfile(monkeypatch, tmp_path):
    lockfile = tmp_path / "lockfile"
    lockfile.write_text(f"LeagueClient:{os.getpid()}:5000:lockpw:https", encoding="utf-8")
    processes = [_fake_process(4, "explorer.exe"),
                 _fake_process(7, "LeagueClientUx.exe", ["LeagueClientUx.exe", "--app-port=6100", "--remoting-auth-token=cmdpw", "--app-pid=7"])]
    monkeypatch.setattr(lcu.psutil, "process_iter", lambda _attrs: processes)
    found = lcu.discover(str(lockfile))
    assert found == lcu.Credentials(6100, "cmdpw", 7)


def test_lockfile_fallback_and_stale_pid(monkeypatch, tmp_path):
    lockfile = tmp_path / "lockfile"
    lockfile.write_text(f"LeagueClient:{os.getpid()}:5000:lockpw:https", encoding="utf-8")
    monkeypatch.setattr(lcu.psutil, "process_iter", lambda _attrs: [_fake_process(9, "LeagueClient.exe", exe=str(tmp_path / "LeagueClient.exe"))])
    assert lcu.discover("") == lcu.Credentials(5000, "lockpw", os.getpid())

    dead = max(psutil.pids()) + 50000
    lockfile.write_text(f"LeagueClient:{dead}:5000:lockpw:https", encoding="utf-8")
    assert lcu.discover("") is None


def test_parse_cmdline_rejects_incomplete_arguments():
    assert lcu.parse_cmdline(["LeagueClientUx.exe", "--app-port=6100"]) is None
    assert lcu.parse_cmdline(None) is None
