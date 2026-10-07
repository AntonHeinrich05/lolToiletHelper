"""Update from GitHub: newest branch (latest commit) -> archive download -> update_apply.py replaces the files after exit."""
import io
import json
import logging
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .storage import read_json

LOG = logging.getLogger(__name__)
REPO = "AntonHeinrich05/lolToiletHelper"
API = "https://api.github.com"
VERSION_FILE = "version.json"


def _get(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": "LoLAutopicker-Updater", "Accept": "application/vnd.github+json"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request, timeout=timeout) as response:
        return response.read(64 * 2 ** 20)


def installed(root):
    """{'sha', 'branch', 'date'} written by the last update; empty for a manual installation."""
    value = read_json(Path(root) / VERSION_FILE, {})
    return value if isinstance(value.get("sha"), str) else {}


def describe(info):
    if not info:
        return "Installierte Version: unbekannt (manuell eingerichtet)"
    return f"Installiert: {info.get('branch', '?')} @ {info['sha'][:7]} · {str(info.get('date', ''))[:10]}"


def latest(repo=REPO):
    """The branch whose last commit is the newest one of the repository."""
    branches = json.loads(_get(f"{API}/repos/{repo}/branches?per_page=100"))
    best = None
    for branch in branches:
        commit = json.loads(_get(f"{API}/repos/{repo}/commits/{branch['commit']['sha']}"))
        date = commit["commit"]["committer"]["date"]
        if best is None or date > best["date"]:
            best = {"branch": branch["name"], "sha": commit["sha"], "date": date,
                    "message": (commit["commit"].get("message") or "").splitlines()[0][:80]}
    if best is None:
        raise ValueError("Keine Branches im Repository gefunden")
    return best


def check(root, repo=REPO):
    newest = latest(repo)
    current = installed(root)
    newest["available"] = current.get("sha") != newest["sha"]
    return newest


def download(info, repo=REPO):
    """Downloads the commit archive and returns the extracted program folder (the one with Autopicker.py)."""
    data = _get(f"https://codeload.github.com/{repo}/zip/{info['sha']}", timeout=180)
    target = Path(tempfile.mkdtemp(prefix="lolautopicker-update-"))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(target)
    source = next(iter(sorted(target.rglob("Autopicker.py"))), None)
    if source is None:
        raise ValueError("Archiv enthält keinen Autopicker-Ordner")
    for batch in source.parent.glob("*.bat"):  # cmd.exe wants CRLF (goto/labels misbehave with LF-only files)
        batch.write_bytes(batch.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    (source.parent / VERSION_FILE).write_text(json.dumps({k: info[k] for k in ("sha", "branch", "date")}, indent=2), encoding="utf-8")
    return source.parent


def launch_apply(root, source):
    """Starts update_apply.py detached; the caller quits right afterwards so the files can be replaced."""
    root = Path(root)
    python = root / ".venv/Scripts/python.exe"
    if not python.exists():
        python = Path(sys.executable)
    args = [str(python), str(root / "update_apply.py"), str(source), str(root), str(os.getpid())]
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    subprocess.Popen(args, cwd=str(root), creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    LOG.info("Update wird nach dem Beenden eingespielt: %s -> %s", source, root)
