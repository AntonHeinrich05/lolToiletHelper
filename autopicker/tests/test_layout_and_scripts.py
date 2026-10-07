"""Archive layout and launcher/install script presence checks."""
from pathlib import Path


# packaging basics: startup/install scripts and extension folders should be present
def test_archive_layout_contains_required_files(bundle_dir):
    required = [
        "Autopicker.py",
        "Start.bat",
        "update_apply.py",
        "Setup.bat",
        "Diagnose.bat",
        "install_browser.py",
        "autostart.py",
        "extension/shared/background.js",
        "extension/chromium/manifest.json",
        "extension/firefox/manifest.json",
    ]
    for rel in required:
        assert (bundle_dir / rel).exists(), f"Missing: {rel}"
