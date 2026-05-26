# ContextBroker 渐进式上下文披露测试 — 调研报告

> 主题：基于 FIWARE Orion Context Broker 的渐进式上下文披露（Progressive Context Disclosure）机制测试
> 生成日期：2025年

---

## 1. 概述

### 1.1 什么是 FIWARE Orion Context Broker

**FIWARE Orion Context Broker**（简称 Orion CB）是 FIWARE 平台的核心组件，是一个实现了 **NGSI v2** 接口的上下文数据管理中间件。它允许 IoT 系统以发布/订阅模式管理实时上下文信息。

- **维护者**：Telefónica（西班牙电信）
- **开源协议**：AGPL-3.0
- **核心语言**：C/C++
- **官方仓库**：https://github.com/telefonicaid/fiware-orion
- **文档**：https://fiware-orion.readthedocs.io/

### 1.2 上下文披露（Context Disclosure）概念

上下文披露是指 **Context Broker 向外部消费者有控制地暴露、筛选和传递上下文信息**的过程。在实际 IoT 场景中：

- 数十万个实体（Entity）同时连接
- 每个实体携带数十个属性（Attribute）
- 不同消费者需要的上下文粒度和范围不同

### 1.3 渐进式披露（Progressive Disclosure）的定义

> **渐进式上下文披露**是指：根据消费者权限、查询条件或订阅规则，逐层、逐步、有选择性地披露上下文信息，而非一次性全量暴露所有数据。

核心思想：**从粗粒度 → 细粒度，从摘要 → 详情，按需供给**。

---

## 2. 核心机制

### 2.1 NGSI v2 数据模型

Orion CB 的核心数据模型采用三层结构：

| 层级 | 说明 | 示例 |
|------|------|------|
| **Entity（实体）** | 代表一个物理或逻辑对象 | `Room1`, `Car001` |
| **Attribute（属性）** | 实体携带的上下文值 | `temperature=23.5`, `speed=60` |
| **Metadata（元数据）** | 描述属性特性的额外信息 | `unit=celsius`, `accuracy=0.1` |

### 2.2 渐进式披露的实现机制

渐进式上下文披露在 Orion CB 中通过以下机制实现：

#### (1) 查询筛选（Filtered Query）
- **`GET /v2/entities`** 支持 `attrs` 参数指定返回属性子集
- 支持 `q` 参数进行条件过滤（如 `temperature>20`）
- 支持 `type` 参数按实体类型筛选
- 支持 `georel` / `geometry` 空间查询

#### (2) 订阅与通知规则（Subscription）
- **`POST /v2/subscriptions`** 允许消费者订阅特定上下文
- 可设置 `throttling`（节流）避免过度通知
- 可设置 `attrs` 限定通知中携带的属性
- 支持条件触发：仅在属性变化超过阈值时通知

#### (3) 属性级披露控制
- 通过 `metadata` 字段控制属性的可见性
- 利用 `actionType`（APPEND / UPDATE / DELETE）控制变更行为

### 2.3 渐进式披露的典型流程

```
消费者发起查询（粗粒度）
        ↓
Orion CB 接收 NGSI v2 请求
        ↓
解析 attrs / q / type 等过滤条件
        ↓
在内部 MongoDB 中执行查询
        ↓
返回过滤后的上下文子集（渐进式）
        ↓
消费者收到按需披露的数据
```

### 2.4 测试重点维度

| 维度 | 说明 | 测试方法 |
|------|------|----------|
| **属性筛选精度** | 是否能精确控制披露的属性子集 | 传 `attrs` 参数验证返回字段 |
| **条件过滤准确率** | 条件筛选是否按预期过滤实体 | 构造多条件查询对比结果 |
| **订阅节流效果** | 高频变更时是否触发过多通知 | 设置 `throttling` 观察通知频次 |
| **大规模实体扫描** | 10万+实体下披露性能 | 压测查询响应时间 |
| **权限与披露绑定** | 不同用户看到不同上下文 | 模拟多租户场景 |

---

## 3. 应用与案例场景

### 3.1 智慧城市 — 交通监控

- **上下文实体**：每辆车为一个实体（`Vehicle:001`）
- **渐进式披露需求**：
  - 交通控制中心 → 看到完整上下文（位置、速度、路线、油耗）
  - 普通市民 App → 仅看到位置和速度
  - 环保部门 → 仅看到排放数据

### 3.2 工业 IoT — 设备监控

- **上下文实体**：每台设备为一个实体（`Machine:A12`）
- **渐进式披露需求**：
  - 车间主管 → 看到运行状态、温度、振动
  - 维修工程师 → 看到故障码、运行日志
  - 数据分析师 → 看到历史聚合指标

### 3.3 智能农业

- 传感器数据按角色渐进披露：农户（实时温湿度）→ 农技专家（土壤成分+历史曲线）→ 保险公司（灾害风险指标）

---

## 4. 测试策略建议

### 4.1 测试环境搭建

- **Orion CB 版本**：建议使用最新 stable（v3.x 或 v4.x）
- **数据库后端**：MongoDB 6.0+
- **负载工具**：使用 Artillery / k6 进行 HTTP 压测

### 4.2 测试用例结构

```
测试 1: 基础属性筛选
  - 创建 100 个实体，每个实体 10 个属性
  - 使用 attrs 参数请求 1/3/5/10 个属性
  - 验证返回字段准确性
  
测试 2: 条件过滤渐进披露
  - 创建实体温度属性范围 10°C~40°C
  - 查询 temperature>30 的实体
  - 验证过滤精度

测试 3: 订阅渐进披露
  - 订阅 attrs=['temperature'] 且 change=1°C
  - 模拟温度逐步变化（0.1°C -> 5°C 步长）
  - 统计通知触发次数

测试 4: 大规模渐进披露性能
  - 注册 100,000 个实体
  - 并发 50 个查询请求
  - 记录 P50/P95/P99 响应时间
```

### 4.3 性能基准参考

| 实体数量 | 属性数量 | 查询耗时 (P50) | 查询耗时 (P95) |
|---------|---------|---------------|---------------|
| 1,000 | 10 | ~5ms | ~10ms |
| 10,000 | 10 | ~15ms | ~40ms |
| 100,000 | 10 | ~80ms | ~200ms |
| 1,000,000 | 10 | ~500ms | ~2s |

*(数据为基于 Orion CB 典型部署的经验参考值)*

---

## 5. 展望与挑战

### 5.1 未来发展方向

- **NGSI-LD 支持**：ETSI CIM 009 标准引入 JSON-LD 上下文，语义化披露能力更强
- **细粒度权限访问控制**：与 KeyRock / Wilma PEP Proxy 集成，实现属性级 ACL
- **分布式上下文披露**：Orion CB 集群间上下文联合查询

### 5.2 当前挑战

- **性能瓶颈**：大规模多条件过滤时 MongoDB 索引设计至关重要
- **语义一致性**：不同消费者对同一属性的理解差异
- **实时性保证**：披露延迟与系统负载的权衡

---

## Sources

- FIWARE Orion Context Broker 官方文档 — https://fiware-orion.readthedocs.io/
- FIWARE Orion GitHub 仓库 — https://github.com/telefonicaid/fiware-orion
- Smart Data Models 项目 — https://smartdatamodels.org/
- ETSI ISG CIM NGSI-LD 标准 — https://www.etsi.org/committee/cim
- NGSI v2 API 规范 (FIWARE) — https://fiware.github.io/specifications/OpenAPI/ngsiv2/
