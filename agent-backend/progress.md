# PM Agent 后端开发进度

> 最后更新: 2026-07-01

## 最终目标

用户输入产品想法 → 三层 Agent 全自动分析 → 结构化看板 + MD/PDF 导出，前端实时展示进度。

## ✅ 已完成

| 项目 | 说明 |
|------|------|
| 项目骨架 | Poetry + Python 3.11，全链路跑通 |
| LLM Provider | DeepSeek (OpenAI兼容)，预留多模型切换 (`llm/base.py` + `deepseek.py`) |
| Search Provider | Tavily，Provider模式预留多源扩展 (`search/base.py` + `tavily.py`) |
| Schema | Pydantic 唯一真源：GlobalState / DepartmentState / ExecutionPlan / FinalReport |
| Prompt模板 | Top/Middle×5/Bottom/Reviewer/CEO/搜索策略/通用部门 共12套System Prompt |
| 三层Agent | Top(动态选部门) + Middle(BaseMiddleLeader模板) + Bottom(SearchAgent) |
| DAG引擎 | LangGraph StateGraph：3节点(planning→execute→aggregate) + MemorySaver checkpoint |
| 审核+驳回 | 四维打分(completeness/credibility/freshness/relevance)，3轮驳回→UNCERTAIN |
| 并行搜索 | `asyncio.gather`并行，`_search_one()`异常内化 |
| SSE端点 | `POST /analyze/stream`(SSE) + `/analyze`(非SSE) + `GET /analyze/{id}`(恢复) |
| ProgressTracker | 12种事件类型贯穿全链路，tracker=None时静默跳过 |
| Agent化 | Top LLM动态选3-7部门(可跳过/自创)；中层LLM SearchStrategy；驳回instruction回写 |
| MiddleLeader重构 | 5文件2030行→1文件446行；MiddleLeaderConfig删除；config构造函数注入 |
| 前端SSE对接 | TS类型适配Agent化；plan_generated/reducer适配新数据形状；端到端验证通过 |

## 🐛 已知Bug — 当前阶段

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| B1 | 🔴 高 | Tavily SDK同步调用阻塞事件循环，`asyncio.gather`并行性归零 | `search/tavily.py:109` |
| B2 | 🟡 中 | 搜索异常的UNCERTAIN被review覆盖为PASSED（空结果以"通过"进入分析） | `agents/middle/__init__.py:289-308` |
| B3 | 🟡 中 | 审核LLM失败时返回fake PASSED（满分5.0），虚报高置信度 | `agents/middle/__init__.py:393-403` |

## 💡 架构讨论：什么时候用 LangGraph

外层DAG(planning→execute→aggregate)用LangGraph但只做线性执行，内层审核循环(驳回/重试/状态转换)才是LangGraph擅长的场景却用Python for循环。**当前阶段这是合理选择**：

| 场景 | 用LangGraph | 用Python原生 |
|------|------------|-------------|
| 固定少量步骤(≤5步)，无分支 | ❌ 杀鸡用牛刀 | ✅ 函数链足够 |
| 有界循环(≤N轮)，状态简单 | ❌ 过度工程 | ✅ for循环更直观 |
| **无界循环**(LLM动态决定是否继续) | ✅ 条件边天然支持 | ❌ while True+手动管理 |
| **多路径分支**(不同部门不同驳回路径) | ✅ StateGraph+条件路由 | ❌ if-else堆叠 |
| **跨节点状态依赖**(A的驳回影响B的策略) | ✅ 全局State共享 | ❌ 手动传参 |
| **中断恢复精确到子步骤** | ✅ checkpoint到每个节点 | ❌ 需自己实现 |
| **可视化调试**(LangGraph Studio) | ✅ 图结构可视图 | ❌ 只能打日志 |

**结论**：当前 3 轮固定驳回 + 简单状态转换，Python for 循环比嵌套 LangGraph 子图更合适。当以下任一条件触发时，应引入 LangGraph 到内层：
1. 审核轮次变为无界（LLM 判断质量达标才退出）
2. 不同部门的驳回路径开始分化
3. 需要跨部门交叉驳回（市场调研的驳回影响竞品分析的搜索策略）
4. 需要子 Agent 级别的 checkpoint 恢复

## 🔧 待优化 — 用 LLM 动态判断质量替代固定 3 轮驳回

**当前问题**：审核循环硬编码 `max_cycles=3`。即使第 1 轮数据已足够也被迫跑满；即使第 3 轮仍不够也强制结束。浪费 API 调用，且低质量数据进入最终分析。

**目标**：取消固定轮次，改为每轮审核 LLM 对每个 sub_agent 输出三种判定：

```
"passed"   → 数据质量达标，该 agent 不再重搜
"rejected" → 数据不满足指标，给出 improved_query 重搜  
"abandon"  → 多次重搜均失败，放弃并标记 UNCERTAIN（防无限循环）
```

循环退出条件：`所有 agent ∈ {passed, abandon}`。达标即退出（省调用），有改进空间继续（保质量），确实搜不到放弃（防死循环）。

**相关**：这是 LangGraph 触发器 1（无界循环），审核逻辑从 `for cycle in range(1,4)` 变为 `while not all_done`。B2+B3 的修复与此联动——修复后的审核路径（passed/rejected/abandon）恰好用于 LLM 动态判断。

## 📅 未完成 — 未来阶段(Phase 3+)

| 项目 | 说明 |
|------|------|
| 多模型切换 | Provider 热切换 (OpenAI / Claude / 本地模型) |
| 历史项目向量库 | RAG 检索历史分析报告，复用相似项目结论 |
| 多源搜索 | Google / Bing 扩展，Provider 模式已预留 |
| PDF/MD导出 | FinalReport → Markdown / PDF 文件 |
| 辩论模式 | 多个中层对同一维度独立分析→交叉验证 |
| 持久化 | SQLite checkpoint 替代 MemorySaver；SSE会话存储持久化 |
| 多用户 | 用户隔离、历史记录、项目间关联分析 |

## 重要信息

- **入口**: `main.py "项目描述"` (console) 或 `uvicorn main:app --port 8000` (API)
- **运行环境**: 必须在 `agent-backend/` 目录下；Python: `.venv/Scripts/python.exe`
- **编码规范**: Conventional Commits + 中文subject；Pydantic唯一真源；依赖注入
- **熔断**: 60次LLM调用上限；每中层3轮驳回上限
- **防幻觉**: 每条结论必须有URL+原始关键句；无来源→标存疑；边界不清→追问
- **API文档**: `docs/api.md`
