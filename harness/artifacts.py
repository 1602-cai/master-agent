"""Artifact manager — saves and lists job output files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.safety import resolve_under, safe_relative_path


class ArtifactManager:
    """Manage artifacts under a job workspace."""

    def __init__(self, job_dir: Path):
        self._root = job_dir / "artifacts"
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def save(self, relative_path: str, content: str) -> Path:
        dest = resolve_under(self._root, safe_relative_path(relative_path))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return dest

    def path(self, relative_path: str) -> Path:
        return resolve_under(self._root, safe_relative_path(relative_path))

    def exists(self, relative_path: str) -> bool:
        return self.path(relative_path).exists()

    def read(self, relative_path: str) -> str:
        return self.path(relative_path).read_text(encoding="utf-8")

    def list_all(self) -> list[dict[str, Any]]:
        items = []
        for p in sorted(self._root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(self._root)
                items.append({
                    "path": str(rel),
                    "size": p.stat().st_size,
                    "type": _guess_type(p),
                })
        return items


def _guess_type(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".md": "markdown",
        ".svg": "svg",
        ".json": "json",
        ".pptx": "pptx",
        ".txt": "text",
        ".png": "image",
        ".jpg": "image",
    }.get(ext, "file")
