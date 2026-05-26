"""Human-in-the-loop confirmation management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


class ConfirmationRequired(Exception):
    """Raised by SkillSession.require_confirmation to pause execution."""

    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content
        super().__init__(f"Confirmation required: {title}")


@dataclass
class PendingConfirmation:
    """Tracks a pending confirmation for a job."""

    title: str
    content: str
    response: str | None = None
    resolved: asyncio.Event = field(default_factory=asyncio.Event)

    def resolve(self, user_response: str) -> None:
        self.response = user_response
        self.resolved.set()
