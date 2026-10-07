"""Backend tests for the autopicker download/listing endpoints."""
import hashlib
import io
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ZIP_NAME = "LoL-Autopicker-2.7.1.zip"
ZIP_PREFIX = "LoL-Autopicker-2.7.1"  # 2.7.0 (Zauber vorab, Ban-Vorschläge, Hardcounter, Alt+Shift+4)


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def zip_body(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/{ZIP_NAME}", timeout=60)
    assert r.status_code == 200, r.status_code
    return r


# --- listing ---
def test_listing_returns_zip(api):
    r = api.get(f"{BASE_URL}/api/autopicker/downloads", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert ZIP_NAME in data
    assert "README.md" in data
    assert "SHA256.txt" in data


# --- download zip ---
def test_download_zip_headers(zip_body):
    r = zip_body
    assert r.headers.get("content-type") == "application/zip"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ZIP_NAME in cd
    assert len(r.content) > 1000


def test_download_zip_sha256_matches_file(zip_body):
    sha = hashlib.sha256(zip_body.content).hexdigest()
    # SHA256.txt contains lines like "<hash>  LoL-Autopicker-2.6.0.zip"
    sha_file = "/app/downloads/SHA256.txt"
    expected = None
    with open(sha_file) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1] == ZIP_NAME:
                expected = parts[0]
                break
    assert expected is not None, f"{ZIP_NAME} not listed in SHA256.txt"
    assert sha == expected, f"sha mismatch: {sha} vs {expected}"


def test_download_zip_contains_expected_files(zip_body):
    with zipfile.ZipFile(io.BytesIO(zip_body.content)) as z:
        names = z.namelist()
        assert f"{ZIP_PREFIX}/README.md" in names
        assert f"{ZIP_PREFIX}/Start.bat" in names
        assert f"{ZIP_PREFIX}/lolpicker/lcu.py" in names
        assert f"{ZIP_PREFIX}/lolpicker/lolalytics.py" in names
        assert f"{ZIP_PREFIX}/lolpicker/runes.py" in names
        assert f"{ZIP_PREFIX}/lolpicker/loadout_ui.py" in names
        bg_path = f"{ZIP_PREFIX}/extension/chromium/background.js"
        assert bg_path in names
        bg = z.read(bg_path).decode("utf-8", errors="replace")
        assert "close_lolalytics" in bg
        # 2.7.0 manifest version check
        manifest_path = f"{ZIP_PREFIX}/extension/chromium/manifest.json"
        assert manifest_path in names
        manifest = z.read(manifest_path).decode("utf-8", errors="replace")
        assert '"2.7.1"' in manifest, f"manifest.json missing version 2.7.0: {manifest[:200]}"


# --- error cases ---
def test_download_traversal_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/../server.py", timeout=15, allow_redirects=False)
    assert r.status_code == 404
    assert "application/zip" not in r.headers.get("content-type", "")


def test_download_missing_file_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/does-not-exist.zip", timeout=15)
    assert r.status_code == 404


def test_download_disallowed_extension_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/server.py", timeout=15)
    assert r.status_code == 404
