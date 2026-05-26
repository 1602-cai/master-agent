"""Data Visualizer Skill Adapter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from harness.skill import BaseSkill

if TYPE_CHECKING:
    from harness.session import SkillSession


class DataVisualizerSkill(BaseSkill):
    """Stub: Generate interactive charts from data."""

    name = "data-visualizer"

    async def run(self, session: "SkillSession") -> None:
        data_source = session.state.get("data_source", "")
        await session.emit("progress", {"step": "visualize", "message": f"Generating charts from: {data_source}"})
        # TODO: Implement chart generation

    async def resume(self, session: "SkillSession", user_response: str) -> None:
        await session.emit("progress", {"step": "visualize", "message": "Resuming visualization"})
