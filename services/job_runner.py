from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from harness.jobs import is_terminal_status
from harness.runtime import HarnessRuntime

log = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, runtime_provider: Callable[[], HarnessRuntime]):
        self._runtime_provider = runtime_provider
        self._tasks: dict[str, asyncio.Task] = {}

    def active_job_ids(self) -> list[str]:
        return [job_id for job_id, task in self._tasks.items() if not task.done()]

    def get_task(self, job_id: str) -> asyncio.Task | None:
        return self._tasks.get(job_id)

    def submit_start(self, job_id: str, skill_name: str, user_input: str, initial_state: dict[str, Any]) -> None:
        async def _run_job() -> None:
            try:
                await self._runtime_provider().start_job_with_id(job_id, skill_name, user_input, initial_state)
            except Exception as e:
                log.error("Pipeline %s crashed: %s", job_id, e)
                await self._mark_failed_if_non_terminal(job_id, str(e))

        self._submit(job_id, _run_job)

    def submit_resume(self, job_id: str, response: str) -> None:
        async def _resume_job() -> None:
            try:
                await self._runtime_provider().resume_job(job_id, response)
            except Exception as e:
                log.error("Resume job %s failed: %s", job_id, e)
                await self._mark_failed_if_non_terminal(job_id, str(e))

        self._submit(job_id, _resume_job)

    def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            log.info("Cancelled running task for job %s", job_id)
            return True
        return False

    def discard(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)

    def _submit(self, job_id: str, coro_factory: Callable[[], Any]) -> None:
        existing = self._tasks.get(job_id)
        if existing and not existing.done():
            raise RuntimeError(f"Job {job_id} already has a running task")
        task = asyncio.create_task(coro_factory())
        self._tasks[job_id] = task
        task.add_done_callback(lambda done_task: self._on_done(job_id, done_task))

    def _on_done(self, job_id: str, task: asyncio.Task) -> None:
        self._tasks.pop(job_id, None)
        if task.cancelled():
            log.warning("Task for job %s was cancelled", job_id)
            self._safe_create_task(self._update_job(job_id, status="cancelled", error="任务被取消"))
            return
        if task.exception():
            exc = task.exception()
            log.error("Task for job %s raised unhandled exception: %s", job_id, exc)
            self._safe_create_task(self._mark_failed_if_non_terminal(job_id, str(exc)))
            return
        self._safe_create_task(self._ensure_terminal_or_waiting(job_id))

    async def _ensure_terminal_or_waiting(self, job_id: str) -> None:
        try:
            runtime = self._runtime_provider()
            job = runtime.get_job(job_id)
            if job and not is_terminal_status(job.get("status")) and job.get("status") != "waiting_for_user":
                log.warning("Task for job %s finished but status is still '%s' — marking completed", job_id, job.get("status"))
                await runtime.jobs.async_update(job_id, status="completed", state=job.get("state", {}))
        except Exception:
            pass

    async def _mark_failed_if_non_terminal(self, job_id: str, error: str) -> None:
        try:
            runtime = self._runtime_provider()
            job = runtime.get_job(job_id)
            if job and not is_terminal_status(job.get("status")):
                await runtime.jobs.async_update(job_id, status="failed", error=error)
        except Exception:
            pass

    async def _update_job(self, job_id: str, **fields: Any) -> None:
        try:
            await self._runtime_provider().jobs.async_update(job_id, **fields)
        except Exception:
            pass

    def _safe_create_task(self, coro) -> None:
        try:
            asyncio.create_task(coro)
        except RuntimeError:
            pass
