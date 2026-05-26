"""PPT Master skill configuration — paths, script runner, LLM provider."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()

log = logging.getLogger(__name__)

# ── Paths ──

HARNESS_ROOT = Path(__file__).resolve().parent.parent.parent
PPT_MASTER_ROOT = HARNESS_ROOT.parent / "ppt-master-main 2"
SKILL_DIR = PPT_MASTER_ROOT / "skills" / "ppt-master"
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEMPLATES_DIR = SKILL_DIR / "templates"
LAYOUTS_DIR = TEMPLATES_DIR / "layouts"
BRANDS_DIR = TEMPLATES_DIR / "brands"
DECKS_DIR = TEMPLATES_DIR / "decks"
CHARTS_DIR = TEMPLATES_DIR / "charts"
ICONS_DIR = TEMPLATES_DIR / "icons"
REFERENCES_DIR = SKILL_DIR / "references"

DATA_DIR = HARNESS_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Provider ──

_api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))
_base_url = os.getenv("DEEPSEEK_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"))
_model_name = os.getenv("DEEPSEEK_MODEL", os.getenv("OPENAI_MODEL", "deepseek-chat"))

_client = AsyncOpenAI(
    base_url=_base_url,
    api_key=_api_key,
    timeout=180.0,       # 免费模型响应慢，给足超时时间
    max_retries=3,       # SDK 层自动重试
)
set_tracing_disabled(disabled=True)

MODEL = OpenAIChatCompletionsModel(model=_model_name, openai_client=_client)


# ── Script Runner ──

def run_script(
    script_name: str,
    args: list[str],
    cwd: str | None = None,
    timeout: int = 180,
    retries: int = 2,
) -> tuple[int, str, str]:
    """Run a ppt-master script with retry. Returns (returncode, stdout, stderr)."""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args

    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=cwd or str(PPT_MASTER_ROOT), timeout=timeout,
            )
            if result.returncode == 0 or attempt == retries:
                return result.returncode, result.stdout, result.stderr
            log.warning("Script %s returned %d, retry %d/%d", script_name, result.returncode, attempt, retries)
        except subprocess.TimeoutExpired:
            log.error("Script %s timed out (%ds), attempt %d", script_name, timeout, attempt)
            if attempt == retries:
                return 1, "", f"Script timed out ({timeout}s)"
        except Exception as e:
            log.error("Script %s error: %s", script_name, e)
            if attempt == retries:
                return 1, "", str(e)
    return 1, "", "Unknown error"


# ── Reference Loader ──

def load_reference(name: str, max_chars: int = 0) -> str:
    """Load a reference markdown file from ppt-master references/."""
    path = REFERENCES_DIR / name
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    if max_chars and len(content) > max_chars:
        content = content[:max_chars] + "\n\n... (truncated)"
    return content


# ── Live Preview Process ──

preview_process: subprocess.Popen | None = None
