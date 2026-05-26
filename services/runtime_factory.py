from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from harness.jobs import JobStore
from harness.runtime import HarnessRuntime
from harness.skill_loader import load_skills_from_dir


def build_runtime(
    root_dir: Path,
    data_dir: Path,
    ws_broadcast: Callable[[str, dict], Awaitable[None]] | None = None,
) -> HarnessRuntime:
    registry = load_skills_from_dir(root_dir / "skills")
    job_store = JobStore(data_dir)
    runtime = HarnessRuntime(registry, job_store)
    if ws_broadcast:
        runtime.set_ws_broadcast(ws_broadcast)
    return runtime
