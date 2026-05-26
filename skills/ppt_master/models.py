"""Pydantic models for PPT Master skill — type-safe data contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageSpec(BaseModel):
    """Specification for a single PPT page."""

    num: int = Field(..., description="Page number (1-indexed)")
    title: str = Field(default="", description="Page title")
    brief: str = Field(default="", description="Page content brief")
    generation_mode: str = Field(default="", description="'mirror' or 'standard' (empty = use global)")
    template_basename: str = Field(default="", description="Template SVG basename for mirror mode")


class LayoutSpec(BaseModel):
    """Layout assignment for a page."""

    page_id: str = Field(..., description="e.g. 'P01'")
    template: str = Field(default="", description="Template basename e.g. '001_cover'")
    description: str = Field(default="")
    generation_mode: str = Field(default="", description="'mirror' | 'standard' | '' (inherit global)")


class ProjectConfig(BaseModel):
    """Configuration for a PPT generation project."""

    project_path: str = Field(..., description="Absolute path to project directory")
    is_mirror: bool = Field(default=False, description="Global mirror mode flag")
    canvas_format: str = Field(default="ppt169", description="'ppt169' or 'ppt43'")
    colors: list[str] = Field(default_factory=list, description="Hex color palette")
    total_pages: int = Field(default=0)


class PageContext(BaseModel):
    """Structured context for a single page (from ContextBroker)."""

    page_id: str
    page_num: int
    title: str = ""
    brief: str = ""
    rhythm: str = ""
    layout: str = ""
    page_type: str = "content"
    page_type_label: str = "内容页"
    colors: list[str] = Field(default_factory=list)
    charts: str = ""
    template_exists: bool = False
    template_file: str = ""


class QualityError(BaseModel):
    """A quality check error for a specific page."""

    page_num: int
    errors: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    """Metadata describing a skill for the platform registry."""

    name: str
    description: str = ""
    version: str = "0.1.0"
    supported_ui_types: list[str] = Field(
        default_factory=lambda: ["svg_slides"],
        description="UI artifact types this skill can produce",
    )


class ArtifactEvent(BaseModel):
    """An artifact creation event with type metadata for frontend routing."""

    path: str
    type: str = "svg"  # svg | markdown | code | dataframe | pptx
    ui_hint: str = ""  # Optional frontend rendering hint
