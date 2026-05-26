# Agent Harness

> **华中师范大学 华为杯 参赛作品**
> 版权所有，仅供参赛评审使用，未经许可禁止转载、修改或用于任何商业用途。

通用 Agent/Skill 运行平台 MVP。平台核心遵循“Runtime 管生命周期、Skill 只发事件和产物、前端只做事件投影”的分层原则。

## Quick Start

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY

# 3. CLI 测试
python3 main.py "帮我做一个3页PPT：商业银行并购管理"

# 4. API 服务器
python3 server.py
# 访问 http://localhost:8000/docs

# 5. 核心回归测试
python3 test_core_hardening.py
```

## Architecture

```
server.py                         # 薄入口 (~24 行)
  └── routes/               # 模块化路由
        __init__.py           # create_app() 组装 CORS / static / routers
        deps.py               # 单例、路径常量、共享访问器
        upload.py             # 文件上传
        templates.py          # 模板管理
        jobs.py               # 任务生命周期
        projects.py           # SVG / notes / spec / download / events
        settings.py           # LLM 配置热重载
        ws.py                 # WebSocket 广播

Harness Runtime
  ├── SkillRegistry / Manifest Loader
  ├── JobStore              # 原子化 state.json + .state.lock
  ├── EventWriter           # append-only events.jsonl + seq
  ├── ArtifactManager
  ├── Safety Guards         # path / SVG / source boundary
  └── OpenAI Agent SDK Adapter

Services
  ├── runtime_factory
  ├── project_paths
  └── job_runner            # 本地后台任务边界，可替换为 durable queue

Skills
  └── ppt-master
        tools.py              # @_with_path_guards 统一路径安全装饰器
        adapter.py            # spec_contract 驱动执行流
        skill.yaml            # manifest 注册

Frontend
  ├── WebSocket harness_event stream
  ├── Historical event replay
  └── Shared event-to-UI projection
```

## Platform Core Invariants

- **Single lifecycle path**: `start_job()`、`start_job_with_id()`、`resume_job()` 都收敛到 Runtime 内部同一个生命周期执行器。
- **Terminal status guard**: `completed`、`failed`、`cancelled` 是终态，所有兜底逻辑都通过统一 helper 判断。
- **Atomic job state**: `state.json` 使用临时文件 + rename 写入，避免进程中断造成半写文件。
- **Cross-process state guard**: `JobStore` 更新时使用 per-job `.state.lock`，降低本机多进程/热重载下的状态覆盖风险。
- **Append-only events**: `events.jsonl` 是事实日志，每条事件带 `seq`，支持 `/events?after_seq=N` 增量读取。
- **Unified event contract**: WebSocket 和历史恢复都使用原始 `HarnessEvent`，前端通过同一个 projection 函数生成 chat/log/outline/SVG 状态。
- **Skill isolation**: Skill 不直接操作 WebSocket、全局 JobStore 或前端状态，只通过 `SkillSession` 发事件、保存 artifact、请求确认。
- **Tool safety boundary**: PPT tools 只能访问 harness `data/` 与 `data/jobs/` 下的受控路径；URL 只允许 `http/https`。
- **SVG safety boundary**: AI 生成/模板导入/接口返回/前端渲染前均做 SVG 清洗，降低 XSS 风险。
- **Spec contract**: `design_spec.md` / `spec_lock.md` 派生 `spec_contract.json`；Executor 仅从 contract 获取页面结构和布局，无 contract 时失败，不再回退到正则解析。
- **Template ID contract**: 前端只传 `template_id`，服务端内部解析模板路径；API 不向前端暴露 `project_path` / `pptx_path`。
- **LLM config guard**: 有本地运行任务时拒绝热切换模型配置，避免并发任务被全局 `MODEL` 中途替换。

## Skill Manifest

新增 Skill 时，在 `skills/<skill_name>/skill.yaml` 中声明入口：

```yaml
name: example-skill
entrypoint: skills.example_skill.adapter:ExampleSkill
requires:
  - llm
  - artifacts
```

`routes/deps.py` 和 `main.py` 会通过 `harness.skill_loader.load_skills_from_dir()` 自动注册，不需要手改平台入口。

## Claude Code Architecture Lessons Adopted

本项目只吸收通用架构思想，不复制 Claude Code 代码：

- **Task terminal state**: 明确终态集合，避免向已结束任务继续注入状态。
- **Append-only history**: 使用 JSONL 事件历史，前端可重放恢复完整上下文。
- **Tool/Skill boundary**: 平台状态与具体 agent/tool 执行解耦。
- **Single projection path**: 实时流和历史恢复共享同一 UI 投影，避免协议分叉。

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/start | Start ppt-master job |
| GET | /api/status/{job_id} | Get job status |
| POST | /api/confirm/{job_id} | Confirm and resume |
| GET | /api/projects/{job_id}/events | Get append-only HarnessEvent log |
| GET | /api/projects/{job_id}/events?after_seq=N | Incremental event replay |
| GET | /api/projects/{job_id}/svgs | List generated SVG pages |
| GET | /api/projects/{job_id}/svg/{page} | Get SVG content |
| GET | /api/projects/{job_id}/notes | Get speaker notes |
| GET | /api/projects/{job_id}/spec | Get design documents |
| GET | /api/download/{job_id} | Download PPTX |
| GET | /api/jobs | List all jobs |
| POST | /api/jobs/{job_id}/cancel | Cancel job |
| DELETE | /api/jobs/{job_id} | Delete job |
| WS | /ws/progress/{job_id} | Real-time `{ type: "harness_event", event }` stream |
