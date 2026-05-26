"""SkillSession — the only interface a skill uses to interact with the platform."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.artifacts import ArtifactManager
from harness.confirmations import ConfirmationRequired
from harness.events import Event, EventWriter

if TYPE_CHECKING:
    from harness.jobs import JobStore

log = logging.getLogger(__name__)

# Events that trigger automatic state.json persistence
_STATE_SYNC_EVENTS = frozenset({
    "step_start", "step_done", "artifact_created",
    "job_completed", "job_failed", "job_waiting",
})


class SkillSession:
    """Provided to every skill.run() / skill.resume() call.

    Skills must only interact with the platform through this object.
    """

    def __init__(
        self,
        job_id: str,
        skill_name: str,
        workspace: Path,
        user_input: str,
        state: dict[str, Any],
        event_writer: EventWriter,
        artifact_manager: ArtifactManager,
        job_store: "JobStore | None" = None,
    ):
        self.job_id = job_id
        self.skill_name = skill_name
        self.workspace = workspace
        self.user_input = user_input
        self.state = state
        self._events = event_writer
        self._artifacts = artifact_manager
        self._job_store = job_store

    # ── Events ──

    async def emit(self, event_type: str, message: str = "", **payload: Any) -> None:
        ev = Event(event_type, message=message, **payload)
        self._events.write(ev)
        # Auto-persist state on key lifecycle events
        if self._job_store and event_type in _STATE_SYNC_EVENTS:
            await self._sync_state(event_type, payload)

    # ── Artifacts ──

    def save_artifact(self, relative_path: str, content: str) -> Path:
        return self._artifacts.save(relative_path, content)

    def artifact_path(self, relative_path: str) -> Path:
        return self._artifacts.path(relative_path)

    def artifact_exists(self, relative_path: str) -> bool:
        return self._artifacts.exists(relative_path)

    def read_artifact(self, relative_path: str) -> str:
        return self._artifacts.read(relative_path)

    def list_artifacts(self) -> list[dict]:
        return self._artifacts.list_all()

    @property
    def artifacts_root(self) -> Path:
        return self._artifacts.root

    # ── Confirmation ──

    async def require_confirmation(self, title: str, content: str) -> None:
        """Pause execution and wait for user confirmation.

        Raises ConfirmationRequired which the runtime catches to pause the job.
        """
        await self.emit(
            "confirmation_required",
            message=title,
            title=title,
            content_preview=content[:500],
        )
        raise ConfirmationRequired(title=title, content=content)

    # ── State Sync (event-driven persistence) ──

    async def _sync_state(self, event_type: str, payload: dict[str, Any]) -> None:
        """Persist current progress to state.json — called automatically on key events.

        This ensures /api/status always reflects true progress, even if the
        pipeline crashes mid-step.
        """
        try:
            updates: dict[str, Any] = {"state": self.state}

            if event_type == "step_start":
                step_key = payload.get("step", "")
                updates["current_step"] = step_key

            elif event_type == "step_done":
                # Persist latest artifacts snapshot
                updates["artifacts"] = self.list_artifacts()

            elif event_type == "artifact_created":
                updates["artifacts"] = self.list_artifacts()

            elif event_type in ("job_completed", "job_failed", "job_waiting"):
                updates["artifacts"] = self.list_artifacts()

            await self._job_store.async_update(self.job_id, **updates)
        except Exception as e:
            log.warning("State sync failed for job %s: %s", self.job_id, e)
