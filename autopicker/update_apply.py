"""Runs detached after the Autopicker quit: waits for the old process, copies the update, installs dependencies, restarts."""
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KEEP = {".venv", "native_manifests", "__pycache__"}


def apply(source, root):
    """Copies the new program folder over the installation; .venv and native_manifests stay untouched."""
    source, root = Path(source), Path(root)
    for item in source.iterdir():
        if item.name in KEEP:
            continue
        dest = root / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, dest)


def main():
    source, root, pid = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "LoLAutopicker"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "update.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        import psutil
        for _ in range(300):
            if not psutil.pid_exists(pid):
                break
            time.sleep(0.2)
    except ImportError:
        time.sleep(3)
    try:
        apply(source, root)
        logging.info("Dateien aktualisiert: %s", root)
        python = root / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
        if python.exists():
            result = subprocess.run([str(python), "-m", "pip", "install", "-q", "."], cwd=str(root), capture_output=True, text=True)
            logging.info("pip install: %s %s", result.returncode, (result.stderr or "")[-400:])
        launcher = root / (".venv/Scripts/pythonw.exe" if sys.platform == "win32" else ".venv/bin/python")
        if launcher.exists():
            subprocess.Popen([str(launcher), str(root / "Autopicker.py")], cwd=str(root), close_fds=True)
            logging.info("Autopicker neu gestartet")
    except Exception:  # noqa: BLE001 - the log is the only place a detached process can report to
        logging.exception("Update fehlgeschlagen")
    finally:
        shutil.rmtree(source.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
