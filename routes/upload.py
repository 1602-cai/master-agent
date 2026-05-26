"""File upload routes."""
from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from routes.deps import UPLOAD_DIR, MAX_UPLOAD_BYTES, resolve_under, safe_filename

router = APIRouter()


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload source file."""
    file_id = str(uuid.uuid4())[:8]
    upload_dir = UPLOAD_DIR / file_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = safe_filename(file.filename, "upload")
    file_path = resolve_under(upload_dir, filename)
    content = await file.read()
    if len(content) == 0:
        return JSONResponse({"error": "文件为空（0字节），请检查文件是否完整"}, status_code=400)
    if len(content) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "文件过大，最大支持 50MB"}, status_code=413)
    with open(file_path, "wb") as f:
        f.write(content)

    return JSONResponse({
        "file_id": file_id,
        "filename": filename,
        "size": len(content),
    })


@router.post("/api/upload_url")
async def upload_url(payload: dict):
    """Register a URL as a source."""
    url = payload.get("url", "")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return JSONResponse({"error": "Only http/https URLs are allowed"}, status_code=400)
    file_id = str(uuid.uuid4())[:8]
    return JSONResponse({
        "file_id": file_id,
        "filename": url,
        "size": 0,
    })
