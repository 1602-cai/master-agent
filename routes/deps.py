"""Shared dependencies — singletons, path constants, helper functions.

Every route module imports from here instead of reaching into server globals.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

from harness.jobs import is_terminal_status
from harness.safety import SafetyError, resolve_under, safe_filename, sanitize_svg
from services.job_runner import JobRunner
from services.project_paths import get_artifacts_dir, get_project_path
from services.runtime_factory import build_runtime

load_dotenv()

log = logging.getLogger("harness.server")

# ── Paths ──

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CUSTOM_TEMPLATES_DIR = DATA_DIR / "custom_templates"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Template dirs come from ppt-master config
from skills.ppt_master.config import TEMPLATES_DIR, LAYOUTS_DIR, BRANDS_DIR, DECKS_DIR  # noqa: E402

# ── Singletons ──

_runtime = None
_job_runner: JobRunner | None = None


def runtime():
    global _runtime
    if _runtime is None:
        _runtime = build_runtime(ROOT_DIR, DATA_DIR)
        from routes.ws import ws_event_broadcast
        _runtime.set_ws_broadcast(ws_event_broadcast)
    return _runtime


def job_runner() -> JobRunner:
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner(runtime)
    return _job_runner


# ── Convenience helpers ──

def project_path_for(job_id: str) -> str:
    return get_project_path(runtime().jobs, job_id)


def artifacts_dir_for(job_id: str) -> Path:
    return get_artifacts_dir(runtime().jobs, job_id)


def resolve_template_id(template_id: str) -> str:
    if not template_id:
        return ""
    roots = {
        "layouts": LAYOUTS_DIR,
        "brands": BRANDS_DIR,
        "decks": DECKS_DIR,
        "custom": CUSTOM_TEMPLATES_DIR,
    }
    for kind, root in roots.items():
        prefix = f"{kind}_"
        if not template_id.startswith(prefix):
            continue
        raw_name = template_id[len(prefix):]
        safe_name = safe_filename(raw_name, "template")
        if safe_name != raw_name:
            raise SafetyError("Invalid template id")
        path = resolve_under(root, safe_name)
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(path)
        return str(path)
    raise SafetyError("Invalid template id")
