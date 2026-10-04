"""Public deliverables explicitly requested by the project owner.

Only a fixed manifest of source/docs/icons is exposed, never arbitrary paths or
user uploads. Object-store credentials stay on the server.
"""
import io
import json
import os
from pathlib import Path
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import requests

router = APIRouter(prefix="/autopicker")
BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = BASE.rstrip("/") + "/objstore/api/v1/storage"
MANIFEST = Path(__file__).parent / "autopicker_artifacts.json"
_key = None
_lock = threading.Lock()


def storage_key():
    global _key
    with _lock:
        if _key is None:
            response = requests.post(STORAGE_URL + "/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
            response.raise_for_status()
            _key = response.json()["storage_key"]
        return _key


@router.get("/download/{filename}")
def download(filename: str):
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Download noch nicht bereit") from error
    artifact = manifest.get(filename)
    if not artifact:
        raise HTTPException(404, "Datei nicht gefunden")
    try:
        response = requests.get(STORAGE_URL + "/objects/" + artifact["path"],
                                headers={"X-Storage-Key": storage_key()}, timeout=60)
        response.raise_for_status()
    except (requests.RequestException, KeyError) as error:
        raise HTTPException(502, "Dateispeicher vorübergehend nicht erreichbar") from error
    return StreamingResponse(io.BytesIO(response.content), media_type=artifact["content_type"],
                             headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                      "Content-Length": str(len(response.content)),
                                      "Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})