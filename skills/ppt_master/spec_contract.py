from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def build_spec_contract(design_spec: str, spec_lock: str) -> dict[str, Any]:
    pages = _parse_pages_from_design_spec(design_spec) or _parse_pages_from_spec_lock(spec_lock)
    errors: list[str] = []
    warnings: list[str] = []

    if not pages:
        errors.append("design_spec/spec_lock 中没有可解析的页面结构")

    seen: set[int] = set()
    for page in pages:
        num = int(page.get("num", 0) or 0)
        if num <= 0:
            errors.append(f"非法页码: {num}")
        if num in seen:
            errors.append(f"重复页码: P{num:02d}")
        seen.add(num)

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "version": 1,
        "mode": "standard",
        "pages": sorted(pages, key=lambda p: int(p["num"])),
        "warnings": warnings,
    }


def save_spec_contract(project_path: str | Path, contract: dict[str, Any]) -> Path:
    path = Path(project_path) / "spec_contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse_pages_from_design_spec(design_spec: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    seen_nums: set[int] = set()

    # Strategy 1: Heading format — ### Page 1: 封面 / ### 第 1 页: 封面
    # Require "Page", "P", or "第" prefix to avoid matching section headers like "## 1. 文档概览"
    heading_re = re.compile(
        r"^#{2,3}\s*(?:Page|P|第)\s*(\d+)\s*(?:页)?\s*[：:．.\-—\s]+(.+?)$",
        re.MULTILINE | re.IGNORECASE,
    )
    matches = list(heading_re.finditer(design_spec))
    for idx, match in enumerate(matches):
        num = int(match.group(1))
        if num in seen_nums:
            continue
        seen_nums.add(num)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(design_spec)
        body = design_spec[start:end].strip()
        bullets = [line.strip()[2:].strip() for line in body.splitlines() if line.strip().startswith("- ")]
        pages.append({"num": num, "title": match.group(2).strip(), "brief": "\n".join(bullets[:6]) or body[:500]})

    if pages:
        return pages

    # Strategy 2: Table format — multiple column variations:
    #   | 1 | 封面 | anchor | **title** | brief |
    #   | 1 | 封面 | **anchor** | 结构锚点 — 开场 |
    # Common when LLM puts the page outline in a markdown table
    table_re = re.compile(
        r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*\*{0,2}(?:anchor|dense|breathing|[a-z_]+)\*{0,2}\s*\|([^|]*)\|",
        re.MULTILINE,
    )
    for match in table_re.finditer(design_spec):
        num = int(match.group(1))
        if num in seen_nums:
            continue
        seen_nums.add(num)
        page_type = re.sub(r"[*`]", "", match.group(2)).strip()
        col4 = re.sub(r"[*`]", "", match.group(3)).strip()
        title = page_type  # Column 2 is the actual page title (封面/目录/etc)
        # Get the rest of the row as additional brief
        row_end = design_spec.find("\n", match.end())
        row_tail = design_spec[match.end():row_end].strip() if row_end > 0 else ""
        brief_parts = [col4, re.sub(r"[|*`]", "", row_tail).strip()]
        brief = " — ".join(p for p in brief_parts if p)[:300]
        pages.append({"num": num, "title": title, "brief": brief})

    return pages


def _parse_pages_from_spec_lock(spec_lock: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    seen: set[int] = set()
    for line in spec_lock.splitlines():
        stripped = line.strip()
        table_match = re.match(r"^\|\s*P(\d+)\s*\|\s*([^|]+)", stripped, re.IGNORECASE)
        list_match = re.match(r"^-\s*P(\d+)\s*[:：-]\s*(.+)$", stripped, re.IGNORECASE)
        match = table_match or list_match
        if not match:
            continue
        num = int(match.group(1))
        if num in seen:
            continue
        seen.add(num)
        title = re.sub(r"[`*_]", "", match.group(2)).strip()
        if title and not re.fullmatch(r"[-: ]+", title):
            pages.append({"num": num, "title": title[:120], "brief": ""})
    return pages
