"""Job store — create, persist and query jobs."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATUSES = frozenset({
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
})


def is_terminal_status(status: str | None) -> bool:
    return bool(status) and status in TERMINAL_JOB_STATUSES


class JobStore:
    """File-backed job store. Each job is a directory under *data_dir*/jobs/."""

    def __init__(self, data_dir: Path):
        self._root = data_dir / "jobs"
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, job_id: str) -> asyncio.Lock:
        """Get or create a per-job asyncio lock for atomic updates."""
        if job_id not in self._locks:
            self._locks[job_id] = asyncio.Lock()
        return self._locks[job_id]

    async def async_update(self, job_id: str, **fields: Any) -> dict[str, Any]:
        """Atomic async update — safe under concurrent page generation."""
        async with self._get_lock(job_id):
            return self.update(job_id, **fields)

    async def async_get(self, job_id: str) -> dict[str, Any] | None:
        """Async read with lock protection."""
        async with self._get_lock(job_id):
            return self.get(job_id)

    def create(self, skill_name: str, user_input: str) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        job_dir = self._root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        job = {
            "job_id": job_id,
            "skill": skill_name,
            "status": JobStatus.QUEUED.value,
            "current_step": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "user_input": user_input,
            "state": {},
            "artifacts": [],
            "error": None,
        }
        with self._file_lock(job_id):
            self._save(job_id, job)
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        path = self._root / job_id / "state.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, job_id: str, **fields: Any) -> dict[str, Any]:
        with self._file_lock(job_id):
            job = self.get(job_id)
            if job is None:
                raise KeyError(f"Job {job_id} not found")
            next_status = fields.get("status")
            if next_status and next_status not in {s.value for s in JobStatus}:
                raise ValueError(f"Invalid job status: {next_status}")
            if next_status and next_status not in (JobStatus.FAILED.value, JobStatus.CANCELLED.value):
                fields.setdefault("error", None)
            job.update(fields)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(job_id, job)
            # Clean up asyncio lock when job reaches terminal status
            if next_status and is_terminal_status(next_status):
                self._locks.pop(job_id, None)
            return job

    def job_dir(self, job_id: str) -> Path:
        return self._root / job_id

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = []
        for d in sorted(self._root.iterdir()):
            if d.is_dir() and (d / "state.json").exists():
                jobs.append(json.loads((d / "state.json").read_text("utf-8")))
        return jobs

    @contextlib.contextmanager
    def _file_lock(self, job_id: str):
        lock_path = self._root / job_id / ".state.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _save(self, job_id: str, job: dict) -> None:
        path = self._root / job_id / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        data = json.dumps(job, ensure_ascii=False, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
