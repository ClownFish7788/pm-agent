"""
LangGraph StateGraph 组装与编译。

这是 DAG 的「施工图」—— 定义节点、连线、条件路由、checkpoint，最终编译为可执行对象。

MVP 图结构（5 中层并行 + Skip 路由 + Checkpoint）：

    top_planning ──┬──→ run_market ──────────────┐
                   ├──→ run_competitor ──────────┤
                   ├──→ run_product ─────────────┤
                   ├──→ run_future ──────────────┤
                   ├──→ run_change ──────────────┤
                   │                              ↓
                   │                         aggregate → END
                   │                              ↑
                   ├──→ skip_market ──────────────┤
                   ├──→ skip_competitor ──────────┤
                   ├──→ skip_product ─────────────┤
                   ├──→ skip_future ──────────────┤
                   └──→ skip_change ──────────────┘

Skip 路由：顶层 plan.skipped 中包含的部门 → 走 skip_xxx 节点（返回 SKIPPED 状态）
条件边函数是纯代码，不调 LLM。

Checkpoint：MemorySaver 内置断点存储，分析中断后可用相同 thread_id 恢复。

依赖注入说明：
    LangGraph 的 add_node() 只给节点函数传 state 一个参数。
    但我们的节点函数需要 llm + search_provider（由外部创建）。
    解决方案：用闭包捕获 Provider，包装成只收 state 的函数再注册。

使用方式：
    from dag.graph import build_graph

    llm = DeepSeekProvider()
    search = TavilyProvider()
    graph = build_graph(llm, search)

    # 首次执行
    config = {"configurable": {"thread_id": "session-001"}}
    final_state = await graph.ainvoke(initial_state, config)

    # 中断后恢复（自动从最后一个 checkpoint 继续）
    final_state = await graph.ainvoke(None, config)
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from llm.base import BaseLLMProvider
from schemas import (
    AgentStatus,
    ChangeState,
    CompetitorState,
    FutureState,
    GlobalState,
    MarketResearchState,
    MiddleAgentType,
    ProductDesignState,
)
from search.base import BaseSearchProvider

from .nodes import (
    node_top_planning,
    node_market_research,
    node_competitor_analysis,
    node_product_design,
    node_future_direction,
    node_change_plan,
    node_aggregate,
)

# =============================================================================
# 节点名称常量（避免字符串硬编码拼写错误）
# =============================================================================

# ⚠️ 节点名称不能与 State 字段名相同（LangGraph 会报 ValueError）
# State 有 market_research/competitor_analysis/... 字段
# 所以节点名用动词前缀区分：run_xxx / skip_xxx
NODE_PLAN = "top_planning"
NODE_MARKET = "run_market_research"
NODE_COMPETITOR = "run_competitor_analysis"
NODE_PRODUCT = "run_product_design"
NODE_FUTURE = "run_future_direction"
NODE_CHANGE = "run_change_plan"
NODE_AGGREGATE = "aggregate"

# Skip 节点（顶层决定跳过某部门时走这里）
NODE_SKIP_MARKET = "skip_market_research"
NODE_SKIP_COMPETITOR = "skip_competitor_analysis"
NODE_SKIP_PRODUCT = "skip_product_design"
NODE_SKIP_FUTURE = "skip_future_direction"
NODE_SKIP_CHANGE = "skip_change_plan"


# =============================================================================
# 图构建函数
# =============================================================================

def build_graph(
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> Any:
    """构建并编译 PM Agent 的 LangGraph 图（含 Skip 路由 + Checkpoint）。

    参数：
        llm：LLM Provider 实例（依赖注入）
        search_provider：Search Provider 实例（依赖注入）

    返回：
        编译后的 CompiledStateGraph，可调用 .ainvoke(state, config) 执行

    执行方式：
        llm = DeepSeekProvider()
        search = TavilyProvider()
        graph = build_graph(llm, search)

        # 首次执行
        config = {"configurable": {"thread_id": "my-session"}}
        final_state = await graph.ainvoke(GlobalState(project=...), config)

        # 中断后恢复（自动从最后一个 checkpoint 继续）
        # final_state = await graph.ainvoke(None, config)
    """
    # ---- 创建 StateGraph ----
    builder = StateGraph(GlobalState)

    # ---- 创建包装函数（闭包注入依赖） ----
    # LangGraph 要求节点函数签名是 async def fn(state) -> dict
    # 但我们的节点需要额外的 llm 和 search_provider 参数
    # 解决办法：在 build_graph() 中创建闭包，提前绑定 Provider

    async def _node_plan(state: GlobalState) -> dict:
        return await node_top_planning(state, llm, search_provider)

    async def _node_market(state: GlobalState) -> dict:
        return await node_market_research(state, llm, search_provider)

    async def _node_competitor(state: GlobalState) -> dict:
        return await node_competitor_analysis(state, llm, search_provider)

    async def _node_product(state: GlobalState) -> dict:
        return await node_product_design(state, llm, search_provider)

    async def _node_future(state: GlobalState) -> dict:
        return await node_future_direction(state, llm, search_provider)

    async def _node_change(state: GlobalState) -> dict:
        return await node_change_plan(state, llm, search_provider)

    async def _node_aggregate(state: GlobalState) -> dict:
        return await node_aggregate(state, llm)

    # ===== Skip 节点闭包 =====
    # 被顶层跳过的部门 → 返回 SKIPPED 状态，聚合节点可展示跳过原因
    # 纯代码节点，不调 LLM

    async def _node_skip_market(state: GlobalState) -> dict:
        plan = state.execution_plan
        reason = plan.skip_reasons.get("market_research", "") if plan else ""
        msg = f"⏭️ 顶层计划跳过: {reason}" if reason else "⏭️ 顶层计划跳过（该分析方向不适用于当前项目）"
        return {
            "market_research": MarketResearchState(
                summary=msg,
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.SKIPPED,
            )
        }

    async def _node_skip_competitor(state: GlobalState) -> dict:
        plan = state.execution_plan
        reason = plan.skip_reasons.get("competitor_analysis", "") if plan else ""
        msg = f"⏭️ 顶层计划跳过: {reason}" if reason else "⏭️ 顶层计划跳过"
        return {
            "competitor_analysis": CompetitorState(
                summary=msg,
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.SKIPPED,
            )
        }

    async def _node_skip_product(state: GlobalState) -> dict:
        plan = state.execution_plan
        reason = plan.skip_reasons.get("product_design", "") if plan else ""
        msg = f"⏭️ 顶层计划跳过: {reason}" if reason else "⏭️ 顶层计划跳过"
        return {
            "product_design": ProductDesignState(
                summary=msg,
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.SKIPPED,
            )
        }

    async def _node_skip_future(state: GlobalState) -> dict:
        plan = state.execution_plan
        reason = plan.skip_reasons.get("future_direction", "") if plan else ""
        msg = f"⏭️ 顶层计划跳过: {reason}" if reason else "⏭️ 顶层计划跳过"
        return {
            "future_direction": FutureState(
                summary=msg,
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.SKIPPED,
            )
        }

    async def _node_skip_change(state: GlobalState) -> dict:
        plan = state.execution_plan
        reason = plan.skip_reasons.get("change_plan", "") if plan else ""
        msg = f"⏭️ 顶层计划跳过: {reason}" if reason else "⏭️ 顶层计划跳过"
        return {
            "change_plan": ChangeState(
                summary=msg,
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.SKIPPED,
            )
        }

    # ---- 注册全部节点 ----
    builder.add_node(NODE_PLAN, _node_plan)
    builder.add_node(NODE_MARKET, _node_market)
    builder.add_node(NODE_COMPETITOR, _node_competitor)
    builder.add_node(NODE_PRODUCT, _node_product)
    builder.add_node(NODE_FUTURE, _node_future)
    builder.add_node(NODE_CHANGE, _node_change)
    builder.add_node(NODE_AGGREGATE, _node_aggregate)

    # Skip 节点
    builder.add_node(NODE_SKIP_MARKET, _node_skip_market)
    builder.add_node(NODE_SKIP_COMPETITOR, _node_skip_competitor)
    builder.add_node(NODE_SKIP_PRODUCT, _node_skip_product)
    builder.add_node(NODE_SKIP_FUTURE, _node_skip_future)
    builder.add_node(NODE_SKIP_CHANGE, _node_skip_change)

    # ---- 设置入口 ----
    builder.set_entry_point(NODE_PLAN)

    # ---- Skip 路由：条件边（纯代码判断，不调 LLM） ----
    # PLANNING → 根据 plan.skipped 决定走真实节点还是 skip 节点
    # 返回 list = LangGraph 自动 fan-out 并行执行

    _AGENT_TO_NODES: list[tuple[MiddleAgentType, str, str]] = [
        (MiddleAgentType.MARKET_RESEARCH, NODE_MARKET, NODE_SKIP_MARKET),
        (MiddleAgentType.COMPETITOR_ANALYSIS, NODE_COMPETITOR, NODE_SKIP_COMPETITOR),
        (MiddleAgentType.PRODUCT_DESIGN, NODE_PRODUCT, NODE_SKIP_PRODUCT),
        (MiddleAgentType.FUTURE_DIRECTION, NODE_FUTURE, NODE_SKIP_FUTURE),
        (MiddleAgentType.CHANGE_PLAN, NODE_CHANGE, NODE_SKIP_CHANGE),
    ]

    def _route_middle(state: GlobalState) -> list[str]:
        """纯代码路由：检查 plan.skipped，决定每个部门走真实 or skip 节点。

        LangGraph 条件边函数返回 list 时自动 fan-out 并行。
        """
        plan = state.execution_plan
        if plan is None:
            # 无计划 → 全部执行（兜底）
            return [node for _, node, _ in _AGENT_TO_NODES]

        skipped = set(plan.skipped)
        routes: list[str] = []
        for agent_type, real_node, skip_node in _AGENT_TO_NODES:
            if agent_type in skipped:
                routes.append(skip_node)
            else:
                routes.append(real_node)
        return routes

    # 条件边 path_map：列出所有可能的目的地
    _ALL_MIDDLE_NODES = [n for pair in _AGENT_TO_NODES for n in (pair[1], pair[2])]
    _ROUTE_MAP = {name: name for name in _ALL_MIDDLE_NODES}

    builder.add_conditional_edges(NODE_PLAN, _route_middle, _ROUTE_MAP)

    # ---- 汇聚到 AGGREGATE ----
    # 所有中间节点（真实 + skip）都指向 aggregate
    for node in _ALL_MIDDLE_NODES:
        builder.add_edge(node, NODE_AGGREGATE)

    # 汇总完成后结束（LangGraph 自动等待所有中层都完成才执行 aggregate）
    builder.add_edge(NODE_AGGREGATE, END)

    # ---- 编译（含 MemorySaver Checkpoint） ----
    # MemorySaver：内存级 checkpoint 存储
    # - 每个节点执行后自动保存状态
    # - 中断后用相同 thread_id 调用 ainvoke(None, config) 恢复
    # - Phase 3 可升级为 SqliteSaver 持久化到磁盘
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    return graph
