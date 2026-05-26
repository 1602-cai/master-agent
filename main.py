#!/usr/bin/env python3
"""CLI entry point for Agent Harness."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


def _build_runtime():
    from harness.jobs import JobStore
    from harness.runtime import HarnessRuntime
    from harness.skill_loader import load_skills_from_dir

    registry = load_skills_from_dir(Path(__file__).parent / "skills")
    job_store = JobStore(DATA_DIR)
    return HarnessRuntime(registry, job_store)


async def run_cli(user_input: str, files: list[str] | None = None, skill: str = "ppt-master") -> None:
    runtime = _build_runtime()

    print(f"\n{'='*60}")
    print(f"  Agent Harness — Full Pipeline")
    print(f"  Skill: {skill}")
    print(f"  Input: {user_input[:80]}")
    if files:
        print(f"  Files: {files}")
    print(f"{'='*60}\n")

    # Inject files into initial state
    initial_state = {}
    if files:
        initial_state["files"] = files

    # Phase 1: start job (Steps 1-4, pauses at confirmation)
    job_id = await runtime.start_job(skill, user_input, initial_state=initial_state)
    job = runtime.get_job(job_id)

    print(f"  Job ID: {job_id}")
    print(f"  Status: {job['status']}")

    if job["status"] == "waiting_for_user":
        # Show eight confirmations
        job_dir = DATA_DIR / "jobs" / job_id / "artifacts"
        conf_path = job_dir / "eight_confirmations.md"
        if conf_path.exists():
            print(f"\n{'─'*60}")
            print("  八项确认 (设计方案):")
            print(f"{'─'*60}")
            content = conf_path.read_text(encoding="utf-8")
            # Show first 2000 chars
            print(content[:2000])
            if len(content) > 2000:
                print("  ... (truncated)")
            print(f"{'─'*60}\n")

        # Wait for confirmation
        response = input("  请输入确认或修改意见 (直接回车=确认): ").strip()
        if not response:
            response = "确认"

        print(f"\n  用户回复: {response}")
        print(f"  恢复执行 (Steps 4b-7)...\n")

        # Phase 2: resume (Steps 4b-7)
        await runtime.resume_job(job_id, response)

    # Final status
    job = runtime.get_job(job_id)
    print(f"\n{'='*60}")
    print(f"  最终状态: {job['status']}")

    if job["status"] == "completed":
        artifacts = job.get("artifacts", [])
        print(f"  产出 ({len(artifacts)} 个):")
        for a in artifacts:
            size_str = f"{a.get('size', 0)} bytes" if a.get('size') else ""
            print(f"    - {a['path']} ({a.get('type', 'file')}) {size_str}")
        print(f"\n  Artifacts: data/jobs/{job_id}/artifacts/")
        print(f"  Project:   data/jobs/{job_id}/project/")
    elif job["status"] == "failed":
        print(f"  错误: {job.get('error', 'unknown')}")

    # Show events summary
    events = runtime.get_events(job_id)
    print(f"\n  事件记录 ({len(events)} 条):")
    for ev in events:
        etype = ev['type']
        msg = ev.get('message', '')
        payload = ev.get('payload', {})
        if etype == "page_generating":
            print(f"    [page] {payload.get('page', '?')}/{payload.get('total', '?')} {payload.get('title', '')}")
        elif msg:
            print(f"    [{etype}] {msg}")
        else:
            print(f"    [{etype}]")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Agent Harness CLI")
    parser.add_argument("input", nargs="*", help="User input / topic")
    parser.add_argument("--file", "-f", action="append", default=[], help="Source files (PDF/DOCX/URL)")
    parser.add_argument("--skill", "-s", default="ppt-master", help="Skill name")
    args = parser.parse_args()

    if not args.input and not args.file:
        parser.print_help()
        print("\nExamples:")
        print('  python main.py "帮我做一个PPT：商业银行并购管理"')
        print('  python main.py "AI发展趋势" --file report.pdf')
        print('  python main.py "产品介绍" --file https://example.com/product')
        sys.exit(1)

    user_input = " ".join(args.input) if args.input else f"基于以下文件生成PPT: {', '.join(args.file)}"
    asyncio.run(run_cli(user_input, files=args.file or None, skill=args.skill))


if __name__ == "__main__":
    main()
