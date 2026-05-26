"""PPTMasterSkill — Full 7-step ppt-master workflow."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from harness.agent_adapters import OpenAIAgentAdapter
from harness.skill import BaseSkill, SkillMetadata
from skills.ppt_master.config import load_reference
from skills.ppt_master.agents import (
    source_agent, research_agent, project_agent,
    strategist_agent, spec_generator_agent,
    image_agent, executor_agent, notes_agent, export_agent,
    page_worker_standard,
    chart_verify_agent,
)
from skills.ppt_master.context_broker import (
    get_page_context, get_project_summary, compact_json,
)
from skills.ppt_master.spec_contract import build_spec_contract, save_spec_contract

if TYPE_CHECKING:
    from harness.session import SkillSession

log = logging.getLogger(__name__)
adapter = OpenAIAgentAdapter()


# ─── Helpers ──────────────────────────────────

def _parse_page_outline(design_spec: str) -> list[dict]:
    """Extract page info from design_spec.md — only from the page structure section.

    Looks for lines like:
      ### Page 1: 封面
      ### Page 2: 核心内容
      ### 第 1 页: 封面
    Stops collecting when we hit a non-page heading (e.g. ## 3. 设计规范).
    Returns pages with strictly increasing page numbers.
    """
    pages = []
    seen_nums: set[int] = set()
    in_page_section = False
    current_page: dict | None = None
    current_points: list[str] = []

    page_heading = re.compile(
        r"^#{2,3}\s*(?:Page|P|第)\s*(\d+)\s*[页：:．.\s\-—]+(.+?)$",
        re.IGNORECASE,
    )
    section_heading = re.compile(r"^#{1,2}\s*\d+[\.\s]", re.IGNORECASE)

    for line in design_spec.split("\n"):
        stripped = line.strip()

        # Detect start of page section
        pm = page_heading.match(stripped)
        if pm:
            num = int(pm.group(1))
            title = pm.group(2).strip()

            # Skip duplicates (e.g. layout reference pages)
            if num in seen_nums:
                continue
            seen_nums.add(num)
            in_page_section = True

            # Save previous page
            if current_page is not None:
                current_page["brief"] = "\n".join(current_points[:5])
                pages.append(current_page)

            current_page = {"num": num, "title": title, "brief": ""}
            current_points = []
            continue

        # If we hit a new top-level section after collecting pages, stop
        if in_page_section and section_heading.match(stripped) and not pm:
            break

        # Collect bullet points for current page
        if current_page is not None and stripped.startswith("- "):
            current_points.append(stripped[2:])

    # Save last page
    if current_page is not None:
        current_page["brief"] = "\n".join(current_points[:5])
        pages.append(current_page)

    # Sort by page number
    pages.sort(key=lambda p: p["num"])
    return pages






def _detect_source_type(files: list[str]) -> tuple[str, str]:
    """Return (type, path) for the first recognized source file."""
    for f in files:
        ext = Path(f).suffix.lower().lstrip(".")
        if ext in ("pdf", "docx", "doc", "xlsx", "pptx", "ppt", "epub", "html"):
            return ext, f
        if f.startswith("http"):
            return "url", f
    return "", ""




# ═══════════════════════════════════════════════
# Pipeline steps — each is an independent async function
# ═══════════════════════════════════════════════

async def _step_source_processing(
    session: "SkillSession", files: list[str], user_input: str, project_dir: str,
) -> str:
    """Step 1: Convert source file to Markdown, or run topic research."""
    await session.emit("step_start", step="source_processing", message="处理源文件...")

    source_type, source_path = _detect_source_type(files)
    markdown_content = ""

    if source_type and source_path:
        log.info("Converting source: %s (%s)", source_path, source_type)
        markdown_content = await adapter.run_agent(
            source_agent,
            input_text=f"转换文件为 Markdown:\n路径: {source_path}\n类型: {source_type}",
        )
        # Detect conversion failure — don't let error messages become PPT content
        if not markdown_content or "❌" in markdown_content[:200] or "转换失败" in markdown_content[:500]:
            raise RuntimeError(f"源文件转换失败，请检查文件是否完整或格式是否正确: {source_path}")
    elif not any(f.endswith(".md") for f in files):
        log.info("No source file, running topic research")
        await session.emit("step_start", step="topic_research", message="正在进行话题调研...")
        markdown_content = await adapter.run_agent(
            research_agent,
            input_text=f"请为以下主题进行调研:\n\n{user_input}\n\n项目路径: {project_dir}",
        )
        await session.emit("step_done", step="topic_research")
    else:
        for f in files:
            if f.endswith(".md"):
                markdown_content = Path(f).read_text(encoding="utf-8")
                break

    await session.emit("step_done", step="source_processing", message="源文件处理完毕")
    return markdown_content


async def _step_project_init(
    session: "SkillSession", project_dir: str, markdown_content: str,
) -> None:
    """Step 2: Create project directory structure and save source content."""
    await session.emit("step_start", step="project_init", message="初始化项目...")

    os.makedirs(project_dir, exist_ok=True)
    for sub in ("sources", "svg_output", "images", "notes", "exports"):
        os.makedirs(os.path.join(project_dir, sub), exist_ok=True)

    if markdown_content:
        src_file = os.path.join(project_dir, "sources", "content.md")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(markdown_content[:30000])

    session.state["project_path"] = project_dir
    await session.emit("step_done", step="project_init")


async def _step_template_check(
    session: "SkillSession", user_input: str, project_dir: str,
) -> str:
    """Step 3: Always use standard (General) mode — AI generates SVG from scratch."""
    await session.emit("step_start", step="template_check", message="设计模式: AI 自由设计 (General)")
    template_info = "AI 自由设计 (General 风格)"
    await session.emit("step_done", step="template_check", message=template_info)
    return template_info


async def _step_strategist(
    session: "SkillSession", user_input: str,
    markdown_content: str, template_info: str,
) -> str:
    """Step 4: Generate eight-confirmations design proposal."""
    await session.emit("step_start", step="strategist", message="正在生成设计方案...")

    source_summary = markdown_content[:5000] if markdown_content else user_input

    eight_confirmations = await adapter.run_agent(
        strategist_agent,
        input_text=(
            f"请为以下内容生成 PPT 八项确认建议:\n\n"
            f"用户需求: {user_input}\n\n"
            f"源内容摘要:\n{source_summary}\n\n"
            f"设计模式: {template_info}\n"
        ),
    )

    session.save_artifact("eight_confirmations.md", eight_confirmations)
    session.state["eight_confirmations"] = eight_confirmations
    await session.emit("artifact_created", path="eight_confirmations.md", type="markdown")
    await session.emit("step_done", step="strategist", message="八项确认已生成")
    return eight_confirmations


async def _step_generate_spec(
    session: "SkillSession", project_path: str,
    eight_confirmations: str, user_response: str, markdown_content: str,
) -> tuple[str, str]:
    """Step 4b: Generate design_spec.md and spec_lock.md.

    Returns (design_spec, spec_lock) contents.
    """
    await session.emit("step_start", step="generate_spec", message="正在生成设计文档...")

    await adapter.run_agent(
        spec_generator_agent,
        input_text=(
            f"根据以下确认方案，生成 design_spec.md 和 spec_lock.md:\n\n"
            f"八项确认:\n{eight_confirmations}\n\n"
            f"用户反馈: {user_response}\n\n"
            f"源内容:\n{markdown_content[:8000]}\n\n"
            f"项目路径: {project_path}\n"
        ),
    )

    design_spec = spec_lock = ""
    ds_path = os.path.join(project_path, "design_spec.md")
    sl_path = os.path.join(project_path, "spec_lock.md")
    if os.path.exists(ds_path):
        with open(ds_path, "r", encoding="utf-8") as f:
            design_spec = f.read()
        session.save_artifact("design_spec.md", design_spec)
    if os.path.exists(sl_path):
        with open(sl_path, "r", encoding="utf-8") as f:
            spec_lock = f.read()
        session.save_artifact("spec_lock.md", spec_lock)

    try:
        contract = build_spec_contract(design_spec, spec_lock)
        contract_path = save_spec_contract(project_path, contract)
        session.save_artifact("spec_contract.json", contract_path.read_text(encoding="utf-8"))
        session.state["spec_contract"] = contract
        for warning in contract.get("warnings", []):
            await session.emit("log", message=warning, level="warning")
    except Exception as e:
        await session.emit("step_error", step="generate_spec", error=str(e))
        raise

    await session.emit("step_done", step="generate_spec", message="设计文档已生成")

    # LaTeX formula rendering: detect formulas and trigger rendering
    if os.path.exists(os.path.join(project_path, "formula_manifest.json")):
        try:
            from skills.ppt_master.config import run_script
            log.info("Detected formula_manifest.json, rendering LaTeX formulas")
            await session.emit("log", message="检测到公式，正在渲染 LaTeX...", level="info")
            code, stdout, stderr = run_script("latex_render.py", [project_path])
            if code == 0:
                await session.emit("log", message="✅ LaTeX 公式渲染完成", level="info")
            else:
                await session.emit("log", message=f"⚠️ LaTeX 渲染部分失败: {(stderr or stdout)[:200]}", level="warning")
        except Exception as e:
            log.warning("LaTeX rendering failed (non-fatal): %s", e)
            await session.emit("log", message=f"公式渲染失败(非致命): {e}", level="warning")

    return design_spec, spec_lock


async def _step_image_acquisition(
    session: "SkillSession", project_path: str, design_spec: str,
) -> None:
    """Step 5: Conditionally acquire images (AI generation / web fetch)."""
    enable_images = session.state.get("enable_images", False)
    needs_images = (
        "acquire via: ai" in design_spec.lower()
        or "acquire via: web" in design_spec.lower()
    )

    if enable_images and needs_images:
        await session.emit("step_start", step="image_acquisition", message="获取图片资源...")
        try:
            await adapter.run_agent(
                image_agent,
                input_text=(
                    f"检查并获取图片资源:\n"
                    f"项目路径: {project_path}\n"
                    f"design_spec (图片部分):\n{design_spec[-3000:]}"
                ),
            )
        except Exception as e:
            log.warning("Image acquisition failed (non-fatal): %s", e)
        await session.emit("step_done", step="image_acquisition")
    else:
        reason = "用户未启用 AI 配图" if not enable_images else "无图片需要获取"
        await session.emit("step_start", step="image_acquisition", message=reason)
        await session.emit("step_done", step="image_acquisition")




def _build_page_prompt(
    page_num: int, page_title: str, page_brief: str,
    project_path: str, spec_lock: str,
    canvas_viewbox: str = "",
    previous_summaries: list[str] | None = None,
) -> str:
    """Build page prompt using ContextBroker (progressive disclosure) + cross-page context."""
    page_id = f"P{page_num:02d}"
    vb = canvas_viewbox or CANVAS_VIEWBOX["ppt169"]

    # Get structured page context from broker (small, focused)
    ctx = get_page_context(project_path, page_num)

    color_str = ", ".join(ctx['colors'])
    charts_str = f"\n图表:\n{ctx['charts']}" if ctx.get('charts') else ""

    # Typography info (compact)
    typo_str = ""
    if ctx.get('typography') and len(ctx['typography']) > 1:
        typo_lines = []
        for row in ctx['typography'][1:4]:  # skip header, limit to 3 rows
            typo_lines.append(" | ".join(str(c) for c in row[:3]))
        if typo_lines:
            typo_str = f"\n字体: {'; '.join(typo_lines)}"

    # Icon strategy (compact)
    icon_str = ""
    if ctx.get('icons'):
        icon_str = f"\nicon: {', '.join(ctx['icons'][:8])}"

    # Cross-page design history (lightweight summaries of previous pages)
    history_str = ""
    if previous_summaries:
        history_str = (
            f"\n\n已完成页面设计概览（请保持视觉一致性，避免重复布局）:\n"
            + "\n".join(previous_summaries[-6:])  # last 6 pages max
        )

    return (
        f"生成 {page_id} — {page_title}\n\n"
        f"项目路径: {project_path}\n"
        f"页面类型: {ctx['page_type_label']} | 节奏: {ctx['rhythm']}\n"
        f"canvas: viewBox=\"{vb}\"\n"
        f"色彩: {color_str}{typo_str}{icon_str}\n"
        f"内容要点:\n{page_brief}\n"
        f"{charts_str}"
        f"{history_str}\n\n"
        f"执行: 生成完整 SVG → write_svg_page('{project_path}', {page_num}, svg_content)"
    )


# Canvas viewBox defaults (from ppt-master references/canvas-formats.md)
CANVAS_VIEWBOX: dict[str, str] = {
    "ppt169": "0 0 1280 720",
    "ppt43": "0 0 1024 768",
    "xhs": "0 0 1242 1660",
    "story": "0 0 1080 1920",
}

# Per-page generation timeout (seconds)
_PAGE_TIMEOUT = 120

# Minimum SVG chars before emitting a streaming preview
_SVG_STREAM_MIN_CHARS = 200


def _extract_partial_svg(accumulated_args: str) -> str:
    """Best-effort extraction of partial SVG from streaming JSON arguments.

    The LLM is calling write_svg_page(project_path, page_number, svg_content).
    The accumulated_args is the *partial* JSON being built, e.g.:
      {"project_path": "...", "page_number": 1, "svg_content": "<svg ...
    We locate the svg_content value and JSON-unescape it.
    """
    # Find the svg_content key and its opening quote
    marker = '"svg_content"'
    idx = accumulated_args.find(marker)
    if idx < 0:
        marker = "'svg_content'"
        idx = accumulated_args.find(marker)
    if idx < 0:
        return ""

    # Skip to the colon and opening quote
    rest = accumulated_args[idx + len(marker):]
    rest = rest.lstrip()
    if rest.startswith(":"):
        rest = rest[1:].lstrip()
    if not rest.startswith('"'):
        return ""
    rest = rest[1:]  # skip opening quote

    # Everything after the opening quote is partial SVG (JSON-escaped)
    # The closing quote may not exist yet (streaming), so take everything
    # If there's a closing `"}`, strip it
    if rest.endswith('"}'):
        rest = rest[:-2]
    elif rest.endswith('"'):
        rest = rest[:-1]

    # JSON-unescape common sequences
    svg = (
        rest
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
        .replace("\\/", "/")
    )
    return svg


def _extract_canvas_viewbox(spec_lock: str, default_format: str = "ppt169") -> str:
    """Extract canvas viewBox from spec_lock, fallback to default."""
    # Try to find viewBox in spec_lock canvas section
    m = re.search(r'viewBox[":\s]+([\d\s]+)', spec_lock, re.IGNORECASE)
    if m:
        vb = m.group(1).strip()
        if len(vb.split()) == 4:
            return vb
    # Try format keyword
    for fmt, vb in CANVAS_VIEWBOX.items():
        if fmt in spec_lock.lower():
            return vb
    return CANVAS_VIEWBOX.get(default_format, CANVAS_VIEWBOX["ppt169"])


def _extract_page_summary(svg_path: Path, page_num: int, page_title: str) -> str:
    """Extract a lightweight design summary (~100-200 chars) from a generated SVG.

    Used to give subsequent pages cross-page visual context without
    blowing up the prompt with full SVG content.
    """
    if not svg_path.exists():
        return f"P{page_num:02d} {page_title}: [未生成]"
    try:
        svg = svg_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return f"P{page_num:02d} {page_title}: [读取失败]"

    # Extract top-level group ids (layout structure indicators)
    groups = re.findall(r'<g\s+[^>]*id="([^"]+)"', svg)
    # Count key element types
    n_text = len(re.findall(r'<text\b', svg))
    n_rect = len(re.findall(r'<rect\b', svg))
    n_image = len(re.findall(r'<image\b', svg))
    n_circle = len(re.findall(r'<circle\b', svg))
    # Extract dominant fill colors (first few unique hex colors)
    fills = list(dict.fromkeys(re.findall(r'fill="(#[0-9a-fA-F]{3,8})"', svg)))

    parts = [f"P{page_num:02d} {page_title}:"]
    if groups:
        parts.append(f"结构=[{', '.join(groups[:5])}]")
    elem_parts = []
    if n_text:
        elem_parts.append(f"{n_text}文本")
    if n_rect:
        elem_parts.append(f"{n_rect}矩形")
    if n_image:
        elem_parts.append(f"{n_image}图片")
    if n_circle:
        elem_parts.append(f"{n_circle}圆")
    if elem_parts:
        parts.append(f"元素({', '.join(elem_parts)})")
    if fills:
        parts.append(f"色彩=[{', '.join(fills[:4])}]")
    return " ".join(parts)


async def _step_executor(
    session: "SkillSession", project_path: str,
    spec_lock: str,
) -> list[dict]:
    """Step 6: Generate SVG pages sequentially (General style).

    Pages are driven entirely by spec_contract (built in step 4b).
    If the contract has no pages, the job fails explicitly.

    - Sequential generation: one page at a time for cross-page visual consistency.
    - Lightweight cross-page summary: each completed page's design is summarized
      (~100-200 chars) and injected into the next page's prompt.
    - Per-page timeout: prevents single-page hangs from blocking the pipeline.
    """
    await session.emit("step_start", step="executor", message="正在生成 SVG 页面...")

    contract = session.state.get("spec_contract")
    if not contract or not contract.get("pages"):
        error_message = "spec_contract 无页面结构，无法执行生成。请检查设计文档。"
        await session.emit("step_error", step="executor", error=error_message)
        raise RuntimeError(error_message)

    page_outline = [
        {"num": int(p["num"]), "title": str(p.get("title") or f"第 {int(p['num'])} 页"), "brief": str(p.get("brief") or "")}
        for p in contract["pages"]
    ]

    # Resolve canvas viewBox from spec_lock
    canvas_format = session.state.get("canvas_format", "ppt169")
    canvas_vb = _extract_canvas_viewbox(spec_lock, canvas_format)

    log.info("Executor: %d pages, canvas=%s (standard/general)",
             len(page_outline), canvas_vb)

    # Emit outline for frontend preview
    outline_pages = [
        {"page": p["num"], "title": p["title"],
         "summary": p["brief"][:100], "status": "pending"}
        for p in page_outline
    ]
    await session.emit("outline", pages=outline_pages)

    # Sequential page generation with cross-page visual context
    failed_pages: dict[int, str] = {}
    previous_summaries: list[str] = []

    for page_info in page_outline:
        page_num = page_info["num"]

        await session.emit(
            "page_generating",
            page=page_num, total=len(page_outline), title=page_info["title"],
        )

        prompt = _build_page_prompt(
            page_num, page_info["title"], page_info["brief"],
            project_path, spec_lock,
            canvas_viewbox=canvas_vb,
            previous_summaries=previous_summaries,
        )

        try:
            await asyncio.wait_for(
                adapter.run_agent(page_worker_standard, input_text=prompt, max_turns=10),
                timeout=_PAGE_TIMEOUT,
            )
            await session.emit(
                "artifact_created",
                path=f"svg_output/page_{page_num:02d}.svg", type="svg",
            )
            # Extract lightweight summary for cross-page context
            svg_path = Path(project_path) / "svg_output" / f"page_{page_num:02d}.svg"
            summary = _extract_page_summary(svg_path, page_num, page_info["title"])
            previous_summaries.append(summary)
        except asyncio.TimeoutError:
            log.error("Page %d timed out after %ds", page_num, _PAGE_TIMEOUT)
            failed_pages[page_num] = f"超时 ({_PAGE_TIMEOUT}s)"
            await session.emit("page_error", page=page_num, error=f"生成超时 ({_PAGE_TIMEOUT}s)")
        except Exception as e:
            log.error("Page %d failed: %s", page_num, e)
            failed_pages[page_num] = str(e)
            await session.emit("page_error", page=page_num, error=str(e))

    missing_pages = [
        p["num"]
        for p in page_outline
        if not (Path(project_path) / "svg_output" / f"page_{p['num']:02d}.svg").exists()
    ]
    total = len(page_outline)
    success_count = total - len(missing_pages)

    if missing_pages:
        details = []
        if failed_pages:
            details.append("失败页: " + ", ".join(f"P{num:02d}: {err[:80]}" for num, err in sorted(failed_pages.items())))
        details.append("缺失页: " + ", ".join(f"P{num:02d}" for num in missing_pages))
        detail_msg = "；".join(details)

        # Fail only if majority of pages are missing (>50%)
        if success_count < total * 0.5:
            error_message = f"SVG 页面生成失败（仅 {success_count}/{total} 成功）；" + detail_msg
            await session.emit("step_error", step="executor", error=error_message)
            raise RuntimeError(error_message)
        else:
            # Partial success — continue with warning
            await session.emit("log", message=f"⚠️ 部分页面未生成 ({success_count}/{total} 成功)；{detail_msg}", level="warning")

    await session.emit("step_done", step="executor", message=f"SVG 生成完毕 ({success_count}/{total} 页)")
    return page_outline


async def _step_design_anchor(
    session: "SkillSession", project_path: str, spec_lock: str,
) -> None:
    """Emit design parameters as a visible anchor before page generation starts.

    Gives the user (and LLM) confirmation of the resolved design contract:
    canvas dimensions, color palette, typography, and total page count.
    """
    await session.emit("step_start", step="design_anchor", message="确认设计参数...")

    canvas_format = session.state.get("canvas_format", "ppt169")
    canvas_vb = _extract_canvas_viewbox(spec_lock, canvas_format)
    contract = session.state.get("spec_contract", {})
    total_pages = len(contract.get("pages", []))

    # Extract colors and font from context_broker
    from skills.ppt_master.context_broker import _extract_hex_colors, _section
    colors = _extract_hex_colors(_section(spec_lock, "colors"))
    color_str = ", ".join(colors[:8]) if colors else "未指定"

    # Typography summary (first entry)
    typo_str = "未指定"
    from skills.ppt_master.context_broker import _parse_markdown_table
    typo_rows = _parse_markdown_table(_section(spec_lock, "typography"))
    if len(typo_rows) > 1:
        typo_str = " | ".join(str(c) for c in typo_rows[1][:4])

    anchor_message = (
        f"📐 **设计锚点确认**\n"
        f"- Canvas: `viewBox=\"{canvas_vb}\"`\n"
        f"- 色彩: {color_str}\n"
        f"- 字体: {typo_str}\n"
        f"- 总页数: {total_pages} 页\n"
    )
    await session.emit("log", message=anchor_message, level="info")
    await session.emit("step_done", step="design_anchor", message="设计参数已确认")


async def _step_chart_verification(
    session: "SkillSession", project_path: str,
    design_spec: str, spec_lock: str,
) -> None:
    """Run chart coordinate verification on pages with data-driven charts.

    Only triggers if the design_spec contains chart/visualization indicators.
    Uses chart_verify_agent to calculate and fix coordinate discrepancies.
    """
    # Detect if deck has data charts worth verifying
    chart_keywords = ["bar_chart", "line_chart", "pie_chart", "radar_chart",
                      "柱状图", "折线图", "饼图", "雷达图", "数据可视化"]
    has_charts = any(kw in design_spec.lower() or kw in spec_lock.lower() for kw in chart_keywords)

    if not has_charts:
        return

    await session.emit("step_start", step="chart_verify", message="图表坐标校验...")

    # Identify chart pages from spec_contract
    contract = session.state.get("spec_contract", {})
    chart_pages = []
    for page in contract.get("pages", []):
        brief = str(page.get("brief", "")).lower()
        if any(kw in brief for kw in ["chart", "图表", "柱状", "折线", "饼图", "数据"]):
            chart_pages.append(page)

    if not chart_pages:
        await session.emit("log", message="未发现需要坐标校验的图表页", level="info")
        await session.emit("step_done", step="chart_verify")
        return

    canvas_format = session.state.get("canvas_format", "ppt169")
    page_list = "\n".join(
        f"P{int(p['num']):02d}: {p.get('title', '')} — {str(p.get('brief', ''))[:100]}"
        for p in chart_pages
    )

    try:
        await asyncio.wait_for(
            adapter.run_agent(
                chart_verify_agent,
                input_text=(
                    f"验证以下图表页的坐标精度:\n\n{page_list}\n\n"
                    f"项目路径: {project_path}\n"
                    f"canvas: {canvas_format}\n\n"
                    f"对每页: 从 SVG 中提取数据值，使用 verify_chart_coordinates 计算正确坐标，"
                    f"如偏差 >5px 则用 write_svg_page 修复。"
                ),
                max_turns=10,
            ),
            timeout=180,
        )
        await session.emit("log", message=f"图表校验完成 ({len(chart_pages)} 页)", level="info")
    except asyncio.TimeoutError:
        log.warning("Chart verification timed out")
        await session.emit("log", message="图表校验超时，跳过", level="warning")
    except Exception as e:
        log.warning("Chart verification failed (non-fatal): %s", e)
        await session.emit("log", message=f"图表校验失败(非致命): {e}", level="warning")

    await session.emit("step_done", step="chart_verify")


# ─── Quality Check Policy ───────────────────────────
# Explicit, predictable behavior for quality gate.
QUALITY_POLICY = {
    "max_retries": 1,              # Number of LLM retry rounds
    "retry_timeout_per_page": 60,  # Seconds per page retry
    "fail_on_xml_error": False,    # XML malformed → fail entire job?
    "fail_on_forbidden": False,    # forbidden elements → fail entire job?
    "continue_on_warning": True,   # warnings only → continue
}
_QUALITY_RETRY_TIMEOUT = QUALITY_POLICY["retry_timeout_per_page"]


async def _step_quality_check(
    session: "SkillSession", project_path: str,
    spec_lock: str,
) -> None:
    """Step 6c: Run SVG quality checker, retry failed pages with error context."""
    await session.emit("step_start", step="quality_check", message="质量检查...")
    from skills.ppt_master.config import run_script

    max_retries = 1

    for attempt in range(max_retries + 1):
        try:
            code, stdout, stderr = run_script("svg_quality_checker.py", [project_path])
            output = (stdout + stderr).strip()
            log.info("Quality check (attempt %d): %s", attempt, output[:300])
        except Exception as e:
            log.warning("Quality check script failed: %s", e)
            await session.emit("log", message=f"质量检查脚本异常: {e}", level="warning")
            break

        if code == 0 or attempt >= max_retries:
            if code != 0:
                log.warning("Quality check found issues but max retries reached, continuing")
                await session.emit("log", message="质量检查发现问题但已达最大重试次数，继续流程", level="warning")
            break

        # Parse per-page errors and retry only those pages
        failed_pages = _parse_quality_errors(output)
        if not failed_pages:
            break

        await session.emit("log", message=f"质量检查发现 {len(failed_pages)} 页需要修复，正在重试...", level="info")

        for page_num, errors in failed_pages.items():
            svg_path = Path(project_path) / "svg_output" / f"page_{page_num:02d}.svg"
            backup_path = svg_path.with_suffix(".svg.bak")

            # Backup original SVG before any fix attempt
            if svg_path.exists():
                shutil.copy2(svg_path, backup_path)

            # Read original SVG to give LLM context for targeted patches
            original_svg = ""
            if svg_path.exists():
                try:
                    original_svg = svg_path.read_text(encoding="utf-8")
                    if len(original_svg) > 6000:
                        original_svg = original_svg[:6000] + "\n<!-- ... truncated -->"
                except Exception:
                    pass

            error_context = "\n".join(f"- {e}" for e in errors[:5])
            fix_prompt = (
                f"修复 P{page_num:02d} 的质量问题（仅修复指定错误，保留原有设计和布局）:\n\n"
                f"项目路径: {project_path}\n"
                f"错误:\n{error_context}\n\n"
            )
            if original_svg:
                fix_prompt += (
                    f"当前 SVG 内容（请在此基础上修复，不要重新设计）:\n"
                    f"```svg\n{original_svg}\n```\n\n"
                )
            fix_prompt += (
                f"重要: 只修复上述错误，保持整体设计、布局、色彩不变。\n"
                f"执行: 修改后的完整 SVG → write_svg_page('{project_path}', {page_num}, svg_content)"
            )
            try:
                await asyncio.wait_for(
                    adapter.run_agent(page_worker_standard, input_text=fix_prompt),
                    timeout=_QUALITY_RETRY_TIMEOUT,
                )
                log.info("Retried page %d after quality error", page_num)
                await session.emit("log", message=f"第 {page_num} 页修复完成", level="info")
                # Remove backup on success
                if backup_path.exists():
                    backup_path.unlink()
            except asyncio.TimeoutError:
                log.error("Page %d retry timed out (%ds), restoring original", page_num, _QUALITY_RETRY_TIMEOUT)
                # Restore original SVG on timeout
                if backup_path.exists():
                    shutil.copy2(backup_path, svg_path)
                    backup_path.unlink()
                await session.emit("log", message=f"第 {page_num} 页修复超时，已还原原版", level="warning")
            except Exception as e:
                log.error("Page %d retry failed: %s, restoring original", page_num, e)
                # Restore original SVG on failure
                if backup_path.exists():
                    shutil.copy2(backup_path, svg_path)
                    backup_path.unlink()
                await session.emit("log", message=f"第 {page_num} 页修复失败，已还原原版", level="warning")

    await session.emit("step_done", step="quality_check")


def _parse_quality_errors(output: str) -> dict[int, list[str]]:
    """Parse quality checker output to extract per-page errors."""
    errors: dict[int, list[str]] = {}
    current_page: int | None = None
    for line in output.splitlines():
        # Look for page references like "page_03.svg" or "Page 3"
        page_match = re.search(r"page[_\s]*(\d+)", line, re.IGNORECASE)
        if page_match:
            current_page = int(page_match.group(1))
        if current_page and ("❌" in line or "error" in line.lower() or "fail" in line.lower()):
            errors.setdefault(current_page, []).append(line.strip()[:200])
    return errors


async def _step_speaker_notes(
    session: "SkillSession", project_path: str, page_outline: list[dict],
) -> None:
    """Step 6d: Generate speaker notes."""
    await session.emit("step_start", step="notes", message="正在生成演讲稿...")

    pages_summary = "\n".join(
        f"第{p['num']}页: {p['title']} — {p['brief'][:60]}" for p in page_outline
    )
    try:
        await adapter.run_agent(
            notes_agent,
            input_text=(
                f"请为以下页面生成演讲稿:\n\n{pages_summary}\n\n"
                f"项目路径: {project_path}\n"
                f"调用 write_speaker_notes(project_path='{project_path}', content=<演讲稿>)"
            ),
        )
        await session.emit("artifact_created", path="notes/total.md", type="markdown")
    except Exception as e:
        log.warning("Notes generation failed: %s", e)

    await session.emit("step_done", step="notes")


async def _step_export(session: "SkillSession", project_path: str) -> None:
    """Step 7: Post-processing (finalize SVG + svg_to_pptx) and export."""
    await session.emit("step_start", step="export", message="后处理与导出 PPTX...")

    try:
        export_result = await adapter.run_agent(
            export_agent,
            input_text=(
                f"执行后处理:\n"
                f"项目路径: {project_path}\n"
                f"调用 run_post_processing(project_path='{project_path}', "
                f"transition='fade', animation='auto', merge_paragraphs=True)"
            ),
        )
        log.info("Export result: %s", export_result[:200])

        exports_dir = Path(project_path) / "exports"
        for pptx_file in exports_dir.glob("*.pptx"):
            dest = session.artifact_path(f"exports/{pptx_file.name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pptx_file, dest)
            await session.emit("artifact_created", path=f"exports/{pptx_file.name}", type="pptx")

    except Exception as e:
        log.warning("Export failed (non-fatal): %s", e)
        await session.emit("step_error", step="export", error=str(e))

    await session.emit("step_done", step="export", message="导出完成")

    # Copy SVGs to artifacts
    svg_dir = Path(project_path) / "svg_output"
    if svg_dir.exists():
        for svg_file in sorted(svg_dir.glob("*.svg")):
            dest = session.artifact_path(f"svg_output/{svg_file.name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(svg_file, dest)


# ═══════════════════════════════════════════════
# PPTMasterSkill — thin orchestrator
# ═══════════════════════════════════════════════

class PPTMasterSkill(BaseSkill):
    name = "ppt-master"
    metadata = SkillMetadata(
        name="ppt-master",
        description="AI-powered PPT generation (General style)",
        version="2.0.0",
        supported_ui_types=["svg_slides", "markdown"],
    )

    async def run(self, session: "SkillSession") -> None:
        """Phase 1 (Steps 1-4): Source → Project → Template → Strategist → Pause."""
        user_input = session.user_input
        files: list[str] = session.state.get("files", [])
        project_dir = str(session.workspace / "project")

        markdown_content = await _step_source_processing(session, files, user_input, project_dir)
        session.state["markdown_content"] = markdown_content[:15000]

        await _step_project_init(session, project_dir, markdown_content)

        template_info = await _step_template_check(session, user_input, project_dir)

        await _step_strategist(session, user_input, markdown_content, template_info)

        await session.require_confirmation(
            title="确认 PPT 设计方案（八项确认）",
            content=session.state["eight_confirmations"],
        )

    async def resume(self, session: "SkillSession", user_response: str) -> None:
        """Phase 2 (Steps 4b-7): Spec → Images → Executor → Charts → Notes → Export."""
        project_path = session.state.get("project_path", str(session.workspace / "project"))
        markdown_content = session.state.get("markdown_content", "")
        eight_confirmations = session.state.get("eight_confirmations", "")

        design_spec, spec_lock = await _step_generate_spec(
            session, project_path, eight_confirmations, user_response, markdown_content,
        )

        await _step_image_acquisition(session, project_path, design_spec)

        # Emit design anchor before executor starts
        await _step_design_anchor(session, project_path, spec_lock)

        page_outline = await _step_executor(session, project_path, spec_lock)

        await _step_speaker_notes(session, project_path, page_outline)

        await _step_export(session, project_path)
