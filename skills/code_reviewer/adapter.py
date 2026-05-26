"""Code Reviewer Skill Adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from harness.skill import BaseSkill

if TYPE_CHECKING:
    from harness.session import SkillSession


class CodeReviewerSkill(BaseSkill):
    """Stub: AI code review with security and style checks."""

    name = "code-reviewer"

    async def run(self, session: "SkillSession") -> None:
        file_path = session.state.get("file_path", "")
        await session.emit("progress", {"step": "review", "message": f"Reviewing code: {file_path}"})
        # TODO: Implement code analysis

    async def resume(self, session: "SkillSession", user_response: str) -> None:
        await session.emit("progress", {"step": "review", "message": "Resuming code review"})
