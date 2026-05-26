# Web UI V2 — Chat 风格 + 实时 SVG 预览

> 基于 Skywork SkyClaw 参考 UI 的改造方案
> 替代 PLAN.md (V1 三页分离式) → 单页 Chat + 双栏实时预览

---

## 0. 与 V1 的核心差异

| 维度 | V1 (当前) | V2 (目标) |
|------|-----------|-----------|
| **页面结构** | 3 个独立路由页 (Home/Progress/Result) | **单页应用**，动态布局切换 |
| **交互范式** | 表单式 → 进度条 → 结果卡 | **对话式** Chat 输入 → AI 消息流 |
| **生成中布局** | 进度条 + 日志面板 | **左栏** 对话流 + **右栏** 实时 SVG 大画布 |
| **SVG 预览** | 缩略图网格 (底部，事后查看) | **实时渲染**，每生成一页右侧立即显示 |
| **大纲** | 无 | PPT 大纲卡片 (时间线形式) |
| **底部状态** | 无 | 全局任务状态栏 |

---

## 1. 布局架构

### 1.1 三种布局状态

```
┌─ 状态 A: 首页 (idle) ────────────────────────────────────────┐
│                                                                │
│                    Logo + "全能 PPT 助手"                       │
│                                                                │
│              ┌────────────────────────────────┐                │
│              │ 🎨PPT│ 请输入主题和需求，@引用文件 │                │
│              │      │                          │                │
│              │ 📎1个文件  ⚡1个技能    🚀发送   │                │
│              └────────────────────────────────┘                │
│                                                                │
│         [PPT] [文档] [图片] [表格] [网站] [全部Skills]          │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌─ 状态 B: 生成中 (running/confirming) ─────────────────────────┐
│  PPT Master  ━━  {project_name}                       [取消]   │
├────────────────────────┬───────────────────────────────────────┤
│  💬 对话流 (左栏 40%)   │  🖼 实时 SVG 预览 (右栏 60%)           │
│                        │                                       │
│  🤖 SkyClaw ✨智选模型  │  ┌─────────────────────────────────┐ │
│  好的！我先读取内容...   │  │                                 │ │
│                        │  │     (当前 SVG 页面大图渲染)        │ │
│  📖 读取文件 ˅          │  │     viewBox="0 0 1280 720"      │ │
│  ┌─ MCP工具 | 读取文件 ┐│  │                                 │ │
│  │ ./parsed/xxx.md     ││  │                                 │ │
│  └─────────────────────┘│  └─────────────────────────────────┘ │
│                        │                                       │
│  内容已读取完毕！       │  ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐ ... 缩略  │
│  • 第14章: ...          │  │01││02││03││04││05││06│     图条   │
│  • 第15章: ...          │  └──┘└──┘└──┘└──┘└──┘└──┘           │
│                        │                                       │
│  📋 PPT大纲 ˅          │  ← 版本 1/1 →                        │
│  ┌─────────────────┐   │                                       │
│  │ P01 封面标题     │   │                                       │
│  │ P02 xxx         │   │                                       │
│  │ P03 xxx ← 生成中│   │                                       │
│  └─────────────────┘   │                                       │
│                        │                                       │
│  ● 正在生成中...        │                                       │
├────────────────────────┴───────────────────────────────────────┤
│  ○ 任务运行中  Step 3/7 · 生成SVG · 第5/10页           [⏸暂停] │
└────────────────────────────────────────────────────────────────┘

┌─ 状态 C: 完成 (done) ─────────────────────────────────────────┐
│  PPT Master  ━━  {project_name}                                │
├────────────────────────┬───────────────────────────────────────┤
│  💬 对话流 (左栏)       │  🖼 SVG 预览 (右栏, 可翻页)            │
│                        │                                       │
│  ...之前的消息...       │  ┌─────────────────────────────────┐ │
│                        │  │     (SVG 大图, 可点击翻页)        │ │
│  🎉 PPT 生成完成!       │  │                                 │ │
│  📄 10 页 · 87KB       │  │                                 │ │
│  🕐 耗时 3分12秒       │  └─────────────────────────────────┘ │
│                        │                                       │
│  [⬇️ 下载PPTX]         │  ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐         │
│  [📝 查看演讲稿]        │  │01││02││03││04││05││..│ 缩略图条  │
│                        │  └──┘└──┘└──┘└──┘└──┘└──┘           │
│                        │                                       │
│  [🔄 生成新的PPT]       │  ← P.3/10 →                         │
├────────────────────────┴───────────────────────────────────────┤
│  ✅ 任务已完成  10页 · 87KB · 3分12秒                  [新任务] │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 响应式

| 屏幕 | 布局 |
|------|------|
| `≥1024px` | 左右双栏 (40% / 60%) |
| `<1024px` | 单栏，SVG 预览折叠为可展开面板 |

---

## 2. 组件拆分

### 2.1 新文件结构

```
demo/web/src/
├── main.tsx
├── App.tsx                        # 不再用 react-router，单页动态布局
├── store.ts                       # zustand 全局状态 (扩展)
├── api.ts                         # REST API (保持)
├── ws.ts                          # WebSocket (扩展消息类型)
├── vite-env.d.ts
│
├── layouts/
│   ├── IdleLayout.tsx             # 状态A: 首页居中布局
│   └── WorkLayout.tsx             # 状态B/C: 左右双栏布局
│
├── components/
│   ├── ChatInput.tsx              # 底部输入栏 (PPT标签+文本+附件+发送)
│   ├── ChatMessages.tsx           # 对话消息列表
│   ├── MessageBubble.tsx          # 单条消息气泡 (AI/用户/系统)
│   ├── ToolCallCard.tsx           # 工具调用展示卡片 (折叠式)
│   ├── OutlineCard.tsx            # PPT大纲时间线卡片
│   ├── ConfirmationCard.tsx       # 八项确认交互卡片
│   ├── LiveSvgPreview.tsx         # 右栏: SVG 大画布 + 翻页
│   ├── SvgThumbnailStrip.tsx      # 底部 SVG 缩略图条
│   ├── StatusBar.tsx              # 底部全局状态栏
│   ├── FileChip.tsx               # 文件附件芯片 (PDF图标+文件名)
│   ├── SkillBadge.tsx             # 技能标记 (PPT)
│   └── ResultActions.tsx          # 完成后操作按钮组
│
└── lib/
    └── utils.ts                   # 保持
```

### 2.2 核心组件规格

#### `ChatInput.tsx`
```
┌──────────────────────────────────────────────────┐
│ 🎨PPT│ 请输入PPT的主题和需求，输入@可引用文件     │
│                                                    │
│ 📎1个文件  ⚡1个技能                     🚀发送   │
└──────────────────────────────────────────────────┘
```
- **PPT Skill 标签**: 固定显示，紫色圆角标签
- **文本输入**: 多行 textarea，placeholder 引导
- **附件指示**: 显示已上传文件数，点击可管理
- **发送按钮**: 紫色圆形，触发流水线启动
- 首页模式下带文件拖拽区域

#### `MessageBubble.tsx`
| 类型 | 样式 | 内容 |
|------|------|------|
| `user` | 右对齐，深色背景，PPT标签 | 用户输入文字 |
| `ai` | 左对齐，头像+名称+模型标签 | AI 回复文本 |
| `tool` | 嵌套在 ai 消息中，折叠式 | 工具调用详情 |
| `system` | 居中，小字 | 步骤分隔线 |

#### `OutlineCard.tsx`
```
┌ PPT大纲 ──────────────────────── [📋复制] [↗全屏] ┐
│  ● P01  封面标题                                   │
│         概述内容摘要...                             │
│  ● P02  第14章 利率风险                            │
│         利率类型、VaR计算...                        │
│  ◐ P03  麦考利久期与修正久期  ← 生成中              │
│  ○ P04  凸性分析                                   │
│  ...                                               │
└────────────────────────────────────────────────────┘
```
- `●` 已完成 (绿色) / `◐` 生成中 (蓝色动画) / `○` 待生成 (灰色)
- 点击某页可在右栏跳转预览

#### `LiveSvgPreview.tsx`
- 右栏主体，占满剩余空间
- `dangerouslySetInnerHTML` 渲染 SVG
- 顶部: 关闭按钮
- 底部: 缩略图条 + 翻页导航 (← P.3/10 →)
- 加载中显示 spinner
- 每收到 `svg_created` WS 消息，自动跳到新页

#### `StatusBar.tsx`
```
┌───────────────────────────────────────────────────────────┐
│ ○ 任务运行中  Step 3/7 · 生成SVG · 第5/10页     [⏸暂停]  │
└───────────────────────────────────────────────────────────┘
```
- 固定在窗口底部
- 状态图标: ○ 运行中(旋转) / ✅ 完成(绿色) / ❌ 错误(红色)
- 进度文本: 步骤 + 当前动作 + 细粒度进度

---

## 3. Store 改造

```typescript
interface AppStore {
  // === 布局状态 ===
  phase: 'idle' | 'running' | 'confirming' | 'done' | 'error'

  // === 输入 ===
  file: File | null
  fileId: string
  inputText: string            // 用户输入的文字需求

  // === 任务 ===
  jobId: string
  currentStep: number          // 1-7
  currentStepName: string

  // === 对话消息 ===
  messages: ChatMessage[]
  // ChatMessage = { id, role: 'user'|'ai'|'tool'|'system', content, timestamp, ... }

  // === SVG 预览 ===
  svgPages: SvgPageData[]      // { page, svgContent, status: 'done'|'generating' }
  currentPreviewPage: number   // 当前右栏显示的页码
  totalPlannedPages: number    // 大纲规划的总页数

  // === 大纲 ===
  outline: OutlineItem[]       // { page, title, summary, status }

  // === 八项确认 ===
  eightConfirmations: string

  // === 结果 ===
  pptxUrl: string
  pptxSize: number
  totalPages: number
  durationMs: number
  notes: Record<string, string>

  // === Actions ===
  addMessage: (msg: ChatMessage) => void
  updateSvgPage: (page: number, content: string) => void
  setCurrentPreviewPage: (page: number) => void
  setOutline: (items: OutlineItem[]) => void
  updateOutlineStatus: (page: number, status: string) => void
  // ... 其他 actions
}
```

---

## 4. WebSocket 消息扩展

V1 已有的消息保持不变，**新增**以下类型：

```typescript
type WSMessageV2 =
  // === V1 保留 ===
  | { type: "step_start"; step: number; name: string; timestamp: string }
  | { type: "step_done"; step: number; duration_ms: number }
  | { type: "log"; level: string; message: string }
  | { type: "svg_created"; page: number; filename: string }
  | { type: "confirmation_needed"; eight_confirmations: string }
  | { type: "pipeline_done"; pptx_path: string; pptx_size: number; total_pages: number; duration_ms: number }
  | { type: "error"; message: string }

  // === V2 新增 ===
  | { type: "ai_message"; content: string }             // AI 对话消息 (流式或完整)
  | { type: "tool_call"; tool: string; args: string }   // 工具调用展示
  | { type: "outline"; pages: OutlineItem[] }           // PPT大纲推送
  | { type: "svg_content"; page: number; svg: string }  // 直推 SVG 内容到前端 (实时渲染关键!)
  | { type: "page_generating"; page: number }           // 某页开始生成
```

### 4.1 实时 SVG 关键路径

```
executor_node 写 SVG → write_svg_page 工具调用
    ↓ (在 write_svg_page 后 or nodes.py 中)
progress_callback({"type": "svg_content", "page": N, "svg": "<svg>...</svg>"})
    ↓
WebSocket → 前端 ws.ts handler
    ↓
store.updateSvgPage(N, svgContent)  +  store.setCurrentPreviewPage(N)
    ↓
LiveSvgPreview 组件重新渲染 → 右栏立即显示新 SVG
```

---

## 5. 后端改动

### 5.1 `server.py` 改动

- **无大改**，现有 API 全部保留
- 新增 `POST /api/upload_url` — 支持 URL 输入（如果尚无）

### 5.2 `nodes.py` 改动

在 `executor_node` 中，每写完一页 SVG 后通过 callback 推送 SVG 内容：

```python
# executor_node 中，agent 调用 write_svg_page 后
# 读取刚写入的 SVG 文件并推送
svg_dir = Path(state["project_path"]) / "svg_output"
for svg_file in sorted(svg_dir.glob("*.svg")):
    content = svg_file.read_text(encoding="utf-8")
    if cb:
        await cb({
            "type": "svg_content",
            "page": int(svg_file.stem.split("_")[0].replace("page", "")),
            "svg": content
        })
```

或更优方案: **在 `write_svg_page` 工具内部**添加回调钩子，每写一页立即推送。

### 5.3 大纲推送

在 `generate_spec_node` 完成后，解析 `design_spec.md` 提取大纲并推送：

```python
if cb:
    # 解析 design_spec 中的内容大纲
    outline = parse_outline_from_spec(state.get("design_spec", ""))
    await cb({"type": "outline", "pages": outline})
```

---

## 6. 前端对话消息映射

| 后端事件 | 前端消息 |
|----------|---------|
| 用户点发送 | `{ role: 'user', content: inputText }` |
| `step_start` step=1 | `{ role: 'ai', content: '好的！我先读取文件内容...' }` |
| `step_done` step=1 | `{ role: 'tool', content: '✅ 源文件解析完成 (2109字符)' }` |
| `step_start` step=4 | `{ role: 'ai', content: '现在开始分析内容，生成设计策略...' }` |
| `confirmation_needed` | `{ role: 'ai', content: eightConfirmations }` + ConfirmationCard |
| `outline` | OutlineCard 组件插入消息流 |
| `step_start` step=6 | `{ role: 'ai', content: '资源准备完成，开始生成SVG幻灯片...' }` |
| `svg_content` | 大纲中对应页标记为 ✅，右栏更新 |
| `pipeline_done` | `{ role: 'ai', content: '🎉 PPT生成完成! 共10页...' }` + ResultActions |

---

## 7. 不改的部分

| 文件/模块 | 说明 |
|-----------|------|
| `graph.py` | 不改 |
| `agents_def.py` | 不改 |
| `tools/*` | 不改 (考虑在 `write_svg_page` 中加回调钩子) |
| `config.py` | 不改 |
| `state.py` | 不改 (V1 已加够字段) |
| `ws_manager.py` | 不改 |
| `main.py` | 不改 (CLI 模式保留) |

---

## 8. 改动量估算

| 文件 | 动作 | 行数 |
|------|------|------|
| `App.tsx` | **重写** | ~60 |
| `store.ts` | **重写** | ~180 |
| `ws.ts` | **扩展** | ~80 (+30) |
| `api.ts` | 微调 | ~5 |
| `layouts/IdleLayout.tsx` | **新增** | ~40 |
| `layouts/WorkLayout.tsx` | **新增** | ~50 |
| `components/ChatInput.tsx` | **新增** | ~120 |
| `components/ChatMessages.tsx` | **新增** | ~80 |
| `components/MessageBubble.tsx` | **新增** | ~90 |
| `components/ToolCallCard.tsx` | **新增** | ~50 |
| `components/OutlineCard.tsx` | **新增** | ~80 |
| `components/ConfirmationCard.tsx` | **新增** | ~100 |
| `components/LiveSvgPreview.tsx` | **新增** | ~120 |
| `components/SvgThumbnailStrip.tsx` | **新增** | ~60 |
| `components/StatusBar.tsx` | **新增** | ~50 |
| `components/FileChip.tsx` | **新增** | ~25 |
| `components/ResultActions.tsx` | **新增** | ~60 |
| `nodes.py` | 微改 (SVG推送) | ~20 |
| **前端合计** | | **~1250** |
| **后端合计** | | **~20** |
| **总计** | | **~1270** |

---

## 9. 开发步骤

### Phase 1: 基础骨架 (~20min)
1. 删除旧 `pages/` 目录
2. 重写 `App.tsx` — 根据 `phase` 切换 IdleLayout / WorkLayout
3. 重写 `store.ts` — 新 state 结构
4. 新建 `layouts/IdleLayout.tsx` + `layouts/WorkLayout.tsx`

### Phase 2: 对话流 (~25min)
5. `ChatInput.tsx` — PPT 标签 + 输入 + 附件 + 发送
6. `ChatMessages.tsx` + `MessageBubble.tsx` — 消息渲染
7. `ToolCallCard.tsx` — 折叠式工具调用
8. 扩展 `ws.ts` — 新消息类型 → store.addMessage

### Phase 3: 实时 SVG 预览 (~20min)
9. `LiveSvgPreview.tsx` — 大画布 + 翻页
10. `SvgThumbnailStrip.tsx` — 底部缩略图条
11. 后端 `nodes.py` — executor_node 推送 SVG 内容
12. `ws.ts` 处理 `svg_content` → store → 右栏实时更新

### Phase 4: 交互卡片 (~15min)
13. `OutlineCard.tsx` — 大纲时间线
14. `ConfirmationCard.tsx` — 八项确认 (确认/修改/split)
15. `ResultActions.tsx` — 完成后操作

### Phase 5: 状态栏 + 美化 (~10min)
16. `StatusBar.tsx` — 底部全局状态
17. 动画过渡、暗色主题微调
18. 响应式适配

---

## 10. 视觉规范

延续 V1 暗色主题:

| Token | 值 | 用途 |
|-------|-----|------|
| `--app-bg` | `#1C1C1E` | 全局背景 |
| `--card-bg` | `#191B1F` | 卡片/消息背景 |
| `--chat-user-bg` | `#2A2D35` | 用户消息气泡 |
| `--accent` | `#6C47FF` | 主强调色 (发送按钮、PPT标签) |
| `--accent-light` | `#8B5CF6` | hover 态 |
| `--text-primary` | `#F5F5F5` | 主文字 |
| `--text-secondary` | `#979FAB` | 辅助文字 |
| `--border` | `#525763` | 分割线 |
| `--success` | `#22C55E` | 完成 |
| `--warning` | `#F59E0B` | 等待确认 |
| `--error` | `#EF4444` | 错误 |

字体: `Outfit` (英文) + `Noto Sans SC` (中文)
代码: `JetBrains Mono`
