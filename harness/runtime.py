"""HarnessRuntime — the platform entry point."""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from harness.artifacts import ArtifactManager
from harness.confirmations import ConfirmationRequired
from harness.events import Event, EventWriter
from harness.jobs import JobStatus, JobStore
from harness.session import SkillSession
from harness.skill import SkillRegistry

log = logging.getLogger(__name__)


class HarnessRuntime:
    """Manages job lifecycle and skill execution."""

    def __init__(self, skill_registry: SkillRegistry, job_store: JobStore):
        self.registry = skill_registry
        self.jobs = job_store
        self._ws_broadcast: Callable[[str, dict], Awaitable[None]] | None = None

    def set_ws_broadcast(self, fn: Callable[[str, dict], Awaitable[None]]):
        """Set the WebSocket broadcast function: async fn(job_id, event_dict)."""
        self._ws_broadcast = fn

    # ── Public API ──

    async def start_job(
        self,
        skill_name: str,
        user_input: str,
        files: list[str] | None = None,
        initial_state: dict | None = None,
    ) -> str:
        """Create a new job and run the skill."""
        self.registry.get(skill_name)
        job = self.jobs.create(skill_name, user_input)
        job_id = job["job_id"]
        log.info("Job %s created for skill '%s'", job_id, skill_name)

        state = job.get("state", {})
        if initial_state:
            state.update(initial_state)

        await self.jobs.async_update(job_id, state=state)
        await self._run_job_lifecycle(
            job_id,
            skill_name,
            user_input,
            state,
            lambda skill, session: skill.run(session),
            "job_started",
            f"Skill: {skill_name}",
        )
        return job_id

    async def start_job_with_id(
        self,
        job_id: str,
        skill_name: str,
        user_input: str,
        initial_state: dict | None = None,
    ) -> None:
        """Run a skill on a pre-created job (used by server background tasks)."""
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        state = (job.get("state") or {}).copy()
        if initial_state:
            state.update(initial_state)
        await self.jobs.async_update(job_id, state=state)
        await self._run_job_lifecycle(
            job_id,
            skill_name,
            user_input,
            state,
            lambda skill, session: skill.run(session),
            "job_started",
            f"Skill: {skill_name}",
        )

    async def resume_job(self, job_id: str, user_response: str) -> None:
        """Resume a job that was waiting for user confirmation."""
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        if job["status"] != JobStatus.WAITING.value:
            raise ValueError(f"Job {job_id} is not waiting (status={job['status']})")

        state = (job.get("state") or {}).copy()
        await self._run_job_lifecycle(
            job_id,
            job["skill"],
            job["user_input"],
            state,
            lambda skill, session: skill.resume(session, user_response),
            "job_resumed",
            user_response[:200],
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.jobs.get(job_id)

    def get_events(self, job_id: str) -> list[dict]:
        job_dir = self.jobs.job_dir(job_id)
        ew = EventWriter(job_dir)
        return ew.read_all()

    def list_jobs(self) -> list[dict]:
        return self.jobs.list_jobs()

    async def emit_job_event(self, job_id: str, event_type: str, message: str = "", **payload: Any) -> dict:
        job_dir = self.jobs.job_dir(job_id)
        event = Event(event_type, message=message, **payload)
        event_dict = EventWriter(job_dir).write(event)
        if self._ws_broadcast:
            await self._ws_broadcast(job_id, event_dict)
        return event_dict

    # ── Internal ──

    async def _run_job_lifecycle(
        self,
        job_id: str,
        skill_name: str,
        user_input: str,
        state: dict,
        runner: Callable[[Any, SkillSession], Awaitable[None]],
        start_event: str,
        start_message: str,
    ) -> None:
        skill = self.registry.get(skill_name)
        session = self._build_session(job_id, skill_name, user_input, state)

        await self.jobs.async_update(job_id, status=JobStatus.RUNNING.value, state=session.state)
        await session.emit(start_event, message=start_message)

        try:
            await runner(skill, session)
            await self.jobs.async_update(
                job_id,
                status=JobStatus.COMPLETED.value,
                state=session.state,
                artifacts=session.list_artifacts(),
            )
            await session.emit("job_completed")
            log.info("Job %s completed", job_id)
        except ConfirmationRequired as cr:
            await self.jobs.async_update(
                job_id,
                status=JobStatus.WAITING.value,
                current_step="confirmation",
                state=session.state,
                artifacts=session.list_artifacts(),
            )
            await session.emit("job_waiting", message=cr.title)
            log.info("Job %s paused: %s", job_id, cr.title)
        except Exception as exc:
            await self.jobs.async_update(
                job_id,
                status=JobStatus.FAILED.value,
                error=str(exc),
                state=session.state,
                artifacts=session.list_artifacts(),
            )
            await session.emit("job_failed", message=str(exc))
            log.error("Job %s failed: %s", job_id, exc)
            raise

    def _build_session(
        self,
        job_id: str,
        skill_name: str,
        user_input: str,
        state: dict,
    ) -> SkillSession:
        job_dir = self.jobs.job_dir(job_id)

        # Create WS broadcast callback bound to this job_id
        on_event = None
        if self._ws_broadcast:
            ws_fn = self._ws_broadcast
            async def on_event(event_dict: dict):
                await ws_fn(job_id, event_dict)

        return SkillSession(
            job_id=job_id,
            skill_name=skill_name,
            workspace=job_dir,
            user_input=user_input,
            state=state,
            event_writer=EventWriter(job_dir, on_event=on_event),
            artifact_manager=ArtifactManager(job_dir),
            job_store=self.jobs,
        )
