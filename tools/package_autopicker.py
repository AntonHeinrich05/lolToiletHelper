"""Produce reproducible source bundle, normalized Windows .bat endings and checksums."""
import hashlib
from pathlib import Path
import shutil
import zipfile

VERSION = "2.6.0"
NAME = f"LoL-Autopicker-{VERSION}.zip"
ROOT = Path(__file__).resolve().parents[1] / "autopicker"
for family in ("chromium", "firefox"):
    shutil.copy2(ROOT / "extension/shared/background.js", ROOT / f"extension/{family}/background.js")
OUT = Path(__file__).resolve().parents[1] / "downloads"
OUT.mkdir(exist_ok=True)
for old in OUT.glob("LoL-Autopicker-*.zip"):
    old.unlink()
excluded = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "native_manifests", ".ruff_cache"}
files = [f for f in ROOT.rglob("*") if f.is_file() and not excluded.intersection(f.relative_to(ROOT).parts)
         and not any(p.endswith(".egg-info") for p in f.parts) and f.suffix != ".pyc"]
with zipfile.ZipFile(OUT / NAME, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(files):
        name = str(path.relative_to(ROOT))
        data = path.read_bytes()
        if path.suffix == ".bat":
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        archive.writestr(f"LoL-Autopicker-{VERSION}/" + name, data)
shutil.copy2(ROOT / "assets/icon.png", OUT / "LoL-Autopicker-Icon.png")
shutil.copy2(ROOT / "assets/icon.ico", OUT / "LoL-Autopicker-Icon.ico")
shutil.copy2(ROOT / "README.md", OUT / "README.md")
digest = hashlib.sha256((OUT / NAME).read_bytes()).hexdigest()
(OUT / "SHA256.txt").write_text(f"{digest}  {NAME}\n", encoding="utf-8")
print("Paket erstellt:", NAME, digest)
