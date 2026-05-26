from __future__ import annotations

import re
from pathlib import Path


class SafetyError(ValueError):
    pass


def safe_filename(filename: str | None, default: str = "file") -> str:
    raw = (filename or "").replace("\\", "/").split("/")[-1].strip()
    if not raw or raw in {".", ".."}:
        raw = default
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", raw).strip("._")
    if not cleaned:
        cleaned = default
    return cleaned[:120]


def resolve_under(root: Path, *parts: str | Path, must_exist: bool = False) -> Path:
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*(str(p) for p in parts)).resolve(strict=False)
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise SafetyError(f"Path escapes workspace: {candidate}")
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def safe_relative_path(relative_path: str | Path) -> Path:
    raw = str(relative_path).replace("\\", "/")
    if not raw or raw.startswith("/"):
        raise SafetyError(f"Invalid relative path: {relative_path}")
    path = Path(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise SafetyError(f"Invalid relative path: {relative_path}")
    return path


def sanitize_svg(svg: str) -> str:
    cleaned = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", svg, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*foreignObject\b[^>]*>.*?<\s*/\s*foreignObject\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s+(?:href|xlink:href)\s*=\s*(['\"])(?:javascript:|data:text/html|https?://)[^'\"]*\1", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"url\(\s*(['\"]?)(?:javascript:|https?://)[^)]+\1\s*\)", "none", cleaned, flags=re.IGNORECASE)
    return cleaned


def validate_svg(svg: str) -> None:
    if "<svg" not in svg.lower() or "</svg" not in svg.lower():
        raise SafetyError("SVG content must contain a complete <svg> document")
