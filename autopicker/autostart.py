"""Opt-in visible Windows Startup shortcut, rather than hidden persistence."""
import os
from pathlib import Path
import subprocess
import sys


def quote_ps(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    if sys.platform != "win32":
        raise SystemExit("Nur Windows")
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    target = startup / "LoL Autopicker 2.lnk"
    if "--remove" in sys.argv:
        target.unlink(missing_ok=True)
        print("Autostart entfernt. Programm und Einstellungen bleiben erhalten.")
        return
    root = Path(__file__).resolve().parent
    python = root / ".venv/Scripts/pythonw.exe"
    if not python.exists():
        raise SystemExit("Zuerst Setup.bat ausführen.")
    if '"' in str(root):
        raise ValueError("Ungültiger Installationspfad")
    startup.mkdir(parents=True, exist_ok=True)
    script = ("$w=New-Object -ComObject WScript.Shell;"
              f"$s=$w.CreateShortcut({quote_ps(target)});"
              f"$s.TargetPath={quote_ps(python)};"
              f"$s.Arguments={quote_ps(chr(34) + str(root / 'Autopicker.py') + chr(34))};"
              f"$s.WorkingDirectory={quote_ps(root)};"
              f"$s.IconLocation={quote_ps(str(root / 'assets/icon.ico'))};"
              "$s.Description='LoL Autopicker (lokal)';$s.Save()")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=True)
    print("Autostart für deine nächste Windows-Anmeldung aktiviert (ohne Administratorrechte).")
    print("Alte LoLHelper.bat in shell:startup bei Bedarf selbst entfernen, damit die alte EXE nicht zusätzlich startet.")


if __name__ == "__main__":
    main()