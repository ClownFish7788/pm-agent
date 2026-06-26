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
from .nodes import node_top_planning, node_market_research, node_aggregate

# =============================================================================
# 节点名称常量（避免字符串硬编码拼写错误）
# =============================================================================

NODE_PLAN = "top_planning"          # 顶层规划
NODE_MARKET = "market_research"     # 市场调研
NODE_AGGREGATE = "aggregate"        # 汇总报告


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

    # node_aggregate 不需要 Provider（只读 state + print），直接用
    # 但签名要保持一致：async def fn(state) -> dict

    async def _node_aggregate(state: GlobalState) -> dict:
        """闭包包装：aggregate 节点不需要 Provider"""
        return await node_aggregate(state)

    # ---- 注册节点 ----
    # 每个节点函数签名：async def fn(state: GlobalState) -> dict
    builder.add_node(NODE_PLAN, _node_plan)
    builder.add_node(NODE_MARKET, _node_market)
    builder.add_node(NODE_AGGREGATE, _node_aggregate)

    # ---- 设置入口 ----
    builder.set_entry_point(NODE_PLAN)

    # ---- 连线 ----
    # 正常流程：plan → market
    builder.add_edge(NODE_PLAN, NODE_MARKET)

    # 条件边：market 执行完后，根据质量判断决定下一步
    # MVP 阶段 judge_market_quality() 始终返回 "pass"
    builder.add_conditional_edges(
        NODE_MARKET,
        judge_market_quality,
        {
            "pass": NODE_AGGREGATE,       # 合格 → 汇总
            "reject": NODE_MARKET,        # 驳回 → 回到 market 重做【Phase 2】
            "uncertain": NODE_AGGREGATE,  # 超限存疑 → 汇总【Phase 2】
        },
    )

    # 汇总完成后结束
    builder.add_edge(NODE_AGGREGATE, END)

    # ---- 编译 ----
    # compile() 验证图结构完整性并生成可执行对象
    graph = builder.compile()

    return graph
