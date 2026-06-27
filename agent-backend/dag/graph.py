"""
LangGraph StateGraph 组装与编译。

这是 DAG 的「施工图」—— 定义节点、连线、条件路由，最终编译为可执行对象。

MVP 图结构（3 节点线性）：
    node_top_planning ──→ node_market_research ──→ node_aggregate
                                  ↑
                                  └── (条件边: 质量判断)
                                        ├── "pass" → node_aggregate  (MVP：始终走这里)
                                        ├── "reject" → node_market_research 【Phase 2】
                                        └── "uncertain" → node_aggregate 【Phase 2】

使用 LangGraph StateGraph 的好处（vs 手写 if-else）：
- 自动并行 fan-out（同一 source → 多个 target，Phase 2 启用）
- 内置 checkpoint（分析中断可从断点恢复）
- 条件边清晰可读（graph 图 = 文档）
- 未来改 DAG 结构时只改图定义，不改节点函数

依赖注入说明：
    LangGraph 的 add_node() 只给节点函数传 state 一个参数。
    但我们的节点函数需要 llm + search_provider（由外部创建）。
    解决方案：用闭包捕获 Provider，包装成只收 state 的函数再注册。

使用方式：
    from dag.graph import build_graph

    llm = DeepSeekProvider()
    search = TavilyProvider()
    graph = build_graph(llm, search)  # Provider 在这里注入
    final_state = await graph.ainvoke(GlobalState(...))
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from langgraph.graph import StateGraph, END

from llm.base import BaseLLMProvider
from schemas import GlobalState
from search.base import BaseSearchProvider

from .conditions import judge_market_quality
from .nodes import node_top_planning, node_market_research, node_competitor_analysis, node_aggregate

# =============================================================================
# 节点名称常量（避免字符串硬编码拼写错误）
# =============================================================================

# ⚠️ 节点名称不能与 State 字段名相同（LangGraph 会报 ValueError）
# State 有 market_research/competitor_analysis/... 字段
# 所以节点名用动词前缀区分：run_xxx
NODE_PLAN = "top_planning"              # 顶层规划
NODE_MARKET = "run_market_research"     # 执行市场调研
NODE_COMPETITOR = "run_competitor_analysis"  # 执行竞品分析
NODE_AGGREGATE = "aggregate"            # 汇总报告


# =============================================================================
# 图构建函数
# =============================================================================

def build_graph(
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> Any:
    """构建并编译 PM Agent 的 LangGraph 图。

    参数：
        llm：LLM Provider 实例（依赖注入）
        search_provider：Search Provider 实例（依赖注入）

    返回：
        编译后的 CompiledStateGraph，可调用 .ainvoke(state) 执行

    执行方式：
        llm = DeepSeekProvider()
        search = TavilyProvider()
        graph = build_graph(llm, search)
        final_state = await graph.ainvoke(
            GlobalState(project=ProjectInfo(description="用户项目描述"))
        )
    """
    # ---- 创建 StateGraph ----
    # StateGraph 接收 Pydantic 模型作为 State Schema
    builder = StateGraph(GlobalState)

    # ---- 创建包装函数（闭包注入依赖） ----
    # LangGraph 要求节点函数签名是 async def fn(state) -> dict
    # 但我们的节点需要额外的 llm 和 search_provider 参数
    # 解决办法：在 build_graph() 中创建闭包，提前绑定 Provider

    async def _node_plan(state: GlobalState) -> dict:
        """闭包包装：注入 llm + search_provider"""
        return await node_top_planning(state, llm, search_provider)

    async def _node_market(state: GlobalState) -> dict:
        """闭包包装：注入 llm + search_provider"""
        return await node_market_research(state, llm, search_provider)

    async def _node_competitor(state: GlobalState) -> dict:
        """闭包包装：注入 llm + search_provider"""
        return await node_competitor_analysis(state, llm, search_provider)

    # node_aggregate 不需要 Provider（只读 state + print），直接用
    # 但签名要保持一致：async def fn(state) -> dict

    async def _node_aggregate(state: GlobalState) -> dict:
        """闭包包装：aggregate 节点不需要 Provider"""
        return await node_aggregate(state)

    # ---- 注册节点 ----
    builder.add_node(NODE_PLAN, _node_plan)
    builder.add_node(NODE_MARKET, _node_market)
    builder.add_node(NODE_COMPETITOR, _node_competitor)
    builder.add_node(NODE_AGGREGATE, _node_aggregate)

    # ---- 设置入口 ----
    builder.set_entry_point(NODE_PLAN)

    # ---- 连线（并行 DAG） ----
    # plan → market 和 plan → competitor 同时 fan-out（LangGraph 自动并行）
    builder.add_edge(NODE_PLAN, NODE_MARKET)
    builder.add_edge(NODE_PLAN, NODE_COMPETITOR)

    # 条件边：market 执行完后，根据质量判断决定下一步
    # MVP 阶段 judge_market_quality() 始终返回 "pass"
    builder.add_conditional_edges(
        NODE_MARKET,
        judge_market_quality,
        {
            "pass": NODE_AGGREGATE,
            "reject": NODE_MARKET,        # 【Phase 2】
            "uncertain": NODE_AGGREGATE,  # 【Phase 2】
        },
    )

    # 竞品分析完成后直接到汇总
    builder.add_edge(NODE_COMPETITOR, NODE_AGGREGATE)

    # 汇总完成后结束（LangGraph 自动等待 market 和 competitor 都完成）
    builder.add_edge(NODE_AGGREGATE, END)

    # ---- 编译 ----
    # compile() 验证图结构完整性并生成可执行对象
    graph = builder.compile()

    return graph
