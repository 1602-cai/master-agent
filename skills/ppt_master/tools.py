"""Full PPT Master tool set — wraps ppt-master scripts as @function_tool.

Path safety is enforced by the @_with_path_guards decorator applied to every
tool that accepts project_path or source_path. Individual tool bodies no longer
need to call validation helpers manually.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from agents import function_tool

from harness.safety import resolve_under, safe_filename, sanitize_svg, validate_svg
from skills.ppt_master.config import (
    run_script, SCRIPTS_DIR, PPT_MASTER_ROOT, DATA_DIR,
    CHARTS_DIR, ICONS_DIR, preview_process,
)
import skills.ppt_master.config as _cfg

# ═══════════════════════════════════════════════
# Path guard infrastructure
# ═══════════════════════════════════════════════

_JOBS_ROOT = (DATA_DIR / "jobs").resolve()
_DATA_ROOT = DATA_DIR.resolve()


def _validate_project(raw: str) -> str:
    """Validate project_path → must resolve under data/jobs/."""
    candidate = Path(raw).resolve(strict=False)
    try:
        rel = candidate.relative_to(_JOBS_ROOT)
    except ValueError as exc:
        raise ValueError(f"project_path must be under data/jobs: {raw}") from exc
    return str(resolve_under(_JOBS_ROOT, rel))


def _validate_source(raw: str, source_type: str = "") -> str:
    """Validate source_path → must be under data/ or http/https URL."""
    parsed = urlparse(raw)
    if source_type in {"url", "web"} or parsed.scheme in {"http", "https"}:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Only http/https URLs are allowed as web sources")
        return raw
    candidate = Path(raw).resolve(strict=False)
    try:
        rel = candidate.relative_to(_DATA_ROOT)
    except ValueError as exc:
        raise ValueError(f"source_path must be under data/: {raw}") from exc
    return str(resolve_under(_DATA_ROOT, rel))


def _with_path_guards(fn):
    """Decorator: auto-validates project_path and source_path arguments.

    Apply between the function def and @function_tool so tool bodies stay clean.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if "project_path" in bound.arguments:
            bound.arguments["project_path"] = _validate_project(bound.arguments["project_path"])
        if "project_dir" in bound.arguments:
            bound.arguments["project_dir"] = _validate_project(bound.arguments["project_dir"])
        if "source_path" in bound.arguments:
            stype = bound.arguments.get("source_type", "")
            bound.arguments["source_path"] = _validate_source(bound.arguments["source_path"], stype)
        return fn(*bound.args, **bound.kwargs)
    return wrapper


# Backward-compat aliases for tests
_project = lambda p: Path(_validate_project(p))
_project_str = _validate_project
_source = _validate_source

# ═══════════════════════════════════════════════
# Source conversion
# ═══════════════════════════════════════════════

SOURCE_CONVERTERS = {
    "pdf": "source_to_md/pdf_to_md.py",
    "docx": "source_to_md/doc_to_md.py",
    "doc": "source_to_md/doc_to_md.py",
    "epub": "source_to_md/doc_to_md.py",
    "html": "source_to_md/doc_to_md.py",
    "xlsx": "source_to_md/excel_to_md.py",
    "xlsm": "source_to_md/excel_to_md.py",
    "pptx": "source_to_md/ppt_to_md.py",
    "ppt": "source_to_md/ppt_to_md.py",
    "url": "source_to_md/web_to_md.py",
    "web": "source_to_md/web_to_md.py",
}


@function_tool
@_with_path_guards
def convert_source_to_markdown(source_path: str, source_type: str) -> str:
    """Convert source file to Markdown.

    Args:
        source_path: Path to file, or URL for web sources.
        source_type: File type (pdf/docx/xlsx/pptx/url/web/html/epub/etc).
    """
    script = SOURCE_CONVERTERS.get(source_type, "source_to_md/doc_to_md.py")
    code, stdout, stderr = run_script(script, [source_path])
    if code != 0:
        return f"❌ 转换失败 ({source_type}): {stderr[:500]}"
    return stdout if stdout else f"转换完成\n{stderr[:200]}"


@function_tool
def web_fetch_to_markdown(url: str) -> str:
    """Fetch a web page and convert to Markdown.

    Args:
        url: The URL to fetch.
    """
    safe_url = _validate_source(url, "url")
    code, stdout, stderr = run_script("source_to_md/web_to_md.py", [safe_url], timeout=60)
    if code != 0:
        return f"❌ 网页抓取失败: {stderr[:300]}"
    content = stdout or ""
    return content[:15000] if content else "❌ 未获取到网页内容"


@function_tool
@_with_path_guards
def save_research_document(project_path: str, filename: str, content: str) -> str:
    """Save research document into the project sources directory.

    Args:
        project_path: Project directory path.
        filename: Filename for the research doc (e.g. 'topic_research.md').
        content: Full Markdown content.
    """
    src_dir = resolve_under(Path(project_path), "sources")
    src_dir.mkdir(parents=True, exist_ok=True)
    path = resolve_under(src_dir, safe_filename(filename, "topic_research.md"))
    path.write_text(content, encoding="utf-8")
    return f"✅ 已保存: {path} ({len(content)} chars)"


# ═══════════════════════════════════════════════
# Project management
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def init_project(project_name: str, canvas_format: str, project_dir: str) -> str:
    """Initialize a PPT Master project.

    Args:
        project_name: Name for the project.
        canvas_format: Canvas format (ppt169/ppt43/xhs/story).
        project_dir: Parent directory for projects.
    """
    code, stdout, stderr = run_script(
        "project_manager.py",
        ["init", project_name, "--format", canvas_format, "--dir", project_dir],
    )
    return stdout if stdout else (f"❌ {stderr[:300]}" if code != 0 else "✅ 项目初始化完成")


@function_tool
@_with_path_guards
def import_source_to_project(project_path: str, source_file: str) -> str:
    """Import source file into project.

    Args:
        project_path: Project directory path.
        source_file: Source file path.
    """
    code, stdout, stderr = run_script(
        "project_manager.py",
        ["import-sources", project_path, source_file, "--copy"],
    )
    return stdout if stdout else ("✅ 源文件已导入" if code == 0 else f"⚠️ {stderr[:300]}")


@function_tool
@_with_path_guards
def validate_project(project_path: str) -> str:
    """Validate project structure.

    Args:
        project_path: Project directory path.
    """
    code, stdout, stderr = run_script("project_manager.py", ["validate", project_path])
    return (stdout + stderr)[:500]


# ═══════════════════════════════════════════════
# Design spec & spec lock
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def write_design_spec(project_path: str, content: str) -> str:
    """Write design_spec.md to the project.

    Args:
        project_path: Project directory path.
        content: Full content of design_spec.md.
    """
    path = resolve_under(Path(project_path), "design_spec.md")
    path.write_text(content, encoding="utf-8")
    return f"✅ design_spec.md ({len(content)} chars)"


@function_tool
@_with_path_guards
def write_spec_lock(project_path: str, content: str) -> str:
    """Write spec_lock.md to the project.

    Args:
        project_path: Project directory path.
        content: Full spec_lock.md content.
    """
    path = resolve_under(Path(project_path), "spec_lock.md")
    path.write_text(content, encoding="utf-8")
    return f"✅ spec_lock.md ({len(content)} chars)"


@function_tool
@_with_path_guards
def read_spec_lock(project_path: str) -> str:
    """Read spec_lock.md (Executor re-reads before each page).

    Args:
        project_path: Project directory path.
    """
    p = resolve_under(Path(project_path), "spec_lock.md")
    if p.exists():
        return p.read_text(encoding="utf-8")
    return "❌ spec_lock.md 不存在"


# ═══════════════════════════════════════════════
# SVG generation
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def write_svg_page(project_path: str, page_number: int, svg_content: str) -> str:
    """Write a SVG page to svg_output/.

    Args:
        project_path: Project directory path.
        page_number: Page number (1-indexed).
        svg_content: Complete SVG content string.
    """
    return _write_svg_page_impl(project_path, page_number, svg_content)


def _extract_text_content(text_element: str) -> str:
    """Extract visible text from a <text>...</text> element, preserving internal spaces."""
    return re.sub(r'<[^>]+>', '', text_element).strip()


def _normalize(s: str) -> str:
    """Normalize text for fuzzy matching: collapse all whitespace."""
    return re.sub(r'\s+', '', s)


def _write_svg_page_impl(project_path: str, page_number: int, svg_content: str) -> str:
    try:
        validate_svg(svg_content)
    except Exception as e:
        return f"❌ SVG 校验失败: {e}"
    svg_content = sanitize_svg(svg_content)
    svg_dir = resolve_under(Path(project_path), "svg_output")
    svg_dir.mkdir(parents=True, exist_ok=True)
    resolve_under(svg_dir, f"page_{page_number:02d}.svg").write_text(svg_content, encoding="utf-8")
    return f"✅ page_{page_number:02d}.svg"


@function_tool
@_with_path_guards
def read_template_svg(project_path: str, template_basename: str) -> str:
    """Read template SVG text map for Mirror mode (lightweight — no full SVG).

    Returns only the list of editable text elements and metadata.
    The full SVG is handled internally by write_mirror_page.

    Args:
        project_path: Project directory path.
        template_basename: Template filename without .svg (e.g. '001_cover').
    """
    from skills.ppt_master.context_broker import get_template_text_map
    tmap = get_template_text_map(project_path, Path(safe_filename(template_basename)).stem)
    if not tmap.get("exists"):
        return f"❌ 模板 SVG 未找到: {template_basename}.svg"
    lines = [
        f"--- 模板: {tmap['file']} (类型: {tmap['page_type']}) ---",
        f"共 {tmap['editable_text_count']} 个可编辑文字元素:",
        "可编辑文字 (old 字段直接复制下方引号内的文字即可，系统自动处理空格差异):",
    ]
    for item in tmap.get("editable_texts", []):
        lines.append(f'  [{item["index"]}] "{item["text"]}"')
    return "\n".join(lines)


@function_tool
@_with_path_guards
def get_page_design_context(project_path: str, page_number: int) -> str:
    """Get structured design context for a specific page (on-demand).

    Returns page-specific colors, typography, charts, constraints etc.
    Use this instead of reading the full spec_lock.md.

    Args:
        project_path: Project directory path.
        page_number: Page number (1-indexed).
    """
    from skills.ppt_master.context_broker import get_page_context
    ctx = get_page_context(project_path, page_number)
    lines = [
        f"=== {ctx['page_id']} 设计上下文 ===",
        f"标题: {ctx['title']}",
        f"页面类型: {ctx['page_type_label']} ({ctx['page_type']})",
        f"节奏: {ctx['rhythm']}",
        f"模板: {ctx['layout']}",
        f"色彩: {', '.join(ctx['colors'])}",
    ]
    if ctx.get('charts'):
        lines.append(f"图表要求:\n{ctx['charts']}")
    if ctx.get('forbidden'):
        lines.append("禁止事项: " + "; ".join(ctx['forbidden'][:6]))
    return "\n".join(lines)


@function_tool
@_with_path_guards
def write_mirror_page(project_path: str, page_number: int, template_basename: str, text_replacements: str) -> str:
    """Mirror mode: copy template SVG and replace only text.

    Fuzzy matching: whitespace differences between old text and template text
    are ignored automatically. The replacement rewrites all <tspan> content
    inside the matched <text> element.

    Args:
        project_path: Project directory path.
        page_number: Page number (1-indexed).
        template_basename: Template SVG basename.
        text_replacements: JSON [{"old":"原文","new":"新文"}, ...].
    """
    return _write_mirror_page_impl(project_path, page_number, template_basename, text_replacements)


def _write_mirror_page_impl(project_path: str, page_number: int, template_basename: str, text_replacements: str) -> str:
    project = Path(project_path)
    safe_template_basename = Path(safe_filename(template_basename)).stem
    tpl_dir = resolve_under(project, "templates")
    svg_path = resolve_under(tpl_dir, f"{safe_template_basename}.svg")
    if not svg_path.exists():
        candidates = list(tpl_dir.glob(f"*{safe_template_basename}*.svg"))
        if candidates:
            svg_path = candidates[0]
        else:
            return f"❌ 模板 SVG 未找到: {template_basename}.svg"

    content = sanitize_svg(svg_path.read_text(encoding="utf-8"))

    try:
        replacements = json.loads(text_replacements)
    except json.JSONDecodeError:
        return "❌ text_replacements 必须是有效 JSON"

    # Build a normalized-old → new_text lookup
    replace_map: list[tuple[str, str]] = []
    for r in replacements:
        old_text = r.get("old", "")
        new_text = r.get("new", "")
        if old_text:
            replace_map.append((_normalize(old_text), new_text))

    if not replace_map:
        # No replacements provided — just copy the template as-is
        svg_dir = resolve_under(project, "svg_output")
        svg_dir.mkdir(parents=True, exist_ok=True)
        with open(resolve_under(svg_dir, f"page_{page_number:02d}.svg"), "w", encoding="utf-8") as f:
            f.write(sanitize_svg(content))
        return f"⚠️ Mirror page_{page_number:02d}.svg (0 replacements — no old text provided)"

    replaced_count = 0

    def replace_text_element(match: re.Match) -> str:
        nonlocal replaced_count
        full_element = match.group(0)
        visible_text = _extract_text_content(full_element)
        normalized_visible = _normalize(visible_text)

        for norm_old, new_text in replace_map:
            if norm_old == normalized_visible or norm_old in normalized_visible:
                replaced_count += 1
                safe_new_text = escape(new_text, quote=False)
                # Strategy: replace text inside <tspan> elements
                tspans = list(re.finditer(r'(<tspan[^>]*>)([^<]*)(</tspan>)', full_element))
                if tspans:
                    # Put all new text into the first tspan, empty the rest
                    result = full_element
                    for idx, tm in enumerate(reversed(tspans)):
                        start, end = tm.start(), tm.end()
                        if idx == len(tspans) - 1:  # first tspan (we reversed)
                            result = result[:tm.start(2)] + safe_new_text + result[tm.end(2):]
                        else:
                            result = result[:tm.start(2)] + result[tm.end(2):]
                    return result
                else:
                    # No tspan — direct text inside <text> tag
                    return re.sub(
                        r'(>)([^<]+)(</text>)',
                        lambda m: m.group(1) + safe_new_text + m.group(3),
                        full_element,
                        count=1,
                    )
        return full_element

    content = re.sub(
        r'<text[^>]*>.*?</text>',
        replace_text_element,
        content,
        flags=re.DOTALL,
    )

    svg_dir = resolve_under(project, "svg_output")
    svg_dir.mkdir(parents=True, exist_ok=True)
    with open(resolve_under(svg_dir, f"page_{page_number:02d}.svg"), "w", encoding="utf-8") as f:
        f.write(sanitize_svg(content))
    return f"✅ Mirror page_{page_number:02d}.svg ({replaced_count} replacements)"


@function_tool
@_with_path_guards
def write_speaker_notes(project_path: str, content: str) -> str:
    """Write speaker notes to notes/total.md.

    Args:
        project_path: Project directory path.
        content: Full speaker notes in Markdown.
    """
    notes_dir = resolve_under(Path(project_path), "notes")
    notes_dir.mkdir(parents=True, exist_ok=True)
    resolve_under(notes_dir, "total.md").write_text(content, encoding="utf-8")
    return f"✅ 演讲稿 ({len(content)} chars)"


@function_tool
@_with_path_guards
def run_quality_check(project_path: str) -> str:
    """Run SVG quality checker.

    Args:
        project_path: Project directory path.
    """
    code, stdout, stderr = run_script("svg_quality_checker.py", [project_path])
    output = (stdout + stderr).strip()
    return output[:2000] if output else "✅ 质量检查通过"


# ═══════════════════════════════════════════════
# Media (formula, images, icons, charts)
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def write_formula_manifest(project_path: str, formulas_json: str) -> str:
    """Write formula_manifest.json.

    Args:
        project_path: Project directory path.
        formulas_json: JSON string containing formula manifest.
    """
    images_dir = resolve_under(Path(project_path), "images")
    images_dir.mkdir(parents=True, exist_ok=True)
    resolve_under(images_dir, "formula_manifest.json").write_text(formulas_json, encoding="utf-8")
    return "✅ formula_manifest.json"


@function_tool
@_with_path_guards
def render_latex_formulas(project_path: str) -> str:
    """Render LaTeX formulas to PNG.

    Args:
        project_path: Project directory path.
    """
    code, stdout, stderr = run_script("latex_render.py", [project_path])
    return (stdout + stderr)[:500] or ("✅ 公式渲染完成" if code == 0 else "❌ 渲染失败")


@function_tool
@_with_path_guards
def analyze_images(project_path: str) -> str:
    """Analyze images in project.

    Args:
        project_path: Project directory path.
    """
    images_dir = resolve_under(Path(project_path), "images")
    if not images_dir.exists():
        return "ℹ️ 无 images 目录"
    code, stdout, stderr = run_script("analyze_images.py", [str(images_dir)])
    return (stdout + stderr)[:1000]


@function_tool
@_with_path_guards
def write_image_prompts(project_path: str, prompts_json: str) -> str:
    """Write image_prompts.json for AI generation.

    Args:
        project_path: Project directory path.
        prompts_json: JSON string containing image prompts.
    """
    images_dir = resolve_under(Path(project_path), "images")
    images_dir.mkdir(parents=True, exist_ok=True)
    resolve_under(images_dir, "image_prompts.json").write_text(prompts_json, encoding="utf-8")
    return "✅ image_prompts.json"


@function_tool
@_with_path_guards
def generate_ai_images(project_path: str) -> str:
    """Generate AI images using manifest mode.

    Args:
        project_path: Project directory path.
    """
    manifest = resolve_under(Path(project_path), "images", "image_prompts.json")
    if not manifest.exists():
        return "❌ image_prompts.json 不存在"
    code, stdout, stderr = run_script("image_gen.py", ["--manifest", str(manifest)], timeout=300)
    result = (stdout + stderr)[:500]
    run_script("image_gen.py", ["--render-md", str(manifest)])
    return result or ("✅ 图片生成完成" if code == 0 else "❌ 生成失败")


@function_tool
def list_available_icons(keyword: str) -> str:
    """Search available icons.

    Args:
        keyword: Search keyword.
    """
    results = []
    if not ICONS_DIR.exists():
        return "❌ 图标库不存在"
    for lib_dir in ICONS_DIR.iterdir():
        if not lib_dir.is_dir():
            continue
        for icon_file in lib_dir.iterdir():
            if keyword.lower() in icon_file.stem.lower():
                results.append(f"{lib_dir.name}/{icon_file.name}")
                if len(results) >= 20:
                    break
    return "\n".join(results) if results else f"未找到 '{keyword}'"


@function_tool
def list_chart_templates(keyword: str) -> str:
    """Search chart/visualization templates.

    Args:
        keyword: Search keyword.
    """
    index_path = CHARTS_DIR / "charts_index.json"
    if not index_path.exists():
        return "❌ charts_index.json 不存在"
    with open(index_path, "r", encoding="utf-8") as f:
        charts = json.load(f)
    results = []
    for cid, info in charts.items():
        if keyword.lower() in cid.lower() or keyword.lower() in str(info).lower():
            results.append(f"- {cid}: {info.get('summary', '')[:80]}")
    return "\n".join(results[:15]) if results else f"未找到 '{keyword}'"


# ═══════════════════════════════════════════════
# Export & post-processing
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def run_post_processing(project_path: str, transition: str, animation: str, merge_paragraphs: bool) -> str:
    """Run full post-processing pipeline (split notes + finalize SVG + svg_to_pptx).

    Args:
        project_path: Project directory path.
        transition: Transition effect (fade/push/wipe/split/none).
        animation: Animation effect (auto/fade/none/mixed).
        merge_paragraphs: Whether to merge paragraphs for editability.
    """
    results = []
    code, stdout, stderr = run_script("total_md_split.py", [project_path])
    results.append(f"1️⃣ split notes: {'✅' if code == 0 else '⚠️'}")

    code, stdout, stderr = run_script("finalize_svg.py", [project_path])
    results.append(f"2️⃣ finalize SVG: {'✅' if code == 0 else '⚠️'} {(stdout+stderr).strip()[:100]}")

    pptx_args = [project_path, "-s", "final", "-t", transition, "-a", animation]
    if merge_paragraphs:
        pptx_args.append("--merge-paragraphs")
    code, stdout, stderr = run_script("svg_to_pptx.py", pptx_args)
    results.append(f"3️⃣ svg_to_pptx: {'✅' if code == 0 else '❌'} {(stdout+stderr).strip()[:200]}")

    # Verify a PPTX file was actually produced; fail loudly otherwise so the
    # job surfaces the error instead of silently completing without a deck.
    from pathlib import Path as _P
    exports = _P(project_path) / "exports"
    pptx_files = list(exports.glob("*.pptx")) if exports.exists() else []
    if code != 0 or not pptx_files:
        raise RuntimeError(
            "PPTX 导出失败 / PPTX export failed.\n" + "\n".join(results)
        )
    return "\n".join(results)


@function_tool
@_with_path_guards
def start_live_preview(project_path: str, port: int) -> str:
    """Start SVG live preview server.

    Args:
        project_path: Project directory path.
        port: Port number.
    """
    if _cfg.preview_process and _cfg.preview_process.poll() is None:
        return f"ℹ️ Live preview running http://localhost:{port}"
    script = SCRIPTS_DIR / "svg_editor" / "server.py"
    _cfg.preview_process = subprocess.Popen(
        [sys.executable, str(script), project_path, "--live", "--port", str(port)],
        cwd=str(PPT_MASTER_ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return f"✅ Live preview: http://localhost:{port}"


# ═══════════════════════════════════════════════
# Image web search
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def search_web_images(
    project_path: str, query: str, filename: str,
    orientation: str, slide: str, purpose: str,
) -> str:
    """Search openly-licensed web images and download best match.

    Args:
        project_path: Project directory path.
        query: Search query (2-5 keywords work best).
        filename: Local filename (e.g. cover_bg.jpg).
        orientation: Image orientation (landscape/portrait/square/any).
        slide: Slide identifier (e.g. 01_cover).
        purpose: Purpose tag (background/hero/side/icon).
    """
    images_dir = str(Path(project_path) / "images")
    args = [query, "--filename", filename, "-o", images_dir]
    if orientation and orientation != "any":
        args += ["--orientation", orientation]
    if slide:
        args += ["--slide", slide]
    if purpose:
        args += ["--purpose", purpose]
    code, stdout, stderr = run_script("image_search.py", args)
    result = (stdout + stderr).strip()
    return result[:500] or ("✅ 图片搜索完成" if code == 0 else "❌ 搜索失败")


# ═══════════════════════════════════════════════
# Chart verification
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def verify_chart_coordinates(
    project_path: str, chart_type: str, data: str,
    page_number: int, canvas: str, area: str,
) -> str:
    """Run svg_position_calculator to verify chart coordinates.

    Args:
        project_path: Project directory path.
        chart_type: Chart type (bar/line/pie/radar).
        data: Data string (e.g. "label1:value1,label2:value2").
        page_number: Page number containing the chart.
        canvas: Canvas format (ppt169/ppt43).
        area: Chart area bounds "x_min,y_min,x_max,y_max".
    """
    args = ["calc", chart_type, "--data", data, "--canvas", canvas]
    if area:
        args += ["--area", area]
    code, stdout, stderr = run_script("svg_position_calculator.py", args)
    result = (stdout + stderr).strip()
    if code == 0 and result:
        return f"✅ P{page_number:02d} {chart_type} 坐标:\n{result[:800]}"
    return f"⚠️ 计算失败: {result[:300]}"


# ═══════════════════════════════════════════════
# update_spec — batch color/font propagation
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def update_spec(project_path: str, changes: str) -> str:
    """Propagate color/font changes across spec_lock.md and all SVGs.

    Args:
        project_path: Project directory path.
        changes: Space-separated key=value pairs (e.g. "primary=#0066AA typography.font_family='PingFang SC'").
    """
    args = [project_path] + changes.split()
    code, stdout, stderr = run_script("update_spec.py", args)
    result = (stdout + stderr).strip()
    return result[:500] or ("✅ 配色/字体已更新" if code == 0 else f"❌ 更新失败: {result[:200]}")


# ═══════════════════════════════════════════════
# Recorded narration
# ═══════════════════════════════════════════════

@function_tool
@_with_path_guards
def generate_narration(project_path: str, voice: str, provider: str) -> str:
    """Generate per-slide narration audio from speaker notes.

    Args:
        project_path: Project directory path.
        voice: Voice name or ID (e.g. "zh-CN-XiaoxiaoNeural" for edge-tts).
        provider: TTS provider (edge/elevenlabs/minimax/qwen/cosyvoice).
    """
    args = [project_path, "--provider", provider]
    if provider == "edge":
        args += ["--voice", voice]
    else:
        args += ["--voice-id", voice]
    code, stdout, stderr = run_script("notes_to_audio.py", args)
    result = (stdout + stderr).strip()
    return result[:500] or ("✅ 语音生成完成" if code == 0 else f"❌ 语音生成失败: {result[:200]}")
