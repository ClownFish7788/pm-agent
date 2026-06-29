@AGENTS.md

# PM Agent — AI 项目经理分析系统

## 项目概述

用户输入产品想法 → 三层 Agent 多轮分析（市场/竞品/产品/技术/方向）→ 结构化看板 + MD/PDF 导出。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 |
| Agent 后端 | FastAPI + LangGraph + LangChain + Pydantic |
| LLM | DeepSeek API（OpenAI 兼容），预留多模型切换 |
| 搜索 | Tavily（MVP），Provider 模式预留多源 |
| 通信 | SSE 流式：Python → Next.js API Route proxy → 浏览器 |

**为什么 Hybrid？** TypeScript 做 UI/流式渲染/导出；Python 做 Agent 编排（LangGraph 生态最成熟，LangGraph.js 功能滞后）。

## 核心架构

### 三层 Agent

```
Top（决策层）— 理解需求、追问边界、生成执行计划、汇总报告
  ├── MarketLeader      → 调度 N 个底层搜索子 Agent
  ├── CompetitorLeader   → 同上
  ├── ProductLeader      → 同上
  ├── FutureLeader       → 同上
  └── ChangeLeader       → 同上
```

每个中层 Leader 是独立的分析部门，各自调度底层子 Agent 搜索 → 验证 → 打分 → 输出。

### 执行流程（5 步）

1. **追问边界** — 顶层禁止自行假设目标市场/预算/竞品范围，必须追问用户
2. **生成 DAG 计划** — 顶层决定哪些中层并行/串行/跳过
3. **中层执行** — 调度底层搜索，逐条目四维打分（完整度/可信度/新鲜度/相关度，各 0-10）
4. **驳回闭环** — 综合分 <5 或可信度 <4 → 驳回重做，最多 3 轮，超限标「存疑」
5. **汇总输出** — 顶层基于多源一致性加权生成结构化报告

### DAG 引擎：LangGraph

核心理由：StateGraph（全局唯一真相源）+ 条件边（纯代码判断，不调 LLM）+ 回路支持 + 自动并行 fan-out + checkpoint 断点恢复。

概念映射：节点 = 一次 LLM 调用、边 = 数据依赖、条件边 = 打分→通过/驳回/熔断三分支、回路 = 驳回重做。

LangGraph 管编排（DAG 拓扑、状态流转、条件路由）；LangChain 管工具（ChatModel 封装、Prompt Template、Output Parser）。

## State 设计哲学

### 核心原则

- **Public/Internal 分离** — 顶层只读中层的 `summary + key_points + overall_confidence`，不碰内部子 Agent 细节
- **dict 管理子 Agent** — `sub_agents["market_size"]` 而非扁平字段，增删子 Agent 灵活、命名不冲突、驳回审计精确到单个 slot
- **只存最新一轮** — 驳回后新结果覆盖旧结果，只保留驳回原因链（≤40 字节/条）做审计；旧数据 99% 不会被再引用

### 数据流向

```
底层子 Agent → SubAgentSlot（summary ≤80字 + topFindings ≤5条）
     ↓
中层 Leader 分三步消费（漏斗式）：
  Step 1: 扫描所有 summary → 找共性和矛盾
  Step 2: 深读高相关条目 → 评估置信度
  Step 3: 整理输出 ≤8 条要点，每条 ≤200 字，不够不凑
     ↓
顶层 → 汇总各中层 key_points → 结构化报告
```

## Token 预算（硬限制）

| 约束 | 数值 |
|------|------|
| 单次分析总 API 调用上限（熔断器） | 30 次 |
| 每个中层最多开底层子 Agent | 5 个（默认 3） |
| 每个底层最多返回发现 | 5 条，每条 ≤150 字 |
| 单个底层 JSON 输出上限 | ~800 tokens |
| 中层收到全部 JSON 上限 | ~4000 tokens |

超出熔断 → 用已有数据直接生成报告，标记未完成维度。

## 关键设计决策

### 防幻觉
1. 每个结论必须有 URL + 原始关键句，穿透所有层级保留
2. 无来源 → 标「存疑」，禁止推测
3. 边界不清 → 追问用户，禁止自行假设

### 多源权重
- 1 个来源 ×0.5 / 2 个独立来源 ×0.8 / 3+ 个 ×1.0
- 高权威来源（.gov/头部媒体/研究机构）额外 +20%
- 来源矛盾 → 暂停加权，中层人工判断

### 通信
- Agent 间始终用结构化 JSON，不传自由文本对话历史
- 不在实时链路中插入 RAG（中层本身就是智能检索层）
- 每个 Agent 只看到它需要的数据

## 项目结构

```
pm-agent/
├── src/                     # Next.js 前端
│   ├── app/                 # App Router（page/layout/api proxy）
│   ├── components/          # React 组件
│   ├── hooks/               # SSE 消费等自定义 Hook
│   └── types/               # 前端类型定义
├── agent-backend/           # Python Agent 引擎
│   ├── main.py              # FastAPI + SSE 端点
│   ├── agents/{top,middle,bottom}/  # 三层 Agent
│   ├── dag/                 # LangGraph 图/节点/条件边
│   ├── llm/                 # LLM Provider（DeepSeek + 基类）
│   ├── search/              # 搜索 Provider（Tavily + 基类）
│   ├── schemas/             # Pydantic 数据模型
│   ├── prompts/             # Prompt YAML 模板
│   └── utils/               # 打分/预算检查
└── docs/                    # 设计规格 + 实现计划
```

## 开发阶段

| 阶段 | 范围 |
|------|------|
| **Phase 1 MVP** | 聊天界面 + 三层 Agent + Tavily 搜索 + 结构化报告 + MD 导出 |
| **Phase 2** | 历史项目向量库 + 多源搜索 + PDF 导出 + 多用户 |
| **Phase 3** | 多模型切换 + 辩论模式 + 项目间关联分析 |
