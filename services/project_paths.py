from __future__ import annotations

from pathlib import Path
from typing import Any


def get_project_path(job_store: Any, job_id: str) -> str:
    job_dir = job_store.job_dir(job_id)
    job = job_store.get(job_id)
    if job:
        project_path = (job.get("state") or {}).get("project_path", "")
        if project_path:
            try:
                candidate = Path(project_path).resolve(strict=False)
                job_dir_resolved = job_dir.resolve()
                if (candidate == job_dir_resolved or job_dir_resolved in candidate.parents) and candidate.exists():
                    return str(candidate)
            except Exception:
                pass
    fallback = job_dir / "project"
    return str(fallback) if fallback.exists() else ""


def get_artifacts_dir(job_store: Any, job_id: str) -> Path:
    return job_store.job_dir(job_id) / "artifacts"
