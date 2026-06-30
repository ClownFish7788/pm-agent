# PM Agent 后端开发进度

> 最后更新: 2026-06-30

## 最终目标

用户输入产品想法 → 三层 Agent 全自动分析 → 结构化看板 + MD/PDF 导出，前端实时展示进度。

## ✅ 已完成

| 项目 | 说明 |
|------|------|
| 项目骨架 | 23个源文件，Poetry + Python 3.11，全链路跑通 |
| LLM Provider | DeepSeek (OpenAI兼容)，预留多模型切换 (`llm/base.py` + `deepseek.py`) |
| Search Provider | Tavily，Provider模式预留多源扩展 (`search/base.py` + `tavily.py`) |
| Schema | Pydantic 唯一真源：GlobalState / ExecutionPlan / 5×中层State / FinalReport |
| Prompt模板 | 三层Agent+CEO+Reviewer共8套System Prompt (`prompts/templates.py`) |
| 三层Agent | TopAgent + 5×MiddleLeader + SearchAgent (底层研究员：搜索→筛选→报告) |
| DAG引擎 | LangGraph StateGraph：5中层并行fan-out + 条件边Skip路由 + MemorySaver checkpoint |
| 搜索词截断 | Top Agent LLM 提取 `core_topic` 替代硬截断 |
| 审核+驳回 | 四维打分(completeness/credibility/freshness/relevance)，3轮驳回→UNCERTAIN |
| 并行搜索 | 中层审核循环内串行→`asyncio.gather`并行，`_search_one()`异常内化 |
| SSE端点 | `POST /analyze/stream`(SSE) + `/analyze`(非SSE) + `GET /analyze/{id}`(恢复) |
| ProgressTracker | 12种事件类型贯穿全链路，tracker=None时静默跳过 |

## 🔜 未完成 — 当前阶段(Phase 2)

| 项目 | 说明 |
|------|------|
| **Agent化** | 中层LLM决定子Agent数量/搜索方向；Top LLM根据项目特征自定义中层(非固定5个)；驳回时修改instruction |

## 📅 未完成 — 未来阶段(Phase 3+)

| 项目 | 说明 |
|------|------|
| 前端SSE对接 | Next.js 消费 `/analyze/stream`，实时渲染进度条/部门卡片 |
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
- **熔断**: 30次LLM调用上限；每中层3轮驳回上限
- **防幻觉**: 每条结论必须有URL+原始关键句；无来源→标存疑；边界不清→追问
- **API文档**: `docs/api.md`
