"""Full agent definitions for PPT Master skill.

Agent instructions are loaded directly from ppt-master's references/ directory
so we always use the original, authoritative rules.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agents import Agent

from skills.ppt_master.config import MODEL, SKILL_DIR
from skills.ppt_master.tools import (
    convert_source_to_markdown,
    web_fetch_to_markdown, save_research_document,
    init_project, import_source_to_project, validate_project,
    write_design_spec, write_spec_lock, read_spec_lock,
    write_formula_manifest, render_latex_formulas, analyze_images,
    write_image_prompts, generate_ai_images, search_web_images,
    write_svg_page, run_quality_check, write_speaker_notes,
    get_page_design_context,
    list_available_icons, list_chart_templates,
    verify_chart_coordinates,
    run_post_processing, start_live_preview,
    update_spec, generate_narration,
)

log = logging.getLogger(__name__)

REFS_DIR = SKILL_DIR / "references"


def _load_ref(*filenames: str, max_chars: int = 12000) -> str:
    """Load one or more reference .md files from ppt-master, concatenated.

    Truncates to max_chars to stay within context limits.
    Falls back to empty string if file not found.
    """
    parts = []
    for fn in filenames:
        p = REFS_DIR / fn
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
        else:
            log.warning("Reference file not found: %s", p)
    combined = "\n\n---\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n... (truncated)"
    return combined

# ═══════════════════════════════════════════════
# Step 1: Source Processing
# ═══════════════════════════════════════════════

source_agent = Agent(
    name="SourceAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的源文件处理 Agent。\n"
        "使用 convert_source_to_markdown 工具将用户提供的文件转换为 Markdown。\n"
        "支持: PDF, DOCX, XLSX, PPTX, URL, HTML, EPUB 等所有格式。"
    ),
    tools=[convert_source_to_markdown],
)

# ═══════════════════════════════════════════════
# Step 1b: Topic Research (when no source file)
# ═══════════════════════════════════════════════

research_agent = Agent(
    name="ResearchAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的话题调研 Agent。当用户只给出话题/主题而没有源文件时，你负责：\n\n"
        "1. 分析话题，确定需要搜集的子主题（概述、背景、核心要点、应用/案例、展望）\n"
        "2. 使用 web_fetch_to_markdown 抓取 2-4 个权威网页获取素材\n"
        "   - 优先: 维基百科、官方网站、学术/机构发布\n"
        "3. 整合所有素材，用 save_research_document 保存为结构化 Markdown\n\n"
        "文档结构要求:\n"
        "- 按话题自然组织章节\n"
        "- 内容要具体：日期、名称、数据、引用\n"
        "- 末尾必须有 ## Sources 列出所有参考 URL\n"
        "- 内容密度要足以支撑 8-15 页 PPT\n\n"
        "输出: 调用 save_research_document 保存完整文档，最后返回文档摘要。"
    ),
    tools=[web_fetch_to_markdown, save_research_document],
)

# ═══════════════════════════════════════════════
# Step 2: Project Init
# ═══════════════════════════════════════════════

project_agent = Agent(
    name="ProjectAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的项目管理 Agent。\n"
        "使用 init_project 创建项目，import_source_to_project 导入源文件。"
    ),
    tools=[init_project, import_source_to_project, validate_project],
)

# ═══════════════════════════════════════════════
# Step 4: Strategist (Eight Confirmations)
# ═══════════════════════════════════════════════

strategist_agent = Agent(
    name="StrategistAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的设计策略师 (Strategist)。用中文回复。\n\n"
        + _load_ref("strategist.md", max_chars=10000)
    ),
    tools=[],
)

# ═══════════════════════════════════════════════
# Step 4b: Spec Generator
# ═══════════════════════════════════════════════

spec_generator_agent = Agent(
    name="SpecGeneratorAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的设计文档生成 Agent。\n\n"
        "根据确认的设计方案，生成两份文档：\n\n"
        "1. **design_spec.md** — 完整设计规格\n"
        "2. **spec_lock.md** — 执行锁定文件，必须包含：\n"
        "   canvas, colors, typography, icons, images,\n"
        "   page_rhythm, page_layouts (有模板时), page_charts, forbidden\n\n"
        "page_rhythm 规则：\n"
        "- anchor: 结构页（封面/章节/目录/结尾）\n"
        "- dense: 信息密集页（数据、对比、列表）\n"
        "- breathing: 低密度冲击页（每 2-3 个 dense 后放 1 个）\n\n"
        "关键要求：\n"
        "- 内容大纲必须忠实覆盖源文件所有章节和核心概念\n"
        "- 每页的要点必须从源文件中提取\n"
        "- 至少 10 页\n\n"
        "使用 write_design_spec 和 write_spec_lock 工具写入文件。"
    ),
    tools=[write_design_spec, write_spec_lock, write_formula_manifest, render_latex_formulas, analyze_images],
)

# ═══════════════════════════════════════════════
# Step 5: Image Acquisition
# ═══════════════════════════════════════════════

image_agent = Agent(
    name="ImageAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的图片获取 Agent。\n\n"
        "检查 design_spec.md 中的图片资源列表，对 Status: Pending 的项目：\n"
        "- Acquire Via: ai → 写 image_prompts.json，调用 generate_ai_images\n"
        "- Acquire Via: web → 调用 search_web_images 搜索开源图片\n"
        "- Acquire Via: user/placeholder → 跳过\n"
        "- Acquire Via: formula → 已在 spec 阶段处理\n\n"
        "web 搜索参数：query=关键词, filename=文件名, orientation=方向, slide=页码标识, purpose=用途\n\n"
        "处理完后调用 analyze_images 验证。"
    ),
    tools=[write_image_prompts, generate_ai_images, search_web_images, analyze_images],
)

# ═══════════════════════════════════════════════
# Step 6: Page Worker (General Style)
# ═══════════════════════════════════════════════

# Load executor-general style reference
_GENERAL_STYLE = _load_ref("executor-general.md", "executor-base.md", max_chars=8000)

page_worker_standard = Agent(
    name="PageWorkerGeneral",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master General 风格页面生成器。你的任务是从零生成完整、专业的 SVG 页面。\n\n"
        "## 核心工作流\n"
        "1. 根据提供的页面上下文（类型、节奏、色彩、内容要点）生成完整 SVG\n"
        "2. 调用 write_svg_page 写入\n\n"
        "## SVG 硬性规范\n"
        "- viewBox: 严格按 canvas 信息（如 \"0 0 1280 720\"）\n"
        "- 所有文字必须使用 <text>/<tspan>，禁止 <foreignObject>\n"
        "- 禁止外部图片链接，禁止 <script>\n"
        "- font-family 末尾必须有系统预装字体兜底（Microsoft YaHei / SimHei / Arial）\n"
        "- 仅使用给定色彩方案中的颜色\n\n"
        "## General 风格要求\n"
        "- **布局多样**: 不要每页都用卡片网格。封面用全屏背景+标题覆盖、内容用左右分栏/三列卡片/上下拆分/中心辐射等\n"
        "- **节奏控制**: 遵守 page_rhythm — anchor(结构页)严格、dense(密集信息)、breathing(留白冲击)\n"
        "  - breathing 页禁止多卡片网格，使用大字/引用/全幅图/单数字+解读\n"
        "  - 每 2-3 个 dense 后应有 1 个 breathing 页\n"
        "- **装饰适度**: 渐变块、圆角卡片、图标点缀、编号圆圈、分割线——服务内容不喧宾夺主\n"
        "- **主题色大胆使用**: 封面/章节页可大面积使用主题色背景\n"
        "- **视觉层次**: Title→Subtitle→Body→Annotation 四层字号递减\n"
        "- **跨页一致**: 参考已完成页面设计概览，保持视觉连贯，避免重复布局\n\n"
        "## 图标\n"
        "- 使用 <use data-icon=\"library/name\" ...> 占位，finalize_svg 会自动嵌入\n"
        "- 始终 fill=\"#HEX\"，禁止 fill=\"none\" 或 stroke\n"
        "- 如需查找可用图标，调用 list_available_icons\n\n"
        "如需更多设计细节，调用 get_page_design_context。\n"
    ),
    tools=[write_svg_page, get_page_design_context, list_available_icons, list_chart_templates],
)

# Legacy alias for backward compatibility
executor_agent = page_worker_standard

# ═══════════════════════════════════════════════
# Step 6d: Notes Writer
# ═══════════════════════════════════════════════

notes_agent = Agent(
    name="NotesWriter",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是演讲稿撰写专家。根据 PPT 页面列表，为每页写 2-3 句自然口语化的演讲稿。\n\n"
        "格式:\n"
        "## 第1页 · <标题>\n\n<演讲内容>\n\n---\n\n## 第2页 · ...\n\n"
        "写完后调用 write_speaker_notes 保存。"
    ),
    tools=[write_speaker_notes],
)

# ═══════════════════════════════════════════════
# Step 7: Export
# ═══════════════════════════════════════════════

export_agent = Agent(
    name="ExportAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的导出 Agent。\n\n"
        "调用 run_post_processing 执行后处理流水线：\n"
        "1. total_md_split — 拆分演讲稿\n"
        "2. finalize_svg — SVG 后处理\n"
        "3. svg_to_pptx — DrawingML 原生转换\n\n"
        "可选能力：\n"
        "- update_spec: 批量修改配色/字体并传播到所有 SVG\n"
        "- generate_narration: 生成每页语音旁白（需指定 voice 和 provider）\n\n"
        "返回最终 PPTX 文件路径。"
    ),
    tools=[run_post_processing, update_spec, generate_narration],
)

# ═══════════════════════════════════════════════
# Chart verification agent
# ═══════════════════════════════════════════════

chart_verify_agent = Agent(
    name="ChartVerifyAgent",
    model=MODEL,  # type: ignore[arg-type]
    instructions=(
        "你是 PPT Master 的图表坐标校验 Agent。\n\n"
        "对包含数据图表的页面，使用 verify_chart_coordinates 计算正确坐标。\n"
        "支持: bar(柱状图), line(折线/散点), pie(饼/环), radar(雷达)\n\n"
        "参数说明：\n"
        "- chart_type: bar/line/pie/radar\n"
        "- data: \"label1:value1,label2:value2\" 格式\n"
        "- canvas: ppt169 或 ppt43\n"
        "- area: 图表区域 \"x_min,y_min,x_max,y_max\"\n\n"
        "如果计算结果与 SVG 中实际坐标有偏差(>5px)，使用 write_svg_page 修复该页。"
    ),
    tools=[verify_chart_coordinates, write_svg_page, get_page_design_context],
)
