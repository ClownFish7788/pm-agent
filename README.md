# PM Agent — AI 项目经理

一个 AI 驱动的项目经理分析系统。输入你的项目想法，获得多维度深度分析报告。

## 它能做什么

你只需要描述你想做（或正在做）的项目，PM Agent 会像一位资深的项目经理顾问一样，通过多轮对话深入了解你的项目，并调动多个 AI 分析团队并行工作，最终产出一份涵盖以下维度的完整分析报告：

- **市场调研** — 目标市场规模、增长趋势、用户画像、需求分析
- **竞品分析** — 竞品识别、功能对比、技术栈对比、优劣势分析
- **产品设计** — 功能优先级、MVP 建议、产品路线图
- **技术建议** — 推荐技术栈、架构方案、第三方服务选型
- **当下改变** — 当前需要立即采取的行动和改进
- **未来方向** — 中长期发展建议、潜在风险、机遇评估

支持导出为 Markdown / PDF 文档。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                   用户 (Web Chat)                         │
└────────────────────────┬────────────────────────────────┘
                         │  SSE Stream
┌────────────────────────▼────────────────────────────────┐
│              Next.js (TypeScript 前端)                    │
│  · 聊天 UI  · Markdown 渲染  · PDF 导出  · SSE 消费      │
│  · API Route 代理 (proxy → Python backend)              │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP/SSE
┌────────────────────────▼────────────────────────────────┐
│              FastAPI (Python Agent 后端)                  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │          LangGraph DAG 编排引擎                   │    │
│  │                                                  │    │
│  │   顶层决策 Agent (CEO)                            │    │
│  │   · 追问边界  · 生成计划  · 驳回调度  · 加权汇总 │    │
│  │   ┌────┬────┬────┬────┬────┐                     │    │
│  │   │市场│竞品│产品│未来│当下│  ← 中层 Leader       │    │
│  │   │调研│分析│设计│方向│改变│                     │    │
│  │   └──┬─┴──┬─┴──┬─┴──┬─┴──┬─┘                     │    │
│  │      └────┴──┬──┴────┴────┘                      │    │
│  │         ┌────▼────────┐                          │    │
│  │         │ 底层搜索 Agent│  ← 多源数据采集 + 真伪辨别│    │
│  │         └────┬────────┘                          │    │
│  └──────────────┼───────────────────────────────────┘    │
└─────────────────┼────────────────────────────────────────┘
                  │
┌─────────────────▼────────────────────────────────────────┐
│                   Tavily Search API                       │
└──────────────────────────────────────────────────────────┘
```

### 核心机制

- **动态 DAG 调度** — 顶层 Agent 根据项目类型动态决定分析策略：哪些并行、哪些串行、哪些跳过
- **条目级驳回/重做** — 每项数据被评分，低分条目针对性重做（最多 3 轮），而非整份报告重来
- **多源真实性加权** — 多源印证的数据权重更高，来源互相矛盾时暂停加权由 Agent 判断
- **主动追问防编造** — 遇到边界不清（目标市场、预算等），Agent 必须追问用户，禁止自行假设
- **Token 预算熔断** — 全局 30 次 API 调用硬上限，底层/中层/全局三层约束

## 技术栈

| 类别 | 技术 |
|------|------|
| 前端 | Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 |
| Agent 后端 | Python 3.11+ + FastAPI + LangGraph + LangChain |
| LLM 引擎 | DeepSeek API（兼容 OpenAI 格式） |
| 搜索服务 | Tavily Search API（Provider 模式） |
| 数据验证 | Pydantic (Python) + Zod (TypeScript) |
| 通信 | SSE 流式推送 (Python → Next.js proxy → 浏览器) |

### 为什么是 Hybrid 架构？

- **TypeScript/Next.js** 做聊天 UI、流式渲染、前端状态管理 —— 这是它最擅长的
- **Python/LangGraph** 做 Agent DAG 编排 —— Python 的 Agent 框架生态最成熟（LangGraph、CrewAI 等），LangGraph.js 功能滞后
- 两层通过 FastAPI SSE 端点通信，Next.js API Route 做 proxy 转发

## 快速开始

```bash
# === 前端 ===
npm install
cp .env.example .env.local   # DEEPSEEK_API_KEY, TAVILY_API_KEY

# === Agent 后端 ===
cd agent-backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # FASTAPI_PORT, DEEPSEEK_API_KEY, TAVILY_API_KEY

# === 启动 ===
# 终端 1: Agent 后端
cd agent-backend && uvicorn main:app --reload --port 8000

# 终端 2: 前端
npm run dev

# 打开 http://localhost:3000
```

## 项目结构

```
pm-agent/
├── src/                     # Next.js 前端 (TypeScript)
│   ├── app/                 # App Router 页面 + API Routes
│   ├── components/          # React 聊天 UI 组件
│   └── hooks/               # SSE 消费等自定义 Hooks
│
├── agent-backend/           # Agent 引擎 (Python)
│   ├── main.py             # FastAPI 入口 + /analyze SSE 端点
│   ├── agents/              # 三层 Agent (top/middle/bottom)
│   ├── dag/                 # LangGraph DAG 定义 + 条件边
│   ├── llm/                 # LLM Provider (DeepSeek + 预留)
│   ├── search/              # 搜索 Provider (Tavily + 预留)
│   ├── schemas/             # Pydantic 数据模型
│   ├── prompts/             # Prompt YAML 模板
│   └── utils/               # 打分/预算检查工具
│
└── docs/                    # 文档 (规格 + 计划)
```

## 开发阶段

| 阶段 | 范围 | 状态 |
|------|------|------|
| Phase 1 MVP | 聊天界面 + 三层 Agent + 搜索 + 报告 + MD 导出 | 🚧 设计中 |
| Phase 2 | 历史项目向量库 + 多源搜索 + PDF 导出 + 多用户 | ⏳ 规划中 |
| Phase 3 | 多模型切换 + 辩论模式 + 跨项目关联分析 | 📋 待规划 |

## License

MIT
