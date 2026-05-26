"""ArXiv Researcher Skill Adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from harness.skill import BaseSkill

if TYPE_CHECKING:
    from harness.session import SkillSession


class ArxivResearcherSkill(BaseSkill):
    """Stub: Search and summarize academic papers from ArXiv."""

    name = "arxiv-researcher"

    async def run(self, session: "SkillSession") -> None:
        query = session.state.get("query", "")
        await session.emit("progress", {"step": "research", "message": f"Searching ArXiv for: {query}"})
        # TODO: Implement ArXiv API integration

    async def resume(self, session: "SkillSession", user_response: str) -> None:
        await session.emit("progress", {"step": "research", "message": "Resuming research"})
