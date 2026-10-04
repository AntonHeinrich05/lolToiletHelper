"""Backend tests for the autopicker download/listing endpoints."""
import io
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://lol-picker-fix.preview.emergentagent.com").rstrip("/")
ZIP_NAME = "LoL-Autopicker-2.2-Verbindungsfix.zip"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


# --- listing ---
def test_listing_returns_zip(api):
    r = api.get(f"{BASE_URL}/api/autopicker/downloads", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert ZIP_NAME in data


# --- download zip ---
def test_download_zip_headers_and_valid_zip(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/{ZIP_NAME}", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/zip"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ZIP_NAME in cd
    body = r.content
    assert len(body) > 1000
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        names = z.namelist()
    assert "LoL-Autopicker-2.2/lolpicker/lcu.py" in names


# --- error cases ---
def test_download_traversal_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/../server.py", timeout=15, allow_redirects=False)
    # Traversal must never return a Python source file.
    assert r.status_code == 404
    assert "application/zip" not in r.headers.get("content-type", "")


def test_download_missing_file_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/does-not-exist.zip", timeout=15)
    assert r.status_code == 404


def test_download_disallowed_extension_404(api):
    r = api.get(f"{BASE_URL}/api/autopicker/download/server.py", timeout=15)
    assert r.status_code == 404
