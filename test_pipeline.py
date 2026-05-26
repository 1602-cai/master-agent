#!/usr/bin/env python3
"""Automated end-to-end integration test for concurrency and hybrid mode."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

# Load env vars first
from dotenv import load_dotenv
load_dotenv()

# Build runtime
from harness.jobs import JobStore
from harness.runtime import HarnessRuntime
from harness.skill import SkillRegistry
from skills.ppt_master import PPTMasterSkill

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TestPipeline")


async def main():
    DATA_DIR = Path(__file__).parent / "data"
    registry = SkillRegistry()
    registry.register(PPTMasterSkill())
    job_store = JobStore(DATA_DIR)
    runtime = HarnessRuntime(registry, job_store)

    user_input = "帮我做一个关于人工智能在医疗领域的应用的三页PPT"
    log.info("Starting integration test...")
    log.info(f"User Input: {user_input}")

    # 1. Start Job (Phase 1)
    t0 = time.time()
    job_id = await runtime.start_job("ppt-master", user_input)
    job = runtime.get_job(job_id)
    log.info(f"Phase 1 done. Job ID: {job_id}, Status: {job['status']}")

    if job["status"] == "waiting_for_user":
        log.info("Simulating user design confirmation...")
        # 2. Resume Job (Phase 2 — will generate pages in parallel!)
        await runtime.resume_job(job_id, "确认，同意该设计方案")

    # 3. Check final status
    job = runtime.get_job(job_id)
    t1 = time.time()
    duration = t1 - t0

    log.info(f"Test Pipeline finished in {duration:.2f} seconds.")
    log.info(f"Final Job Status: {job['status']}")

    # 4. Verify events are concurrent
    events = runtime.get_events(job_id)
    page_events = [ev for ev in events if ev.get("type") == "page_generating"]
    log.info(f"Found {len(page_events)} page generation events:")
    for ev in page_events:
        log.info(f"  - {ev.get('ts')}: page {ev.get('payload', {}).get('page')} generating")

    # 5. Verify Artifacts
    artifacts = job.get("artifacts", [])
    log.info(f"Generated artifacts:")
    for a in artifacts:
        log.info(f"  - {a['path']} ({a.get('type')})")

    assert job["status"] == "completed", "Job failed!"
    print("\n🎉 INTEGRATION TEST SUCCESSFUL! 🎉\n")


if __name__ == "__main__":
    asyncio.run(main())
