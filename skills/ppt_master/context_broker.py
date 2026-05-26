from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


TYPE_LABELS = {
    "cover": "封面页",
    "toc": "目录页",
    "chapter": "章节分隔页",
    "content": "内容页",
    "ending": "结尾页/致谢页",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _section(md: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\b.*?$", re.MULTILINE | re.IGNORECASE)
    match = pattern.search(md)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", md[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(md)
    return md[start:end].strip()


def _extract_hex_colors(text: str) -> list[str]:
    return sorted(set(re.findall(r"#[0-9A-Fa-f]{6}\b", text)))


def _parse_markdown_table(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")]
        if cells and all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _normalize_page_id(page_num: int) -> str:
    return f"P{page_num:02d}"


def _parse_page_sections(design_spec: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    matches = list(re.finditer(r"^###\s+(P\d{1,2})\s*[—\-:：]\s*(.+?)$", design_spec, re.MULTILINE))
    for idx, match in enumerate(matches):
        page_id = match.group(1).upper()
        title = match.group(2).strip()
        start = match.end()
        next_page = matches[idx + 1].start() if idx + 1 < len(matches) else len(design_spec)
        next_section = re.search(r"^##\s+", design_spec[start:], re.MULTILINE)
        section_end = start + next_section.start() if next_section else len(design_spec)
        end = min(next_page, section_end)
        body = design_spec[start:end].strip()
        result[page_id] = {"title": title, "brief": body[:1800]}
    return result


def _parse_page_rhythm(spec_lock: str) -> dict[str, dict[str, str]]:
    rows = _parse_markdown_table(_section(spec_lock, "page_rhythm"))
    result: dict[str, dict[str, str]] = {}
    for cells in rows[1:]:
        if len(cells) >= 3 and re.match(r"P\d+", cells[0], re.IGNORECASE):
            page_id = cells[0].upper()
            result[page_id] = {"title": cells[1], "rhythm": cells[2], "description": cells[3] if len(cells) > 3 else ""}
    return result


def _parse_page_layouts_rich(spec_lock: str) -> dict[str, dict[str, str]]:
    """Internal: returns {page_id: {template, description}} from Page Layouts table."""
    flat = parse_page_layouts_flat(spec_lock)
    rows = _parse_markdown_table(_section(spec_lock, "page_layouts"))
    result: dict[str, dict[str, str]] = {}
    for cells in rows[1:]:
        if len(cells) >= 2 and re.match(r"P\d+", cells[0], re.IGNORECASE):
            page_id = cells[0].upper()
            tpl = flat.get(page_id, cells[1].replace("`", "").strip())
            result[page_id] = {"template": tpl, "description": cells[2] if len(cells) > 2 else ""}
    # Also include entries only found in list format
    for pid, tpl in flat.items():
        if pid not in result:
            result[pid] = {"template": tpl, "description": ""}
    return result


def parse_page_layouts_flat(spec_lock: str) -> dict[str, str]:
    """Parse page_layouts from spec_lock → {page_id: template_basename}.

    Supports multiple formats:
      List:  - P01: 001_cover
      Table: | P01 | 封面：... | `001_cover` | Cover | anchor |
    Strips backticks, .svg suffix; scans all table columns.
    """
    layouts: dict[str, str] = {}
    section = _section(spec_lock, "page_layouts") or _section(spec_lock, "Page Layouts")
    text = section if section else spec_lock
    for line in text.split("\n"):
        stripped = line.strip()
        # List format: - P01: 001_cover
        m = re.match(r"-\s*(P\d+):\s*(.+)", stripped)
        if m:
            raw_val = m.group(2).strip().replace(".svg", "").replace("`", "").split("|")[0].strip()
            tpl_match = re.search(r"\b(\d{2,3}_\w+)\b", raw_val)
            if tpl_match:
                layouts[m.group(1).upper()] = tpl_match.group(1)
            continue
        # Table format: | P01 | ... | 001_cover_candidate | ... |
        if "|" in stripped:
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cells) >= 2:
                page_m = re.match(r"(P\d+)", cells[0], re.IGNORECASE)
                if page_m:
                    for cell in cells[1:]:
                        clean = cell.replace("`", "").replace(".svg", "").strip()
                        tpl_match = re.search(r"\b(\d{2,3}_\w+)\b", clean)
                        if tpl_match:
                            layouts[page_m.group(1).upper()] = tpl_match.group(1)
                            break
    return layouts


def _parse_page_charts(spec_lock: str) -> dict[str, str]:
    section = _section(spec_lock, "page_charts")
    result: dict[str, str] = {}
    matches = list(re.finditer(r"^###\s+(P\d{1,2})\b.*?$", section, re.MULTILINE))
    for idx, match in enumerate(matches):
        page_id = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section)
        result[page_id] = section[start:end].strip()[:1200]
    return result


def _infer_type(template: str) -> str:
    cleaned = template.replace("_candidate", "")
    match = re.match(r"\d{2,3}[a-z]?_(.+)", cleaned)
    if not match:
        return "content"
    role = match.group(1)
    for key in TYPE_LABELS:
        if key in role:
            return key
    return role


def _resolve_template(project_path: str | Path, template_basename: str) -> Path | None:
    tpl_dir = Path(project_path) / "templates"
    candidates = [template_basename, template_basename.replace("_candidate", "")]
    for name in candidates:
        path = tpl_dir / f"{name}.svg"
        if path.exists():
            return path
    for name in candidates:
        matches = sorted(tpl_dir.glob(f"*{name}*.svg"))
        if matches:
            return matches[0]
    return None


def get_project_summary(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path)
    spec_lock = _read(project / "spec_lock.md")
    design_spec = _read(project / "design_spec.md")
    layouts = _parse_page_layouts_rich(spec_lock)
    rhythms = _parse_page_rhythm(spec_lock)
    pages = _parse_page_sections(design_spec)
    types: dict[str, int] = {}
    for item in layouts.values():
        page_type = _infer_type(item["template"])
        types[page_type] = types.get(page_type, 0) + 1
    return {
        "project_path": str(project),
        "mode": "mirror" if "mirror" in (spec_lock + design_spec).lower() else "standard",
        "pages": len(pages) or len(layouts) or len(rhythms),
        "template_type_counts": {TYPE_LABELS.get(k, k): v for k, v in sorted(types.items())},
        "colors": _extract_hex_colors(_section(spec_lock, "colors")),
    }


def get_page_context(project_path: str | Path, page_num: int) -> dict[str, Any]:
    project = Path(project_path)
    spec_lock = _read(project / "spec_lock.md")
    design_spec = _read(project / "design_spec.md")
    page_id = _normalize_page_id(page_num)
    pages = _parse_page_sections(design_spec)
    rhythms = _parse_page_rhythm(spec_lock)
    layouts = _parse_page_layouts_rich(spec_lock)
    charts = _parse_page_charts(spec_lock)
    layout = layouts.get(page_id, {})
    template = layout.get("template", "")
    page_type = _infer_type(template) if template else "content"
    template_path = _resolve_template(project, template) if template else None
    return {
        "page_id": page_id,
        "page_num": page_num,
        "title": pages.get(page_id, {}).get("title") or rhythms.get(page_id, {}).get("title", ""),
        "brief": pages.get(page_id, {}).get("brief", ""),
        "rhythm": rhythms.get(page_id, {}).get("rhythm", ""),
        "layout": template.replace("_candidate", ""),
        "layout_original": template,
        "page_type": page_type,
        "page_type_label": TYPE_LABELS.get(page_type, page_type),
        "layout_description": layout.get("description", ""),
        "template_exists": bool(template_path),
        "template_file": template_path.name if template_path else "",
        "colors": _extract_hex_colors(_section(spec_lock, "colors")),
        "typography": _parse_markdown_table(_section(spec_lock, "typography"))[:6],
        "icons": [m.group(1) for m in re.finditer(r"`([^`]+)`", _section(spec_lock, "icons"))][:20],
        "charts": charts.get(page_id, ""),
        "forbidden": [line.strip("- 0123456789.、") for line in _section(spec_lock, "forbidden").splitlines() if line.strip()][:12],
    }


def get_template_text_map(project_path: str | Path, template_basename: str) -> dict[str, Any]:
    path = _resolve_template(project_path, template_basename)
    if not path:
        return {"template": template_basename, "exists": False, "editable_texts": []}
    text = path.read_text(encoding="utf-8", errors="ignore")
    editable: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(text)
        for idx, el in enumerate(root.iter()):
            tag = str(el.tag).split("}")[-1]
            if tag != "text":
                continue
            visible = "".join(el.itertext()).strip()
            visible = re.sub(r"\s+", " ", visible)
            if visible:
                editable.append({"index": len(editable), "text": visible[:220]})
    except Exception:
        for match in re.finditer(r"<text[^>]*>(.*?)</text>", text, re.DOTALL | re.IGNORECASE):
            visible = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            visible = re.sub(r"\s+", " ", visible)
            if visible:
                editable.append({"index": len(editable), "text": visible[:220]})
    return {
        "template": template_basename.replace("_candidate", ""),
        "template_original": template_basename,
        "exists": True,
        "file": path.name,
        "size_chars": len(text),
        "page_type": _infer_type(path.stem),
        "editable_text_count": len(editable),
        "editable_texts": editable[:40],
    }


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
