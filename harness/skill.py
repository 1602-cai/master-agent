"""Base skill interface and skill registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from harness.session import SkillSession


class SkillMetadata(BaseModel):
    """Declarative metadata for a skill — used by platform for routing & UI."""

    name: str
    description: str = ""
    version: str = "0.1.0"
    supported_ui_types: list[str] = Field(
        default_factory=lambda: ["default"],
        description="UI artifact types: svg_slides, code_editor, interactive_table, markdown, etc.",
    )


class BaseSkill(ABC):
    """Every skill must subclass this."""

    name: str = ""
    metadata: SkillMetadata = SkillMetadata(name="unknown")

    @abstractmethod
    async def run(self, session: "SkillSession") -> None:
        """Execute the skill from the beginning."""
        ...

    @abstractmethod
    async def resume(self, session: "SkillSession", user_response: str) -> None:
        """Resume after a confirmation pause."""
        ...

    async def cancel(self, session: "SkillSession") -> None:
        """Optional: gracefully cancel a running skill."""
        pass


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not registered. Available: {list(self._skills)}")
        return self._skills[name]

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_metadata(self, name: str) -> SkillMetadata:
        return self.get(name).metadata
