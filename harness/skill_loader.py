from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from harness.skill import BaseSkill, SkillRegistry


def load_skills_from_dir(skills_dir: Path) -> SkillRegistry:
    registry = SkillRegistry()
    if not skills_dir.exists():
        return registry
    for manifest_path in sorted(skills_dir.glob("*/skill.yaml")):
        skill = load_skill_from_manifest(manifest_path)
        registry.register(skill)
    return registry


def load_skill_from_manifest(manifest_path: Path) -> BaseSkill:
    manifest = _parse_simple_yaml(manifest_path.read_text(encoding="utf-8"))
    entrypoint = str(manifest.get("entrypoint", "")).strip()
    if not entrypoint or ":" not in entrypoint:
        raise ValueError(f"Invalid skill entrypoint in {manifest_path}")
    module_name, class_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    skill = cls()
    if not isinstance(skill, BaseSkill):
        raise TypeError(f"Skill {entrypoint} must inherit BaseSkill")
    return skill


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and current_key:
            result.setdefault(current_key, []).append(stripped[1:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = value
                current_key = None
            else:
                result[key] = []
                current_key = key
    return result
