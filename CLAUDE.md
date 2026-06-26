@AGENTS.md

# PM Agent — AI 项目经理分析系统

## 项目概述

一个模拟项目经理的多 Agent 分析系统。用户输入项目/产品想法后，系统通过**三层 Agent 架构**进行多轮分析（市场调研、竞品分析、产品设计、技术建议、发展方向），最终产出结构化分析看板和可导出的 MD/PDF 报告。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 (TS) | Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 |
| Agent 后端 (Python) | FastAPI + LangGraph + LangChain + Pydantic |
| LLM 引擎 | DeepSeek API（兼容 OpenAI 格式），预留多模型切换 |
| 搜索 | Tavily Search API（MVP），Provider 模式预留多源扩展 |
| 向量存储 | 暂不引入（Phase 2 用于历史项目知识库） |
| 通信 | SSE 流式（Python → Next.js proxy → 浏览器） |

### 为什么是 Hybrid（TS 前端 + Python 后端）

- **TypeScript/Next.js** — 聊天 UI、流式渲染、前端状态管理、MD/PDF 导出
- **Python/LangGraph** — Agent DAG 编排在 Python 生态最成熟（LangGraph/CrewAI/LangChain），LangGraph.js 功能滞后
- 两层通过 FastAPI SSE 端点通信，Next.js API Route 做 proxy 转发

## 核心架构：三层 Agent + 动态 DAG

### Agent 层级

```
Top (决策层)
├── MarketLeader    (市场调研)
├── CompetitorLeader (竞品分析)
├── ProductLeader   (产品设计)
├── FutureLeader    (未来方向)
└── ChangeLeader    (当下改变)
    │
    └── 每个中层 Leader 可调度 N 个底层子 Agent
```

### 执行流程

1. **用户输入** → 顶层 Agent 追问边界条件（目标市场/预算/竞品范围等），禁止自行编造
2. **顶层规划** → 生成 DAG 执行计划（决定哪些中层并行/串行/跳过）
3. **中层执行** → 调度底层搜索，验证数据真伪，逐条目打分
4. **驳回机制** → 上层对低分条目给出明确重做指令（最多 3 轮，超限标记为「存疑」）
5. **汇总输出** → 顶层基于多源一致性加权，生成结构化报告

### DAG 节点 = 一次 LLM 调用

每个 DAG 节点是单一职责的 Agent 调用，输入/输出均为结构化 JSON。节点粒度：一次 prompt → 一次结构化输出。不可在一个节点内塞多个分析任务。

### DAG 引擎：LangGraph (Python)

选择 LangGraph 而非 LangGraph.js 或自研引擎：

- **StateGraph** — 全局 State 作为唯一真相源，每个节点只改自己的字段
- **条件边 (Conditional Edge)** — 打分 → 驳回/通过/熔断 三分支，判断函数是纯代码不调 LLM
- **回路支持** — 驳回 → 回到同节点重做，靠 `retry_count` 上限防止死循环
- **自动并行** — 同一 source → 多个 target 边，LangGraph 自动 fan-out 并行执行
- **状态持久化** — 内置 checkpoint，分析中断可从断点恢复

DAG 三层概念映射：
| DAG 概念 | PM Agent 对应 | LangGraph 实现 |
|---------|-------------|---------------|
| 节点 | 一次 Agent 执行（LLM 调用） | `graph.add_node("name", fn)` |
| 边 | 数据依赖关系 | `graph.add_edge(A, B)` |
| 条件边 | 打分判定 → 通过/驳回/熔断 | `graph.add_conditional_edges(A, judge_fn, paths)` |
| 回路 | 驳回返回同节点重做 | 条件边指向同节点 + `retry_count` 上限 |
| 并行 | 无依赖中层同时跑 | 多条边自动 fan-out |

### State 设计：嵌套 + Public/Internal 分离

#### 设计原则

1. **全局 State 只做路由索引** — 顶层不关心中层内部脏活，只读标准化 Public 接口
2. **每个中层独立子 State** — 字段名不冲突，修改中层不打乱其他层
3. **驳回不存历史数据** — 只存最新一轮输出 + 驳回原因链，不存完整旧数据
4. **子 Agent 用 dict 管理** — key = agent ID，value = SubAgentSlot（最新输出 + 状态 + 驳回日志）

#### 为什么只存最新一轮？

- 被驳回的数据 99% 不会再被引用（驳回指令变了搜索方向和验证标准）
- 旧数据保留只会让中层在下轮读取时混淆——「现在到底看哪轮的数据？」
- 驳回原因链（40 字节/条）提供足够审计信息
- 极少数需要查原始数据 → 日志系统，不是 state

#### 全局 State（顶层直接持有）

```python
class GlobalState(TypedDict):
    """顶层 Agent 的 State —— 只做路由索引"""
    # === 用户输入 ===
    project: ProjectInfo
    conversation_history: list[Message]

    # === 顶层执行计划 ===
    execution_plan: ExecutionPlan   # 决定谁跑、谁跳过、谁并行

    # === 中层结果（只读 Public 字段，详见子 State 定义） ===
    market_research: MarketResearchState | None
    competitor_analysis: CompetitorState | None
    product_design: ProductDesignState | None
    future_direction: FutureState | None
    change_plan: ChangeState | None

    # === 全局控制 ===
    total_api_calls: int            # 已消耗的 LLM 调用次数
    max_api_calls: int              # 30（硬上限）
    current_phase: str
    errors: list[str]
```

#### 中层 State（以市场调研为例）

每个中层 State 分 `Public`（顶层可读）和 `Internal`（中层自己用）两部分：

```python
class MarketResearchState(TypedDict):
    # === Public 接口（顶层只读这三个字段） ===
    summary: str | None                         # ≤ 200 字摘要
    key_points: list[AnalysisPoint]             # ≤ 8 条分析要点
    overall_confidence: float                   # 本部门整体可信度
    status: Literal["completed", "uncertain", "skipped"]

    # === Internal（顶层不碰） ===
    project: dict                               # 顶层传入的项目信息
    focus_direction: str                        # 本中层关注方向
    sub_agents: dict[str, SubAgentSlot]         # ← 底层子 Agent dict
    cycle_count: int                            # 中层整体循环次数
```

**设计意图**：顶层汇总 `market_research.key_points` 时不需要知道底层开了几个子 Agent、搜了几次——它只消费结论。

#### 底层子 Agent dict 定义

```python
class SubAgentSlot(TypedDict):
    """每个底层子 Agent 的「卡槽」—— 只存最新一轮"""
    sub_id: str                            # agent ID，如 "market_trend_query"
    search_query: str                      # 当前搜索词
    latest_output: SubAgentOutput | None   # 只存最新结果（不存历史）
    round_number: int                      # 当前第几轮（1-indexed）
    rejection_log: list[RejectionEntry]    # 每轮驳回原因摘要（不存完整数据）
    status: Literal["running", "passed", "rejected", "uncertain"]


class RejectionEntry(TypedDict):
    """一次驳回记录 — 只记原因，不存完整输出"""
    round: int                             # 第几轮被驳回
    reason: str                            # "可信度 3.2 < 4，来源为个人博客"
    instruction: str                       # "更换搜索词，优先找行业报告"
    timestamp: str


class SubAgentOutput(TypedDict):
    """底层 Agent 归拢结果"""
    summary: str                           # 一句话总结 ≤ 80 字
    topFindings: list[Finding]             # 最多 5 条
```

#### 驳回流程推演（演示 dict 怎么运作）

```
第 1 轮：3 个底层并行执行
    sub_agents = {
        "market_size":    { latest_output: {...}, status: "passed" },      # ✅ 通过
        "user_profile":   { latest_output: {...}, status: "rejected" },    # ❌ 驳回
        "business_model": { latest_output: {...}, status: "passed" },      # ✅ 通过
    }

第 2 轮：只重做 "user_profile"（只改这一个 slot）
    sub_agents["user_profile"] = {
        latest_output:  {...},           # ← 新结果覆盖旧结果
        round_number:   2,
        rejection_log:  [
            {"round": 1, "reason": "可信度 2.1 < 4", "instruction": "换搜索词"}
        ],
        status: "passed",                # ← 本轮通过
    }
    # "market_size" 和 "business_model" 不受影响，结果被中层吸收

第 3 轮：仍不通过 → 标记存疑
    sub_agents["user_profile"] = {
        latest_output:  None,            # 最后这次也没过
        round_number:   3,
        rejection_log:  [
            {"round": 1, ...},
            {"round": 2, ...},
        ],
        status: "uncertain",             # ← 超限，放弃
    }
    # 中层在 key_points 中标注 "该维度数据不足（3 轮未达标）"
```

#### 为什么 dict 优于扁平字段？

| | 扁平字段 | dict[str, SubAgentSlot] |
|---|:--:|:--:|
| 新增子 Agent | 加 N 个新字段 | `sub_agents["new_key"] = slot` 一行 |
| 查找子数据 | `state["sub1_score"]` ← 名字是谁？ | `sub_agents["market_size"]["status"]` ← 路径清晰 |
| 命名冲突 | `market_score` vs `competitor_score` | 各自 State 独立，可同名 |
| 驳回审计 | 不知道哪个子 Agent 被驳回几次 | `slot["rejection_log"]` 精确到单个子 Agent |

### LangGraph vs LangChain 职责划分

```
LangGraph (编排引擎)
  └── DAG 拓扑、状态流转、条件路由、驳回回路、checkpoint

LangChain (工具库)
  └── ChatModel 封装、Prompt Template、Output Parser、Tool 定义
```

- **DAG 图是 LangGraph 管的**，不是 LangChain
- LangChain 帮你少写模板代码（调 DeepSeek、解析 JSON），是辅助
- 两者不是竞争关系，是分工关系

## 关键设计决策

### Agent 间通信：结构化 JSON 直接传递，不用 RAG

中层 Agent 自身就是智能检索层（验证、去重、提炼）。在 agent 链中间插入 RAG 会架空中层判断力，并使驳回闭环复杂化。Phase 2 引入历史项目向量库用于跨项目参考，但不在实时链路中使用。

### 驳回 + 打分：条目级精度

```typescript
// 每项数据被评分，低分条目针对性重做，非整份报告重来
interface ItemScore {
  completeness: number;    // 0-10
  credibility: number;    // 0-10
  freshness: number;       // 0-10
  relevance: number;       // 0-10
}
// 综合分 < 5 或 可信度 < 4 → 驳回 + 附带具体改进指令
// 最多重做 3 次 → 超限标记为「存疑」继续流程
```

### 搜索：Provider 模式

```typescript
interface SearchProvider {
  name: string;
  search(query: string, opts: SearchOptions): Promise<SearchResult[]>;
}
// MVP: TavilyProvider 单一实现
// Phase 2: MultiProvider + CrossValidator 多源交叉验证
```

### 防幻觉三原则

1. **每个结论必须有来源引用** — URL + 原始关键句穿透所有层级保留
2. **无来源则标注「存疑」** — 禁止推测无依据结论
3. **边界不清必须追问用户** — 不得自行假设目标市场/预算/竞品范围

### 多源真实性权重

- 1 个来源：权重 × 0.5
- 2 个独立来源印证：权重 × 0.8
- 3+ 个独立来源印证：权重 × 1.0
- 高权威来源（.gov / 头部媒体 / 研究机构）：额外 +20%
- 来源互相矛盾：暂停加权，由中层 Agent 人工判断

## Token 预算与防过载机制

### 设计目标

防止底层 Agent 数量失控导致 token 消耗爆炸，同时防止中层 Leader 被大量碎片化 JSON 淹没导致注意力分散或幻觉。

### 三层硬预算

```typescript
const BUDGET = {
  // === 一次完整分析 ===
  maxTotalApiCalls: 30,            // 超过则中断，用已有数据生成报告（熔断器）

  // === 中层 Leader 约束 ===
  maxSubAgentsPerLeader: 5,       // 每个中层最多开 5 个底层
  defaultSubAgentsPerLeader: 3,   // 默认开 3 个，不够再追加上限内

  // === 底层 Agent 输出约束 ===
  maxFindingsPerSubAgent: 5,      // 最多返回 5 条发现
  maxCharsPerFinding: 150,        // 每条发现 ≤ 150 字符（≈ 40 tokens）
  maxTokensPerSubAgentOutput: 800,// 单个底层 JSON 输出上限

  // === 中层 Leader 输入约束 ===
  maxTokensPerMiddleInput: 4000,  // 中层收到的全部 JSON ≤ 4000 tokens
};
```

### 底层输出 Schema（严格控制体积）

```typescript
interface SubAgentOutput {
  summary: string;          // 一句话总结（≤ 80 字），供中层快速扫描
  topFindings: Finding[];   // 最多 5 条，按相关度降序
}

interface Finding {
  insight: string;          // 关键发现（≤ 150 字）
  sourceUrl: string;        // 来源 URL
  sourceType: 'data' | 'report' | 'opinion';
  relevance: number;        // 1-10 与任务相关度自评
  confidence: number;       // 1-10 数据可信度自评
}
```

**设计要点**：
- `summary` 不是摆设——中层数据太多时先扫描所有 summary 快速定位，再深读具体 finding
- `relevance < 5` 的发现：底层自行丢弃，不向上输出
- 与其他来源重复的发现：标注「与 X 来源一致」，不重复输出相同内容

### 中层分步处理（漏斗式，防一次性吞入）

中层 Leader 禁止一次性读完所有底层数据做判断。强制分三步：

```
Step 1 — 扫描摘要（~3 × 80 字 = 240 字）
  → "这几份搜索的共性结论是什么？矛盾点在哪里？"

Step 2 — 挑重点深读（取 topFinding 中的前 5 条高相关条目）
  → "深入分析这 5 条发现，补充细节，评估置信度"

Step 3 — 整理输出（结构化提炼）
  → "产出本部门分析结果，缺失维度标注'数据不足'"
```

### 中层输出约束（防凑数）

```
- 最多输出 8 条分析要点，每条 ≤ 200 字
- 如果数据不足以支撑 8 条，有几条写几条，严禁凑数
- 缺失维度必须标注："该维度数据不足"
- 禁止在没有数据支撑的情况下编造趋势、预测或结论
```

### 中层 Prompt 内置防迷失指令

分析时必须遵循：
1. 先看所有 summary，总结共性和矛盾点
2. 对有矛盾的发现，对比来源权威度，选择置信度更高的一方
3. 相关性预过滤交给底层做，中层不做垃圾清理
4. 信任底层自评的 relevance/confidence 分数，不对低分条目过度关注

### 效果基准

以市场调研中层为例的合规调用：
```
底层1: 搜索 "宠物社交App 市场规模 2025 2026" → 5 条发现 ≈ 800 tokens
底层2: 搜索 "宠物经济 用户画像 中国市场"       → 5 条发现 ≈ 800 tokens
底层3: 搜索 "宠物App 商业模式 变现"            → 4 条发现 ≈ 650 tokens
                                                    (relevance<5 已过滤)

中层收到的总输入 ≈ 2250 tokens + 800 tokens(prompt) ≈ 3000 tokens ✅
中层输出 ≈ 8 × 200 字 ≈ 1600 tokens ✅
```

## 编码约定

### 项目结构（规划）

```
pm-agent/
├── src/                    # Next.js 前端 (TypeScript)
│   ├── app/                # App Router
│   │   ├── page.tsx       # 主聊天界面
│   │   ├── layout.tsx     # 根布局
│   │   └── api/           # API Routes (proxy → Python)
│   ├── components/         # React 组件
│   ├── hooks/              # 自定义 Hooks (SSE 消费等)
│   └── types/              # 前端类型定义
│
├── agent-backend/          # Agent 引擎 (Python)
│   ├── main.py            # FastAPI 入口 + SSE 端点
│   ├── agents/             # Agent 核心
│   │   ├── top/           # 顶层决策 + DAG 计划生成
│   │   ├── middle/         # 中层 Leader (5 个方向)
│   │   └── bottom/         # 底层搜索 Agent
│   ├── dag/                # LangGraph DAG
│   │   ├── graph.py       # 图定义 + 节点连线
│   │   ├── nodes.py       # 各节点实现
│   │   └── conditions.py  # 条件边判断函数
│   ├── llm/                # LLM Provider
│   │   ├── deepseek.py    # DeepSeek 实现
│   │   └── base.py        # Provider 基类
│   ├── search/             # 搜索 Provider
│   │   ├── tavily.py      # Tavily 实现
│   │   └── base.py        # SearchProvider 接口
│   ├── schemas/            # Pydantic 数据模型
│   │   ├── agent.py       # Agent 通信 Schema
│   │   ├── report.py      # 报告结构 Schema
│   │   └── budget.py      # 预算常量
│   ├── prompts/            # Prompt YAML 模板
│   │   ├── top.yaml
│   │   ├── middle-market.yaml
│   │   └── bottom.yaml
│   └── utils/              # 工具函数
│       ├── scoring.py     # 打分计算
│       └── budget.py      # 预算检查 + 熔断
│
├── docs/                   # 文档
│   └── superpowers/
│       ├── specs/          # 设计规格
│       └── plans/          # 实现计划
└── CLAUDE.md              # 本文件
```

### 代码风格

- TypeScript strict mode，所有类型显式声明
- 一个文件一个明确职责，超过 200 行检查是否该拆分
- Agent prompt 模板化：`prompts/{agent-name}.ts` 独立管理
- 测试覆盖 Agent 的核心决策链路（非 UI）

### Agent 开发原则

- 每个 Agent 调用是**幂等的**：同输入 → 同输出，状态外挂到 DAG 上下文
- Agent 间通信始终用结构化 JSON，不传自由文本对话历史
- 每个 Agent 只看到它需要的数据，不给多余上下文
- 原始引用链（URL + 关键句）穿透全部层级保留

## 开发阶段

| 阶段 | 范围 |
|------|------|
| **Phase 1 MVP** | 聊天界面 + 三层 Agent + Tavily 搜索 + 结构化报告 + MD 导出 |
| **Phase 2** | 历史项目向量库 + 多源搜索 + PDF 导出 + 多用户 |
| **Phase 3** | 多模型切换 + 辩论模式 + 项目间关联分析 |

## 相关文档

- 设计规格：`docs/superpowers/specs/` (待产出)
- 实现计划：`docs/superpowers/plans/` (待产出)
