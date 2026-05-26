"""Project data routes — SVGs, notes, spec, events, download."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from routes.deps import (
    runtime, project_path_for, artifacts_dir_for,
    resolve_under, safe_filename, sanitize_svg,
)

router = APIRouter()


@router.get("/api/download/{job_id}")
async def download_pptx(job_id: str):
    """Download generated PPTX file."""
    pp = project_path_for(job_id)
    if not pp:
        return JSONResponse({"error": "Project not ready"}, status_code=404)
    exports_dir = Path(pp) / "exports"
    if exports_dir.exists():
        for f in exports_dir.glob("*.pptx"):
            return FileResponse(
                str(f),
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=f.name,
            )
    return JSONResponse({"error": "PPTX not ready"}, status_code=404)


@router.get("/api/projects/{job_id}/svgs")
async def list_svgs(job_id: str):
    """List all SVG pages for a project."""
    pp = project_path_for(job_id)
    if not pp:
        return JSONResponse({"error": "Project not ready"}, status_code=404)
    svg_dir = Path(pp) / "svg_output"
    svgs = []
    if svg_dir.exists():
        for svg_file in sorted(svg_dir.glob("*.svg")):
            svgs.append({
                "page": svg_file.stem,
                "filename": svg_file.name,
                "size": svg_file.stat().st_size,
            })
    return JSONResponse({"svgs": svgs, "total": len(svgs)})


@router.get("/api/projects/{job_id}/svg/{page}")
async def get_svg(job_id: str, page: str):
    """Get single SVG page content."""
    pp = project_path_for(job_id)
    if not pp:
        return JSONResponse({"error": "Project not ready"}, status_code=404)
    svg_dir = Path(pp) / "svg_output"
    page_key = Path(safe_filename(page, "page")).stem
    svg_file = resolve_under(svg_dir, f"{page_key}.svg")
    if not svg_file.exists():
        matches = list(svg_dir.glob(f"*{page_key}*.svg"))
        if matches:
            svg_file = matches[0]
        else:
            return JSONResponse({"error": "SVG page not found"}, status_code=404)
    content = sanitize_svg(svg_file.read_text(encoding="utf-8", errors="ignore"))
    return JSONResponse({"page": page, "svg": content})


@router.get("/api/projects/{job_id}/notes")
async def get_notes(job_id: str):
    """Get speaker notes."""
    pp = project_path_for(job_id)
    if not pp:
        return JSONResponse({"error": "Project not ready"}, status_code=404)
    notes: dict[str, str] = {}
    notes_dir = Path(pp) / "notes"
    if notes_dir.exists():
        for f in sorted(notes_dir.glob("*.md")):
            notes[f.stem] = f.read_text(encoding="utf-8")
    total_notes = Path(pp) / "speaker_notes.md"
    if total_notes.exists():
        notes["_total"] = total_notes.read_text(encoding="utf-8")
    return JSONResponse({"notes": notes})


@router.get("/api/projects/{job_id}/spec")
async def get_spec(job_id: str):
    """Get design spec documents."""
    pp = project_path_for(job_id)
    if not pp:
        return JSONResponse({"error": "Project not ready"}, status_code=404)
    ds_path = Path(pp) / "design_spec.md"
    sl_path = Path(pp) / "spec_lock.md"
    ec_path = artifacts_dir_for(job_id) / "eight_confirmations.md"
    return JSONResponse({
        "design_spec": ds_path.read_text(encoding="utf-8") if ds_path.exists() else "",
        "spec_lock": sl_path.read_text(encoding="utf-8") if sl_path.exists() else "",
        "eight_confirmations": ec_path.read_text(encoding="utf-8") if ec_path.exists() else "",
    })


@router.get("/api/projects/{job_id}/events")
async def get_job_events(job_id: str, after_seq: int | None = None):
    """Return historical events for a job (for chat replay)."""
    events = runtime().get_events(job_id)
    if after_seq is not None:
        events = [e for e in events if int(e.get("seq", 0) or 0) > after_seq]
    return JSONResponse({"events": events})
