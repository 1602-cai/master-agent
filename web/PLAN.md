# Web UI 技术方案

> LangGraph + OpenAI Agents SDK + PPT Master 的 Web 前端 + 后端包装

---

## 1. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│  Browser                                                      │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐ │
│  │ ① 上传   │→ │ ② 配置   │→ │ ③ 进度面板 │→ │ ④ 结果    │ │
│  │ 拖拽文件  │  │ 模板选择  │  │ 实时日志    │  │ PPTX 下载 │ │
│  │ URL 粘贴  │  │ 画布格式  │  │ SVG 预览   │  │ 演讲稿    │ │
│  └──────────┘  │ 八项确认  │  │ 步骤进度条  │  └───────────┘ │
│                 └──────────┘  └────────────┘                  │
│       ↕ REST                      ↕ WebSocket                 │
├───────────────────────────────────────────────────────────────┤
│  FastAPI Backend  (Port 8000)                                 │
│                                                               │
│  ┌─────────────┐  ┌────────────┐  ┌────────────────────────┐│
│  │ REST API    │  │ WebSocket  │  │ 现有 LangGraph 流水线   ││
│  │ /upload     │  │ /ws/{job}  │  │ (graph.py, nodes.py    ││
│  │ /start      │  │ 进度推送   │  │  agents_def.py, tools/)││
│  │ /confirm    │  │ 日志广播   │  │ 完全不改               ││
│  │ /download   │  │ SVG 变化   │  └────────────────────────┘│
│  │ /templates  │  └────────────┘                              │
│  └─────────────┘                                              │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. 后端 (FastAPI)

### 2.1 文件结构

```
demo/
├── server.py                # FastAPI 主入口 (~250行)
├── ws_manager.py            # WebSocket 连接管理 (~60行)
├── ... (现有文件不变)
```

### 2.2 API 设计

#### REST 端点

| 端点 | 方法 | 请求体 | 响应 | 说明 |
|---|---|---|---|---|
| `POST /api/upload` | multipart | `file: UploadFile` | `{file_id, filename, size}` | 上传源文件到临时目录 |
| `GET /api/templates` | - | - | `{layouts: [...], brands: [...], decks: [...]}` | 列出所有可用模板 |
| `POST /api/start` | JSON | `{file_id, template_id?, canvas_format?, auto?}` | `{job_id}` | 启动流水线 |
| `GET /api/status/{job_id}` | - | - | `{step, status, project_path, ...}` | 查询任务状态 |
| `POST /api/confirm/{job_id}` | JSON | `{action: "confirm"/"split"/"modify", feedback?}` | `{ok}` | 用户确认/修改八项设计 |
| `GET /api/download/{job_id}` | - | - | File response | 下载 PPTX 文件 |
| `GET /api/projects/{job_id}/svgs` | - | - | `[{page, url, size}]` | 列出 SVG 页面 |
| `GET /api/projects/{job_id}/svg/{page}` | - | - | SVG content | 获取单页 SVG |
| `GET /api/projects/{job_id}/notes` | - | - | `{total, pages: [...]}` | 获取演讲稿 |
| `GET /api/projects/{job_id}/spec` | - | - | `{design_spec, spec_lock, eight_confirmations}` | 获取设计文档 |

#### WebSocket 端点

| 端点 | 消息方向 | 格式 |
|---|---|---|
| `ws://localhost:8000/ws/progress/{job_id}` | Server → Client | JSON |

WebSocket 消息类型：

```typescript
type WSMessage =
  | { type: "step_start"; step: number; name: string; timestamp: string }
  | { type: "step_done"; step: number; duration_ms: number }
  | { type: "log"; level: "info" | "warning" | "error"; message: string }
  | { type: "svg_created"; page: number; filename: string }
  | { type: "confirmation_needed"; eight_confirmations: string }
  | { type: "pipeline_done"; pptx_path: string; pptx_size: number }
  | { type: "pipeline_error"; error: string; step: number }
```

### 2.3 核心改动

**只改 2 个文件** + **新增 2 个文件**:

#### 改: `config.py` — 增加 WebSocket 日志广播

```python
# 新增: WebSocket 广播 handler
class WebSocketLogHandler(logging.Handler):
    """将日志消息广播到所有连接的 WebSocket 客户端."""
    def __init__(self, ws_manager):
        super().__init__()
        self.ws_manager = ws_manager

    def emit(self, record):
        msg = {"type": "log", "level": record.levelname.lower(), "message": self.format(record)}
        asyncio.create_task(self.ws_manager.broadcast(record.job_id, msg))
```

#### 改: `nodes.py` — 节点增加进度回调

```python
# 方案 A: 通过 PPTState 注入回调（推荐）
# 在 PPTState 中添加:
#   progress_callback: Optional[Callable]  # WebSocket 推送函数

async def source_processing_node(state: PPTState) -> dict:
    cb = state.get("progress_callback")
    if cb: await cb({"type": "step_start", "step": 1, "name": "源文件处理"})
    ...
    if cb: await cb({"type": "step_done", "step": 1, "duration_ms": ...})
```

#### 新: `server.py`

```python
from fastapi import FastAPI, UploadFile, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PPT Master Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# 任务存储 (单机内存，足够比赛用)
jobs: dict[str, dict] = {}

@app.post("/api/upload")
async def upload_file(file: UploadFile): ...

@app.get("/api/templates")
async def list_templates(): ...

@app.post("/api/start")
async def start_pipeline(req: StartRequest): ...
    # 创建 asyncio.Task 运行 graph.ainvoke
    # 注入 progress_callback 到 initial_state

@app.post("/api/confirm/{job_id}")
async def confirm_design(job_id: str, req: ConfirmRequest): ...
    # 通过 asyncio.Event 通知暂停的 human_confirmation_node

@app.websocket("/ws/progress/{job_id}")
async def ws_progress(ws: WebSocket, job_id: str): ...

@app.get("/api/download/{job_id}")
async def download_pptx(job_id: str): ...
```

#### 新: `ws_manager.py`

```python
class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, ws: WebSocket): ...
    def disconnect(self, job_id: str, ws: WebSocket): ...
    async def broadcast(self, job_id: str, message: dict): ...
```

### 2.4 Human-in-the-loop 改造

CLI 模式用 `input()` 阻塞，Web 模式用 `asyncio.Event` 替代：

```python
# nodes.py — human_confirmation_node 改造
async def human_confirmation_node(state: PPTState) -> dict:
    if state.get("auto_mode"):
        return {"user_confirmed": True, ...}

    # Web 模式: 推送确认请求，等待 Event
    event = state.get("confirmation_event")  # asyncio.Event
    if event:
        cb = state.get("progress_callback")
        await cb({"type": "confirmation_needed", "eight_confirmations": state["eight_confirmations"]})
        await event.wait()  # 阻塞直到 /api/confirm 被调用
        user_input = state.get("user_feedback", "确认")
    else:
        user_input = await asyncio.to_thread(input, "👤 你的回复: ")
    ...
```

---

## 3. 前端 (React)

### 3.1 技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| React | 18+ | 框架 |
| Vite | 6+ | 构建工具 |
| TailwindCSS | 4+ | 样式 |
| shadcn/ui | latest | UI 组件库 |
| Lucide React | latest | 图标 |
| zustand | 5+ | 状态管理 |
| react-dropzone | latest | 文件拖拽上传 |

### 3.2 文件结构

```
demo/web/
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx                    # 路由 + 布局
│   ├── store.ts                   # zustand 全局状态
│   ├── api.ts                     # REST API 封装
│   ├── ws.ts                      # WebSocket 连接管理
│   ├── pages/
│   │   ├── HomePage.tsx           # ① 上传 + 模板选择
│   │   ├── ProgressPage.tsx       # ② 进度面板 (主页面)
│   │   └── ResultPage.tsx         # ③ 结果下载
│   ├── components/
│   │   ├── FileUpload.tsx         # 拖拽上传组件
│   │   ├── TemplateGrid.tsx       # 模板网格 (卡片)
│   │   ├── CanvasFormatPicker.tsx # 画布格式选择器
│   │   ├── StepProgress.tsx       # 7步进度条
│   │   ├── LogStream.tsx          # 实时日志流 (终端风格)
│   │   ├── ConfirmationCard.tsx   # 八项确认卡片 (可编辑)
│   │   ├── SvgPreview.tsx         # SVG 缩略图网格
│   │   ├── SvgViewer.tsx          # 单页 SVG 放大查看
│   │   ├── DownloadPanel.tsx      # PPTX 下载面板
│   │   └── NotesPreview.tsx       # 演讲稿预览
│   └── lib/
│       └── utils.ts               # 辅助函数
```

### 3.3 页面设计

#### ① 首页 (HomePage)

```
┌──────────────────────────────────────────────────────┐
│  🎨 PPT Master                               [设置]  │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │     📄                                          │ │
│  │     拖拽文件到这里，或点击选择                      │ │
│  │     支持 PDF / DOCX / XLSX / PPTX / URL         │ │
│  │                                                  │ │
│  │     ┌──────────────────────────────┐             │ │
│  │     │ 或输入网页 URL               │             │ │
│  │     └──────────────────────────────┘             │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  画布格式:  ● 16:9  ○ 4:3  ○ 竖版  ○ 小红书          │
│                                                       │
│  📐 选择模板 (可选):                                   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │academic│ │ai_ops  │ │gov_blue│ │gov_red │        │
│  │defense │ │        │ │        │ │        │        │
│  │ [缩略图]│ │ [缩略图]│ │ [缩略图]│ │ [缩略图]│        │
│  │ 学术答辩│ │ AI运维 │ │ 政府蓝 │ │ 政府红 │        │
│  └────────┘ └────────┘ └────────┘ └────────┘        │
│  ┌────────┐ ┌────────┐ ┌────────┐                   │
│  │ ...更多 │ │ 自由设计│                               │
│  └────────┘ └────────┘                               │
│                                                       │
│              ┌───────────────────┐                    │
│              │ 🚀 开始生成 PPT   │                    │
│              └───────────────────┘                    │
└──────────────────────────────────────────────────────┘
```

#### ② 进度面板 (ProgressPage) — 核心页面

```
┌──────────────────────────────────────────────────────┐
│  🎨 PPT Master  ━━  资产定价_Chapter14-15      [取消] │
├──────────────────────────────────────────────────────┤
│                                                       │
│  进度: ●━━●━━●━━●━━○━━○━━○   Step 4/7                │
│        1   2   3   4   5   6   7                     │
│        源  项  模  策  图  执  导                     │
│        件  目  板  略  片  行  出                     │
│                                                       │
├────────────────────────┬─────────────────────────────┤
│  📋 八项确认            │  📄 日志                     │
│                        │                              │
│  ┌──────────────────┐  │  01:07:30 ✅ 解析完成        │
│  │ 1. 画布格式       │  │  01:07:32 📁 项目初始化      │
│  │ ● 16:9  ○ 4:3   │  │  01:07:33 📐 模板: academic  │
│  └──────────────────┘  │  01:07:35 🎨 Strategist...   │
│  ┌──────────────────┐  │  01:08:12 ✅ 八项确认完成     │
│  │ 2. 页数范围       │  │  ...                         │
│  │ 10-12 页         │  │                              │
│  └──────────────────┘  │                              │
│  ┌──────────────────┐  │                              │
│  │ 3. 配色方案       │  │                              │
│  │ 主: #1B3A5C      │  │                              │
│  │ ■■■ ■■■ ■■■     │  │                              │
│  └──────────────────┘  │                              │
│  ...                   │                              │
│                        │                              │
│  [✏️ 修改] [✅ 确认]   │                              │
│  [📦 Split Mode]      │                              │
├────────────────────────┴─────────────────────────────┤
│  🖼️ SVG 预览 (实时更新)                               │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐         │
│  │ 01 │ │ 02 │ │ 03 │ │ 04 │ │ 05 │ │ .. │         │
│  │    │ │    │ │    │ │    │ │    │ │    │         │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘         │
└──────────────────────────────────────────────────────┘
```

#### ③ 结果页 (ResultPage)

```
┌──────────────────────────────────────────────────────┐
│  🎉 PPT 生成完成!                                     │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────┐   📊 统计                        │
│  │                 │   ━━━━━━━━                       │
│  │   [PPT 封面     │   📄 页数: 10                    │
│  │    缩略图]      │   📁 大小: 87 KB                 │
│  │                 │   🕐 耗时: 3分12秒               │
│  │                 │   🎨 模板: academic_defense       │
│  └─────────────────┘   📝 演讲稿: 7,422 字            │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐                  │
│  │ ⬇️ 下载 PPTX  │  │ 📝 查看演讲稿 │                  │
│  └──────────────┘  └──────────────┘                  │
│                                                       │
│  🖼️ 全部页面预览                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                │
│  │ P.01 │ │ P.02 │ │ P.03 │ │ P.04 │                │
│  │      │ │      │ │      │ │      │                │
│  │      │ │      │ │      │ │      │                │
│  └──────┘ └──────┘ └──────┘ └──────┘                │
│  (点击放大查看)                                        │
│                                                       │
│  ┌──────────────────┐                                │
│  │ 🔄 生成新的 PPT   │                                │
│  └──────────────────┘                                │
└──────────────────────────────────────────────────────┘
```

### 3.4 zustand 状态

```typescript
interface AppStore {
  // 上传
  file: File | null;
  fileId: string;
  url: string;

  // 配置
  templateId: string;
  canvasFormat: "ppt169" | "ppt43" | "xhs" | "story";
  templates: Template[];

  // 任务
  jobId: string;
  status: "idle" | "uploading" | "running" | "confirming" | "done" | "error";
  currentStep: number;        // 1-7
  logs: LogEntry[];
  eightConfirmations: string;

  // SVG 预览
  svgPages: SvgPage[];

  // 结果
  pptxUrl: string;
  pptxSize: number;
  totalNotes: string;
  durationMs: number;

  // Actions
  setFile: (f: File) => void;
  startPipeline: () => Promise<void>;
  confirmDesign: (action: string, feedback?: string) => Promise<void>;
  connectWebSocket: (jobId: string) => void;
}
```

---

## 4. 改动量评估

| 文件 | 改动类型 | 行数 |
|---|---|---|
| `server.py` | **新增** | ~250 |
| `ws_manager.py` | **新增** | ~60 |
| `config.py` | 微改 (加 WS handler) | +20 |
| `state.py` | 微改 (加 callback 字段) | +5 |
| `nodes.py` | 微改 (每个节点加 2 行回调) | +30 |
| `graph.py` | 不改 | 0 |
| `agents_def.py` | 不改 | 0 |
| `tools/*` | 不改 | 0 |
| **后端小计** | | **~365** |
| 前端 `web/` | **新增** | ~800-1000 |
| **总计** | | **~1200-1400** |

---

## 5. 开发步骤

### Phase 1: 后端 API (~30min)

1. `ws_manager.py` — WebSocket 连接管理器
2. `state.py` — 增加 `progress_callback` 和 `confirmation_event` 字段
3. `nodes.py` — 每个节点开头/结尾加进度回调
4. `server.py` — FastAPI 主入口，全部 API 端点
5. 验证: `curl` 测试 `/api/templates`、`/api/upload`

### Phase 2: 前端基础 (~40min)

1. `npx create-vite web --template react-ts`
2. 安装 tailwindcss + shadcn/ui
3. `HomePage.tsx` — 上传 + 模板选择
4. `ProgressPage.tsx` — 进度条 + 日志流
5. `ResultPage.tsx` — 下载页
6. `api.ts` + `ws.ts` — 后端通信
7. `store.ts` — zustand 状态

### Phase 3: 联调 (~20min)

1. 前后端联调上传 → 启动流水线 → 实时进度
2. 八项确认交互
3. SVG 预览实时更新
4. PPTX 下载

### Phase 4: 美化 (~15min)

1. 进度条动画
2. SVG 缩略图网格
3. 日志流终端风格 (深色背景 + 等宽字体)
4. 响应式布局

---

## 6. 启动方式

```bash
# 终端 1: 后端
cd demo
pip install fastapi uvicorn python-multipart
uvicorn server:app --reload --port 8000

# 终端 2: 前端
cd demo/web
npm install
npm run dev
# → http://localhost:3000

# CLI 模式仍然保留:
python3 main.py /path/to/file.pdf --auto
```

---

## 7. 新增依赖

### 后端

```
fastapi>=0.115.0
uvicorn>=0.32.0
python-multipart>=0.0.9
```

### 前端

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^7.0.0",
    "zustand": "^5.0.0",
    "react-dropzone": "^14.0.0",
    "lucide-react": "^0.460.0"
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.0.0"
  }
}
```
