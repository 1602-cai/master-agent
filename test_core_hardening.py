from __future__ import annotations

import tempfile
import asyncio
import contextlib
import logging
from pathlib import Path

from harness.artifacts import ArtifactManager
from harness.events import Event, EventWriter
from harness.jobs import JobStore
from harness.safety import SafetyError, resolve_under, safe_filename, sanitize_svg
from harness.skill_loader import load_skills_from_dir
from services.job_runner import JobRunner
from skills.ppt_master.spec_contract import build_spec_contract
from skills.ppt_master.tools import _project, _source, _write_mirror_page_impl, _write_svg_page_impl


def test_resolve_under_rejects_escape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            resolve_under(root, "../escape.txt")
        except SafetyError:
            return
        raise AssertionError("resolve_under allowed path escape")


def test_safe_filename_strips_path_parts():
    assert safe_filename("../../secret.env") == "secret.env"


def test_artifact_manager_rejects_relative_escape():
    with tempfile.TemporaryDirectory() as tmp:
        manager = ArtifactManager(Path(tmp))
        try:
            manager.save("../bad.txt", "bad")
        except SafetyError:
            return
        raise AssertionError("ArtifactManager allowed relative path escape")


def test_sanitize_svg_removes_active_content():
    dirty = '<svg onload="evil()"><script>alert(1)</script><foreignObject>x</foreignObject><a href="javascript:evil()">x</a></svg>'
    clean = sanitize_svg(dirty)
    assert "script" not in clean.lower()
    assert "foreignobject" not in clean.lower()
    assert "onload" not in clean.lower()
    assert "javascript:" not in clean.lower()


def test_spec_contract_parses_pages_and_layouts():
    design_spec = """
## Page 1: 封面
- 标题
## Page 2: 核心内容
- 要点 A
"""
    spec_lock = """
## page_layouts
- P01: 001_cover
- P02: 002_content
"""
    contract = build_spec_contract(design_spec, spec_lock)
    assert [p["num"] for p in contract["pages"]] == [1, 2]
    assert contract["mode"] == "standard"


def test_spec_contract_fails_without_pages():
    try:
        build_spec_contract("没有页面", "没有锁")
    except ValueError as exc:
        assert "没有可解析的页面结构" in str(exc)
        return
    raise AssertionError("build_spec_contract accepted invalid spec")


def test_ppt_tool_project_guard_rejects_outside_path():
    try:
        _project("/tmp/not-agent-harness-project")
    except ValueError:
        return
    raise AssertionError("_project accepted path outside data/jobs")


def test_ppt_tool_source_guard_rejects_outside_file():
    try:
        _source("/etc/passwd", "pdf")
    except ValueError:
        return
    raise AssertionError("_source accepted path outside data/")


def test_ppt_tool_source_guard_allows_https_url():
    assert _source("https://example.com/report", "url") == "https://example.com/report"


def test_write_svg_page_sanitizes_output():
    jobs_root = Path(__file__).parent / "data" / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=jobs_root) as tmp:
        project = Path(tmp) / "project"
        project.mkdir(parents=True, exist_ok=True)
        result = _write_svg_page_impl(str(project), 1, '<svg onload="x()"><script>x</script><text>OK</text></svg>')
        assert "✅" in str(result)
        content = (project / "svg_output" / "page_01.svg").read_text(encoding="utf-8")
        assert "script" not in content.lower()
        assert "onload" not in content.lower()


def test_write_mirror_page_escapes_replacement_text():
    jobs_root = Path(__file__).parent / "data" / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=jobs_root) as tmp:
        project = Path(tmp) / "project"
        tpl_dir = project / "templates"
        tpl_dir.mkdir(parents=True, exist_ok=True)
        (tpl_dir / "001_cover.svg").write_text('<svg><text>Hello</text></svg>', encoding="utf-8")
        result = _write_mirror_page_impl(str(project), 1, "001_cover", '[{"old":"Hello","new":"<script>x</script>"}]')
        assert "✅" in str(result)
        content = (project / "svg_output" / "page_01.svg").read_text(encoding="utf-8")
        assert "<script>" not in content.lower()
        assert "&lt;script&gt;" in content


def test_skill_loader_loads_ppt_master_manifest():
    registry = load_skills_from_dir(Path(__file__).parent / "skills")
    assert "ppt-master" in registry.list_skills()


async def _test_job_runner_rejects_duplicate_running_task_async():
    runner_log = logging.getLogger("services.job_runner")
    old_disabled = runner_log.disabled
    runner_log.disabled = True
    class FakeRuntime:
        async def start_job_with_id(self, job_id, skill_name, user_input, initial_state):
            await asyncio.sleep(0.05)

    runner = JobRunner(lambda: FakeRuntime())
    runner.submit_start("job1", "skill", "input", {})
    try:
        runner.submit_start("job1", "skill", "input", {})
    except RuntimeError:
        task = runner.get_task("job1")
        runner.cancel("job1")
        if task:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        return
    finally:
        runner_log.disabled = old_disabled
        runner.discard("job1")
    raise AssertionError("JobRunner accepted duplicate running task")


def test_job_runner_rejects_duplicate_running_task():
    asyncio.run(_test_job_runner_rejects_duplicate_running_task_async())


def test_job_store_uses_file_lock_for_updates():
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(Path(tmp))
        job = store.create("skill", "input")
        store.update(job["job_id"], current_step="a")
        assert store.get(job["job_id"])["current_step"] == "a"
        assert (Path(tmp) / "jobs" / job["job_id"] / ".state.lock").exists()


def test_event_writer_assigns_contiguous_seq_without_replay_loss():
    with tempfile.TemporaryDirectory() as tmp:
        writer = EventWriter(Path(tmp))
        first = writer.write(Event("step_start"))
        second = writer.write(Event("step_done"))
        assert first["seq"] == 1
        assert second["seq"] == 2
        assert [event["seq"] for event in writer.read_all()] == [1, 2]


if __name__ == "__main__":
    tests = [
        test_resolve_under_rejects_escape,
        test_safe_filename_strips_path_parts,
        test_artifact_manager_rejects_relative_escape,
        test_sanitize_svg_removes_active_content,
        test_spec_contract_parses_pages_and_layouts,
        test_spec_contract_fails_without_pages,
        test_ppt_tool_project_guard_rejects_outside_path,
        test_ppt_tool_source_guard_rejects_outside_file,
        test_ppt_tool_source_guard_allows_https_url,
        test_write_svg_page_sanitizes_output,
        test_write_mirror_page_escapes_replacement_text,
        test_skill_loader_loads_ppt_master_manifest,
        test_job_runner_rejects_duplicate_running_task,
        test_job_store_uses_file_lock_for_updates,
        test_event_writer_assigns_contiguous_seq_without_replay_loss,
    ]
    for test in tests:
        test()
    print(f"✅ {len(tests)} core hardening tests passed")
