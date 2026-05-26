"""Template listing, custom upload/delete."""
from __future__ import annotations

import asyncio
import json as _json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from routes.deps import (
    BRANDS_DIR, CUSTOM_TEMPLATES_DIR, DECKS_DIR, LAYOUTS_DIR,
    MAX_UPLOAD_BYTES, SafetyError, log,
    resolve_under, safe_filename, sanitize_svg,
)

router = APIRouter()

# ── Display names ──

TEMPLATE_CN_NAMES = {
    "academic_defense": "学术答辩",
    "ai_ops": "AI 智能运维",
    "government_blue": "政务蓝",
    "government_red": "党政红",
    "medical_university": "医学学术",
    "pixel_retro": "像素复古",
    "psychology_attachment": "心理学讲座",
}

TEMPLATE_CN_SUMMARIES = {
    "academic_defense": "学术答辩、毕业论文、研究汇报",
    "ai_ops": "AI 运维方案、智能监控、自动化运维",
    "government_blue": "重点项目汇报、政策解读、工作总结",
    "government_red": "政府简报、党建汇报、工作总结",
    "medical_university": "医学学术报告、病例讨论、科研汇报",
    "pixel_retro": "技术分享、编程教程、极客风展示",
    "psychology_attachment": "心理治疗培训、学术讲座、咨询分析",
}

# ── Helpers ──

_ENDING_KW = ("thank", "thanks", "q&a", "qa", "contact", "致谢", "谢谢", "感谢", "答疑", "联系方式", "end")
_TOC_KW = ("agenda", "contents", "content", "outline", "目录", "议程", "目录页", "大纲")
_CHAPTER_KW = ("chapter", "part", "section", "章节", "部分", "篇")


def _classify_svg_page(svg_path: Path, index: int, total: int) -> str:
    try:
        tree = ET.parse(str(svg_path))
        root = tree.getroot()
        ns = {"svg": "http://www.w3.org/2000/svg"}
        texts = []
        for el in root.iter():
            tag = el.tag.split("}")[-1] if "}" in str(el.tag) else str(el.tag)
            if tag in ("text", "tspan") and el.text:
                texts.append(el.text.strip())
        joined = " ".join(texts).lower()
        text_count = len(texts)
        shape_count = len(list(root))
    except Exception:
        joined, text_count, shape_count = "", 0, 0

    if any(kw in joined for kw in _ENDING_KW):
        return "ending"
    if any(kw in joined for kw in _TOC_KW):
        return "toc"
    if any(kw in joined for kw in _CHAPTER_KW):
        return "chapter"
    if index == 0:
        return "cover"
    if index == total - 1 and text_count <= 6:
        return "ending"
    if text_count <= 3 and shape_count <= 12:
        return "chapter"
    return "content"


def _list_templates_from_dir(base_dir: Path, kind: str) -> list[dict]:
    templates = []
    if not base_dir.exists():
        return templates
    for d in sorted(base_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        cover_file = d / "01_cover.svg"
        cover_name = "01_cover.svg"
        if not cover_file.exists():
            for candidate in sorted(d.glob("*cover*.svg")):
                cover_file = candidate
                cover_name = candidate.name
                break
        if not cover_file.exists():
            for candidate in sorted(d.glob("*.svg")):
                cover_file = candidate
                cover_name = candidate.name
                break
        cover_url = f"/static/templates/{kind}/{d.name}/{cover_name}" if cover_file.exists() else ""
        templates.append({
            "id": f"{kind}_{d.name}",
            "kind": kind,
            "name": TEMPLATE_CN_NAMES.get(d.name, d.name),
            "summary": TEMPLATE_CN_SUMMARIES.get(d.name, f"{kind} 模板"),
            "cover_url": cover_url,
        })
    return templates


# ── Routes ──

@router.get("/api/templates")
async def get_templates():
    """List all available templates."""
    templates = []
    templates.extend(_list_templates_from_dir(LAYOUTS_DIR, "layouts"))
    templates.extend(_list_templates_from_dir(BRANDS_DIR, "brands"))
    templates.extend(_list_templates_from_dir(DECKS_DIR, "decks"))
    for d in sorted(CUSTOM_TEMPLATES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            cover_file = d / "01_cover.svg"
            cover_url = f"/static/custom_templates/{d.name}/01_cover.svg" if cover_file.exists() else ""
            templates.append({
                "id": f"custom_{d.name}",
                "kind": "custom",
                "summary": "用户自定义模板",
                "name": d.name,
                "cover_url": cover_url,
            })
    return JSONResponse({"templates": templates, "total": len(templates)})


@router.post("/api/templates/custom/upload")
async def upload_custom_template(file: UploadFile = File(...)):
    """Upload a custom PPTX template → convert to SVG."""
    from skills.ppt_master.config import SCRIPTS_DIR

    filename = safe_filename(file.filename, "custom_template.pptx")
    stem = Path(filename).stem
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in stem)[:30]

    tpl_dir = CUSTOM_TEMPLATES_DIR / safe_name
    if tpl_dir.exists():
        shutil.rmtree(tpl_dir)
    tpl_dir.mkdir(parents=True, exist_ok=True)

    file_path = resolve_under(tpl_dir, filename)
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        shutil.rmtree(tpl_dir, ignore_errors=True)
        return JSONResponse({"error": "文件过大，最大支持 50MB"}, status_code=413)
    file_path.write_bytes(content)

    # Convert PPTX → SVG
    import_script = str(SCRIPTS_DIR / "pptx_template_import.py")
    import_output_dir = tpl_dir / "import_workspace"
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, import_script, str(file_path),
             "-o", str(import_output_dir), "--embed-images"],
            capture_output=True, text=True, timeout=180,
            cwd=str(SCRIPTS_DIR),
        )
        log.info("pptx_template_import exit=%d", result.returncode)
    except Exception as e:
        log.warning("pptx_template_import failed: %s, fallback to pptx_to_svg", e)
        pptx_to_svg_script = str(SCRIPTS_DIR / "pptx_to_svg.py")
        await asyncio.to_thread(
            subprocess.run,
            [sys.executable, pptx_to_svg_script, str(file_path),
             "-o", str(import_output_dir), "--embed-images"],
            capture_output=True, text=True, timeout=120,
        )

    # Collect SVG files
    flat_dir = import_output_dir / "svg-flat"
    if not flat_dir.exists():
        flat_dir = import_output_dir / "svg"
    if not flat_dir or not flat_dir.exists():
        return JSONResponse({"error": "SVG 转换失败"}, status_code=500)

    svg_files = sorted(flat_dir.glob("*.svg"))
    manifest = {}
    manifest_path = import_output_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    slide_meta = manifest.get("slides", [])
    page_roster = []
    for i, svg_file in enumerate(svg_files):
        page_type = "content"
        if i < len(slide_meta):
            raw = slide_meta[i].get("pageType", "content_candidate")
            page_type = raw.replace("_candidate", "")
        else:
            page_type = _classify_svg_page(svg_file, i, len(svg_files))
        dst_name = f"{i+1:03d}_{page_type}.svg"
        (tpl_dir / dst_name).write_text(
            sanitize_svg(svg_file.read_text(encoding="utf-8", errors="ignore")),
            encoding="utf-8",
        )
        page_roster.append({"idx": i + 1, "filename": dst_name, "type": page_type})
    log.info("Template page roster: %s", [(r["idx"], r["type"]) for r in page_roster])

    first_svg = tpl_dir / page_roster[0]["filename"] if page_roster else None
    cover_path = tpl_dir / "01_cover.svg"
    if first_svg and first_svg.exists() and not cover_path.exists():
        cover_path.write_text(
            sanitize_svg(first_svg.read_text(encoding="utf-8", errors="ignore")),
            encoding="utf-8",
        )

    return JSONResponse({
        "id": f"custom_{safe_name}",
        "name": safe_name,
        "filename": filename,
        "size": len(content),
        "pages": len(page_roster),
        "replication_mode": "mirror",
    })


@router.delete("/api/templates/custom/{template_id:path}")
async def delete_custom_template(template_id: str):
    """Delete a custom template."""
    raw_name = template_id.replace("custom_", "", 1) if template_id.startswith("custom_") else template_id
    # Reject path traversal without re-sanitizing (safe_filename strips leading _ which breaks lookup)
    if not raw_name or "/" in raw_name or "\\" in raw_name or ".." in raw_name:
        return JSONResponse({"error": "Invalid template id"}, status_code=400)
    try:
        tpl_dir = resolve_under(CUSTOM_TEMPLATES_DIR, raw_name)
    except SafetyError:
        return JSONResponse({"error": "Invalid template id"}, status_code=400)
    if tpl_dir.exists():
        shutil.rmtree(tpl_dir, ignore_errors=True)
    return JSONResponse({"status": "ok"})
