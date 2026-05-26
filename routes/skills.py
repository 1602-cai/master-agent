"""ClawSkill Marketplace & Skill Management API.

Provides endpoints for:
- Listing currently installed/active skills
- Browsing available marketplace skills
- Installing/uninstalling skills dynamically
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harness.skill_loader import load_skills_from_dir, load_skill_from_manifest
from routes.deps import ROOT_DIR, runtime

router = APIRouter(tags=["skills"])

SKILLS_DIR = ROOT_DIR / "skills"
MARKETPLACE_FILE = ROOT_DIR / "data" / "marketplace.json"
INSTALLED_STATE_FILE = ROOT_DIR / "data" / "installed_skills.json"


class SkillInfo(BaseModel):
    name: str
    description: str
    version: str
    icon: str
    requires: list[str]
    installed: bool
    active: bool


class MarketplaceSkill(BaseModel):
    id: str
    name: str
    description: str
    version: str
    author: str
    icon: str
    category: str
    installed: bool


def _get_installed_skills() -> set[str]:
    """Read installed skills state from file."""
    if not INSTALLED_STATE_FILE.exists():
        return set()
    try:
        data = json.loads(INSTALLED_STATE_FILE.read_text())
        return set(data.get("installed", []))
    except Exception:
        return set()


def _save_installed_skills(installed: set[str]) -> None:
    """Save installed skills state to file."""
    INSTALLED_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_STATE_FILE.write_text(json.dumps({"installed": sorted(installed)}, indent=2))


def _get_marketplace_data() -> list[dict]:
    """Get marketplace skill catalog."""
    if MARKETPLACE_FILE.exists():
        try:
            return json.loads(MARKETPLACE_FILE.read_text())
        except Exception:
            pass
    # Fallback: generate from available skill directories not currently installed
    return _generate_default_marketplace()


def _generate_default_marketplace() -> list[dict]:
    """Generate default marketplace from skills directory."""
    installed = _get_installed_skills()
    marketplace = []

    # Additional premium/community skills not in core 5
    extra_skills = [
        {
            "id": "figma-style-extractor",
            "name": "Figma Style Extractor",
            "description": "Extract color palettes and typography from Figma designs",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "figma",
            "category": "design",
        },
        {
            "id": "slack-postman",
            "name": "Slack Postman",
            "description": "Auto-deliver PPT previews and notes to Slack channels",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "slack",
            "category": "integration",
        },
        {
            "id": "stable-diffusion-illustrator",
            "name": "SD Illustrator",
            "description": "AI-generated illustrations matching your slide themes",
            "version": "1.0.0",
            "author": "ClawSkill Community",
            "icon": "image",
            "category": "creative",
        },
        {
            "id": "github-deliverer",
            "name": "GitHub Deliverer",
            "description": "Commit PPT assets and specs to Git repositories",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "github",
            "category": "integration",
        },
        {
            "id": "notion-sync",
            "name": "Notion Sync",
            "description": "Bi-directional sync with Notion pages and databases",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "file-text",
            "category": "integration",
        },
        {
            "id": "excel-analyzer",
            "name": "Excel Analyzer",
            "description": "智能分析 Excel 表格数据，自动生成图表和洞察",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "table",
            "category": "data",
        },
        {
            "id": "pdf-extractor",
            "name": "PDF Extractor",
            "description": "从 PDF 中提取文本、表格和图片，支持批量处理",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "file-text",
            "category": "document",
        },
        {
            "id": "email-writer",
            "name": "Email Writer",
            "description": "根据要点自动生成专业商务邮件，支持多语言",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "mail",
            "category": "productivity",
        },
        {
            "id": "translator-pro",
            "name": "Translator Pro",
            "description": "专业级文档翻译，保持格式和术语一致性",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "languages",
            "category": "productivity",
        },
        {
            "id": "video-transcriber",
            "name": "Video Transcriber",
            "description": "音视频转文字，自动生成字幕和摘要",
            "version": "1.0.0",
            "author": "ClawSkill Community",
            "icon": "video",
            "category": "media",
        },
        {
            "id": "image-recognizer",
            "name": "Image Recognizer",
            "description": "识别图片内容，提取文字、物体和场景信息",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "scan-eye",
            "category": "vision",
        },
        {
            "id": "sql-assistant",
            "name": "SQL Assistant",
            "description": "自然语言转 SQL，自动生成和优化查询语句",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "database",
            "category": "developer",
        },
        {
            "id": "api-tester",
            "name": "API Tester",
            "description": "自动生成 API 测试用例，支持 REST 和 GraphQL",
            "version": "1.0.0",
            "author": "ClawSkill Community",
            "icon": "webhook",
            "category": "developer",
        },
        {
            "id": "meeting-minutes",
            "name": "Meeting Minutes",
            "description": "会议录音转结构化纪要，自动提取行动项",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "users",
            "category": "productivity",
        },
        {
            "id": "resume-parser",
            "name": "Resume Parser",
            "description": "批量解析简历，提取结构化信息并生成对比报告",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "user-circle",
            "category": "hr",
        },
        {
            "id": "contract-reviewer",
            "name": "Contract Reviewer",
            "description": "法律合同审查，标记风险条款并提供修改建议",
            "version": "1.0.0",
            "author": "ClawSkill Enterprise",
            "icon": "shield-check",
            "category": "legal",
        },
        {
            "id": "social-writer",
            "name": "Social Writer",
            "description": "生成社交媒体文案，适配微博/小红书/LinkedIn",
            "version": "1.0.0",
            "author": "ClawSkill Community",
            "icon": "share-2",
            "category": "marketing",
        },
        {
            "id": "prompt-optimizer",
            "name": "Prompt Optimizer",
            "description": "优化你的 Prompt，让 AI 输出更精准",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "sparkles",
            "category": "ai-tools",
        },
        {
            "id": "chrome-connector",
            "name": "Chrome Connector",
            "description": "浏览器自动化，抓取网页数据并填充表单",
            "version": "1.0.0",
            "author": "ClawSkill Community",
            "icon": "globe",
            "category": "automation",
        },
        {
            "id": "calendar-assistant",
            "name": "Calendar Assistant",
            "description": "智能日程规划，自动安排会议并发送邀请",
            "version": "1.0.0",
            "author": "ClawSkill Official",
            "icon": "calendar",
            "category": "productivity",
        },
    ]

    for skill in extra_skills:
        skill["installed"] = skill["id"] in installed
        marketplace.append(skill)

    return marketplace


@router.get("/api/skills", response_model=list[SkillInfo])
async def list_active_skills() -> list[dict]:
    """List all currently active/loaded skills."""
    registry = runtime().registry
    skills = []

    for name, skill in registry._skills.items():
        # Get manifest info if available
        manifest_path = SKILLS_DIR / name.replace("-", "_") / "skill.yaml"
        icon = "puzzle"
        requires = []

        if manifest_path.exists():
            from harness.skill_loader import _parse_simple_yaml
            try:
                manifest = _parse_simple_yaml(manifest_path.read_text())
                icon = manifest.get("icon", "puzzle")
                requires = manifest.get("requires", [])
            except Exception:
                pass

        skills.append({
            "name": name,
            "description": getattr(skill, "description", "No description"),
            "version": getattr(skill, "version", "0.1.0"),
            "icon": icon,
            "requires": requires,
            "installed": True,
            "active": True,
        })

    return skills


@router.get("/api/skills/marketplace", response_model=list[MarketplaceSkill])
async def list_marketplace_skills() -> list[dict]:
    """List available skills in ClawSkill Marketplace."""
    installed = _get_installed_skills()
    marketplace = _get_marketplace_data()

    for skill in marketplace:
        skill["installed"] = skill["id"] in installed

    return marketplace


@router.post("/api/skills/install/{skill_id}")
async def install_skill(skill_id: str) -> dict:
    """Install a skill from the marketplace."""
    installed = _get_installed_skills()

    if skill_id in installed:
        raise HTTPException(status_code=400, detail=f"Skill {skill_id} already installed")

    # In a real implementation, this would:
    # 1. Download skill package from registry
    # 2. Extract to skills/{skill_id}/
    # 3. Reload runtime registry

    # For MVP: simulate by creating stub if it doesn't exist
    skill_dir = SKILLS_DIR / skill_id.replace("-", "_")
    if not skill_dir.exists():
        skill_dir.mkdir(parents=True)
        # Create minimal manifest
        manifest = skill_dir / "skill.yaml"
        manifest.write_text(f"""name: {skill_id}
description: Installed from ClawSkill Marketplace
version: 1.0.0
entrypoint: skills.{skill_id.replace('-', '_')}.adapter:StubSkill
requires:
  - llm
icon: puzzle
""")
        # Create stub adapter
        adapter = skill_dir / "adapter.py"
        adapter.write_text(f'''"""Stub adapter for {skill_id}."""
from harness.skill import BaseSkill, SkillSession

class StubSkill(BaseSkill):
    async def run(self, session: SkillSession, inputs: dict) -> dict:
        return {{"status": "installed", "skill": "{skill_id}"}}
''')
        init_file = skill_dir / "__init__.py"
        init_file.write_text(f'"""{skill_id} skill module."""\n')

    installed.add(skill_id)
    _save_installed_skills(installed)

    # Reload runtime skills
    new_registry = load_skills_from_dir(SKILLS_DIR)
    runtime().skills._skills.update(new_registry._skills)

    return {"success": True, "skill_id": skill_id, "message": f"Skill {skill_id} installed successfully"}


@router.post("/api/skills/uninstall/{skill_id}")
async def uninstall_skill(skill_id: str) -> dict:
    """Uninstall a skill."""
    installed = _get_installed_skills()

    if skill_id not in installed:
        raise HTTPException(status_code=400, detail=f"Skill {skill_id} not installed")

    # Remove from runtime (but keep files for now)
    if skill_id in runtime().registry._skills:
        del runtime().registry._skills[skill_id]

    installed.discard(skill_id)
    _save_installed_skills(installed)

    return {"success": True, "skill_id": skill_id, "message": f"Skill {skill_id} uninstalled"}


@router.post("/api/skills/reload")
async def reload_skills() -> dict:
    """Reload all skills from disk."""
    new_registry = load_skills_from_dir(SKILLS_DIR)
    runtime().registry._skills.clear()
    runtime().registry._skills.update(new_registry._skills)

    return {
        "success": True,
        "loaded": len(runtime().registry._skills),
        "skills": list(runtime().registry._skills.keys()),
    }
