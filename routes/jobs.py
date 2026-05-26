"""Job lifecycle routes — start, status, confirm, list, cancel, delete."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from routes.deps import (
    is_terminal_status, log,
    runtime, job_runner,
    project_path_for, artifacts_dir_for,
    UPLOAD_DIR,
)

router = APIRouter()


@router.post("/api/start")
async def start_pipeline(payload: dict):
    """Start PPT pipeline — accepts demo frontend format."""
    file_id = payload.get("file_id", "")
    source_file = payload.get("source_file", "")
    user_request = payload.get("user_request", "")
    canvas_format = payload.get("canvas_format", "ppt169")
    auto_mode = payload.get("auto_mode", False)
    enable_images = payload.get("enable_images", False)

    # Resolve file_id to actual path
    if file_id and not source_file:
        upload_dir = UPLOAD_DIR / file_id
        if upload_dir.exists():
            files = list(upload_dir.iterdir())
            if files:
                source_file = str(files[0])

    # Build initial state
    files = []
    if source_file:
        files.append(source_file)

    initial_state = {
        "files": files,
        "canvas_format": canvas_format,
        "auto_mode": auto_mode,
        "enable_images": enable_images,
    }

    if not user_request:
        if source_file:
            user_request = f"请根据文件制作专业 PPT: {Path(source_file).name}"
        else:
            user_request = "请制作专业 PPT"

    job_id = runtime().jobs.create("ppt-master", user_request)["job_id"]
    await runtime().jobs.async_update(job_id, state=initial_state)

    try:
        job_runner().submit_start(job_id, "ppt-master", user_request, initial_state)
    except Exception as e:
        await runtime().jobs.async_update(job_id, status="failed", error=str(e))
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse({"job_id": job_id, "status": "started"})


@router.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Query job status."""
    job = runtime().get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    status = job.get("status", "pending")
    if status == "waiting_for_user":
        status = "confirming"

    result = None
    pp = project_path_for(job_id)
    if status == "completed" and pp:
        pptx_size = 0
        exports_dir = Path(pp) / "exports"
        if exports_dir.exists():
            for f in exports_dir.glob("*.pptx"):
                pptx_size = f.stat().st_size
                break
        svg_dir = Path(pp) / "svg_output"
        total_pages = len(list(svg_dir.glob("*.svg"))) if svg_dir.exists() else 0
        result = {
            "pptx_size": pptx_size,
            "total_pages": total_pages,
            "download_url": f"/api/download/{job_id}",
        }
    elif status == "confirming":
        ec_path = artifacts_dir_for(job_id) / "eight_confirmations.md"
        result = {}
        if ec_path.exists():
            result["eight_confirmations"] = ec_path.read_text(encoding="utf-8")

    visible_error = job.get("error") if status == "failed" else None
    skill_name = job.get("skill", "")
    skill_ui_type = "svg_slides"
    try:
        skill_meta = runtime().registry.get_metadata(skill_name)
        skill_ui_type = skill_meta.supported_ui_types[0] if skill_meta.supported_ui_types else "default"
    except (KeyError, IndexError):
        pass

    return JSONResponse({
        "job_id": job_id,
        "status": status,
        "skill_ui_type": skill_ui_type,
        "project_name": skill_name + "_" + job_id[:8],
        "current_step": job.get("current_step") or job.get("state", {}).get("current_step", ""),
        "current_step_name": job.get("current_step_name") or job.get("state", {}).get("current_step_name", ""),
        "created_at": job.get("created_at"),
        "error": visible_error,
        "result": result,
    })


@router.post("/api/confirm/{job_id}")
async def confirm_design(job_id: str, payload: dict = None):
    """User confirms/modifies design."""
    payload = payload or {}
    action = payload.get("action", "confirm")
    feedback = payload.get("feedback", "")

    if action == "split":
        response = "split"
    elif action == "confirm" and not feedback:
        response = "确认"
    else:
        response = feedback or "确认"

    try:
        job_runner().submit_resume(job_id, response)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return JSONResponse({"status": "confirmed", "action": action, "feedback": response})


@router.get("/api/jobs")
async def get_jobs():
    """List all jobs."""
    jobs_raw = runtime().list_jobs()
    job_list = []
    for j in jobs_raw:
        status = j.get("status", "pending")
        if status == "waiting_for_user":
            status = "confirming"
        user_input = j.get("user_input", "")
        project_name = user_input[:40] if user_input else j.get("job_id", "")[:8]
        state = j.get("state", {})
        files = state.get("files", [])
        source_file = Path(files[0]).name if files else ""
        job_list.append({
            "job_id": j.get("job_id", ""),
            "status": status,
            "project_name": project_name,
            "source_file": source_file,
            "created_at": j.get("created_at"),
            "pinned_at": None,
            "error": j.get("error"),
        })
    job_list.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return JSONResponse({"jobs": job_list})


@router.patch("/api/jobs/{job_id}/rename")
async def rename_job(job_id: str, payload: dict):
    """Rename job (stub)."""
    return JSONResponse({"status": "ok"})


@router.patch("/api/jobs/{job_id}/pin")
async def pin_job(job_id: str):
    """Pin job (stub)."""
    return JSONResponse({"status": "ok"})


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    cancelled = job_runner().cancel(job_id)
    try:
        job = runtime().get_job(job_id)
        if job and not is_terminal_status(job.get("status")):
            await runtime().jobs.async_update(job_id, status="cancelled", error="用户手动中断")
    except Exception:
        pass
    try:
        await runtime().emit_job_event(job_id, "job_cancelled", message="任务已被中断")
    except Exception:
        pass
    return JSONResponse({"status": "ok", "cancelled": cancelled})


@router.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Cancel running task (if any) and delete job data."""
    job_runner().cancel(job_id)
    job_runner().discard(job_id)
    job_dir = runtime().jobs.job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
        log.info("Deleted job %s", job_id)
    return JSONResponse({"status": "ok"})
