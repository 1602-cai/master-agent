"""Doc Outline Generator Skill Adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from harness.skill import BaseSkill

if TYPE_CHECKING:
    from harness.session import SkillSession


class DocOutlineSkill(BaseSkill):
    """Stub: Extract structured outlines from PDF/Word/Markdown."""

    name = "doc-outline-generator"

    async def run(self, session: "SkillSession") -> None:
        source_path = session.state.get("source_path", "")
        await session.emit("progress", {"step": "outline", "message": f"Extracting outline from {source_path}"})
        # TODO: Implement actual document parsing

    async def resume(self, session: "SkillSession", user_response: str) -> None:
        await session.emit("progress", {"step": "outline", "message": "Resuming outline extraction"})
