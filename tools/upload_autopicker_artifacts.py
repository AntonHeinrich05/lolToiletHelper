"""Upload only reviewed public deliverables; no credentials or user state in bundle."""
import json
import mimetypes
import os
from pathlib import Path
import uuid
from dotenv import load_dotenv
import requests

load_dotenv("/app/backend/.env")
base = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
url = base.rstrip("/") + "/objstore/api/v1/storage"
response = requests.post(url + "/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
response.raise_for_status()
key = response.json()["storage_key"]
manifest_path = Path("/app/backend/autopicker_artifacts.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
for filename in ("LoL-Autopicker-2.1-Originaldesign.zip", "LoL-Autopicker-Icon.png", "LoL-Autopicker-Icon.ico", "README.md", "SHA256.txt"):
    path = Path("/app/downloads") / filename
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    storage_path = f"lol-autopicker/uploads/public-release/{uuid.uuid4()}{path.suffix}"
    result = requests.put(url + "/objects/" + storage_path, data=path.read_bytes(),
                          headers={"X-Storage-Key": key, "Content-Type": content_type}, timeout=120)
    result.raise_for_status()
    manifest[filename] = {"path": result.json()["path"], "content_type": content_type, "size": path.stat().st_size}
    print("Gespeichert:", filename, path.stat().st_size, "Bytes")
Path("/app/backend/autopicker_artifacts.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")