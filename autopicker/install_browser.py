"""Explicit per-user Native Messaging registration. No elevation required."""
import json
from pathlib import Path
import re
import sys

HOST = "de.lolautopicker.bridge"
CHROMIUM_KEYS = [r"Software\Google\Chrome", r"Software\Chromium", r"Software\Microsoft\Edge",
                 r"Software\BraveSoftware\Brave-Browser", r"Software\Vivaldi", r"Software\Opera Software"]


def register(root, family, extension_ids=()):
    import winreg
    path = root / "native_manifests"
    path.mkdir(exist_ok=True)
    manifest = {"name": HOST, "description": "LoL Autopicker local browser bridge", "type": "stdio",
                "path": str(root / "native_host.bat")}
    if family == "firefox":
        manifest["allowed_extensions"] = ["lolautopicker@local.invalid"]
        keys = [r"Software\Mozilla"]
    else:
        if not extension_ids or any(not re.fullmatch("[a-p]{32}", eid) for eid in extension_ids):
            raise ValueError("Erweiterungs-ID: genau 32 Kleinbuchstaben a-p (unter Erweiterungsdetails)")
        target = path / "chromium.json"
        existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        origins = existing.get("allowed_origins", []) + [f"chrome-extension://{eid}/" for eid in extension_ids]
        manifest["allowed_origins"] = sorted(set(origins))
        keys = CHROMIUM_KEYS
    target = path / f"{family}.json"
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for key in keys:
        # Both views avoid stale 32-bit registrations shadowing a 64-bit install.
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key + "\\NativeMessagingHosts\\" + HOST,
                                    0, winreg.KEY_SET_VALUE | view) as entry:
                winreg.SetValueEx(entry, "", 0, winreg.REG_SZ, str(target))


def uninstall():
    import winreg
    for base in CHROMIUM_KEYS + [r"Software\Mozilla"]:
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, base + "\\NativeMessagingHosts\\" + HOST, view, 0)
            except FileNotFoundError:
                pass


def main():
    if sys.platform != "win32":
        raise SystemExit("Diese Einrichtung ist für Windows.")
    root = Path(__file__).resolve().parent
    if "--remove" in sys.argv:
        uninstall()
        print("Browser-Bridge-Registrierungen entfernt. Erweiterungen separat im Browser entfernen.")
        return
    if not (root / ".venv/Scripts/python.exe").exists():
        raise SystemExit("Zuerst Setup.bat ausführen.")
    print("Erweiterung zuerst im Browser laden (README Abschnitt 3).")
    choice = input("Browser: [1] Chrome/Edge/Brave/Vivaldi/Opera [2] Firefox: ").strip()
    if choice == "1":
        ids = [eid.strip() for eid in input("Erweiterungs-ID(s), mehrere mit Komma trennen: ").split(",")]
        register(root, "chromium", ids)
    elif choice == "2":
        register(root, "firefox")
    else:
        raise SystemExit("Abgebrochen; keine Änderungen.")
    print("Registriert. Autopicker starten, Erweiterung neu laden und ihr Symbol anklicken.")
    print("Für weitere Browser/Profil-IDs dieses Skript erneut ausführen.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Einrichtung fehlgeschlagen: {error}", file=sys.stderr)
        raise SystemExit(1) from error