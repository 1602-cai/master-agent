# Spec Lock — ContextBroker 渐进式上下文披露测试

**replication_mode**: mirror

---

## Canvas

| 参数 | 值 |
|------|-----|
| 格式 | Standard (16:9) |
| 分辨率 | 1920 × 1080 px |
| 方向 | Landscape |
| 安全边距 | 上下左右各 60px |

---

## Colors

| 角色 | 色值 | 用途 |
|------|------|------|
| Primary | `#1A365D` | 标题、强调边框、关键数据高亮、深色背景 |
| Secondary | `#EDF2F7` | 大面积背景、卡片底色 |
| Accent | `#00A3C4` | 核心图标、数据流箭头、KPI 数字 |
| Background | `#FFFFFF` | 纯白底 |
| Body Text | `#2D3748` | 正文内容 |
| White Text | `#FFFFFF` | 深色背景上的文字 |
| Muted | `#718096` | 注释、次要信息 |

---

## Typography

| 层级 | 西文字体 | 中文字体 | 字重 |
|------|----------|----------|------|
| 封面主标题 | Montserrat | Microsoft YaHei | Bold 700, 34-36pt |
| 页面标题 | Montserrat | Microsoft YaHei | SemiBold 600, 26-28pt |
| 小标题 | Montserrat | Microsoft YaHei | Medium 500, 18-20pt |
| 正文 | Inter | PingFang SC / Microsoft YaHei | Regular 400, 14-16pt |
| 注释 | Inter | PingFang SC / Microsoft YaHei | Light 300, 10-12pt |

---

## Icons

| 参数 | 值 |
|------|-----|
| 方案 | 内置图标库 — tabler-outline |
| 描边宽度 | 1.5 px |
| 图标色 | `#1A365D` 或 `#00A3C4` |
| 使用场景 | 数据模型层级标识、三种披露机制标识、KPI 图标、流向箭头 |

---

## Images

| 方案 | 说明 |
|------|------|
| D) 无图片，仅图表/数据流图 | 不使用非技术性照片。所有视觉信息通过流程图、架构图、数据表格传递。 |

---

## Page Rhythm

| 页码 | 节奏 | 说明 |
|------|------|------|
| P01 | **anchor** | 封面，结构锚点，引入主题 |
| P02 | **dense** | 信息密集页，集中展示核心机制与测试策略 |
| P03 | **anchor** | 结尾/致谢，收束总结与展望 |

> 节奏校验通过：anchor → dense → anchor，符合 3 页简短汇报节奏。

---

## Page Layouts

| 页码 | 模板 SVG | 模板类型 | 内容概要 |
|------|----------|----------|---------|
| P01 | `001_cover` (或 `01_cover`) | **封面页** | 主标题：ContextBroker 渐进式上下文披露测试；副标题+团队/日期 |
| P02 | `002_content` | **内容页** | 页面标题：核心机制详解；NGSI v2 三层模型 + 三种披露机制 + 数据流 + 测试维度 + 性能表 |
| P03 | `015_ending` | **结尾页/致谢页** | 总结与展望；应用场景回顾 + 测试策略 + 未来展望 + 三大挑战；致谢语 |

---

## Page Charts

| 页码 | 图表/图示类型 | 描述 |
|------|-------------|------|
| P02 | 层级结构图 | NGSI v2 三层数据模型：Entity → Attribute → Metadata |
| P02 | 对比表格 | 三种披露机制对比（查询筛选 / 订阅通知 / 属性级控制） |
| P02 | 数据流图 | 客户端 → NGSI v2 API → Broker → 数据模型 → 过滤结果 |
| P02 | 数据表格 | 性能基准参考（1K ~ 1M 实体的预期响应时间） |
| P03 | 三列卡片/区块 | 应用场景（智慧城市 / 工业 IoT / 智能农业） |
| P03 | 列表/图标 | 三大挑战（性能 / 语义 / 实时性） |

---

## Forbidden

- ❌ 非技术性照片/图片
- ❌ 荧光色、高饱和红/紫等跳跃颜色
- ❌ 衬线字体（Times New Roman、宋体等）
- ❌ 厚重冗余的阴影或渐变
- ❌ 动画/转场特效
- ❌ 复杂背景纹理或图案
- ❌ 与核心机制无关的装饰元素
- ❌ 每页信息超载（P02 dense 但保持清晰分区）
- ❌ 额外增加页面（严格控制 3 页）

---

## 执行校验清单

- [x] 总页数：3 页 ✅
- [x] P01 使用封面模板 (`001_cover` / `01_cover`) ✅
- [x] P02 使用内容模板 (`002_content`) ✅
- [x] P03 使用结尾模板 (`015_ending`) ✅
- [x] 节奏：anchor → dense → anchor ✅
- [x] 所有颜色、字体、图标已锁定 ✅
- [x] 禁止项已明确 ✅
