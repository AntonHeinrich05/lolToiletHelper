"""Public deliverables explicitly requested by the project owner: fixed files from /app/downloads only."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/autopicker")
DOWNLOADS = Path(__file__).resolve().parents[1] / "downloads"
CONTENT_TYPES = {".zip": "application/zip", ".png": "image/png", ".ico": "image/vnd.microsoft.icon",
                 ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8"}


@router.get("/download/{filename}")
def download(filename: str):
    path = DOWNLOADS / filename
    if "/" in filename or "\\" in filename or filename.startswith(".") or path.suffix not in CONTENT_TYPES or not path.is_file():
        raise HTTPException(404, "Datei nicht gefunden")
    return FileResponse(path, media_type=CONTENT_TYPES[path.suffix], filename=filename,
                        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})


@router.get("/downloads")
def listing():
    return sorted(p.name for p in DOWNLOADS.iterdir() if p.is_file() and p.suffix in CONTENT_TYPES)
