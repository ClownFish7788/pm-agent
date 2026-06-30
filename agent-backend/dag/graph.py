"""
LangGraph StateGraph 组装与编译。

Phase 2 Agent化：从 10+ 节点简化为 3 节点。

    top_planning → execute_departments → aggregate → END

- execute_departments 内部读 plan.tasks，asyncio.gather 并发执行所有部门
- Top LLM 动态决定部门数量（3-7 个），Graph 结构不变
- Checkpoint：MemorySaver 整体断点（单请求内可恢复）

依赖注入：闭包捕获 llm + search_provider，包装成只收 state 的函数注册。
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from llm.base import BaseLLMProvider
from schemas import GlobalState
from search.base import BaseSearchProvider
from utils.progress import ProgressTracker

from .nodes import node_top_planning, node_execute_departments, node_aggregate

# =============================================================================
# 节点名称常量
# =============================================================================

NODE_PLAN = "top_planning"
NODE_EXECUTE = "execute_departments"
NODE_AGGREGATE = "aggregate"


# =============================================================================
# 图构建函数
# =============================================================================

def build_graph(
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    tracker: ProgressTracker | None = None,
) -> Any:
    """构建并编译 PM Agent 的 LangGraph 图（3 节点 + Checkpoint）。

    图结构：
        top_planning → execute_departments → aggregate → END

    execute_departments 内部：
        - 读 state.execution_plan.tasks
        - 根据 agent_type 选择预置或通用 config
        - asyncio.gather 并发执行所有部门
        - 结果写回 state.department_results
    """

    builder = StateGraph(GlobalState)

    # ---- 闭包装节点 ----
    async def _node_plan(state: GlobalState) -> dict:
        return await node_top_planning(state, llm, search_provider, tracker=tracker)

    async def _node_execute(state: GlobalState) -> dict:
        return await node_execute_departments(state, llm, search_provider, tracker=tracker)

    async def _node_aggregate(state: GlobalState) -> dict:
        return await node_aggregate(state, llm, tracker=tracker)

    # ---- 注册节点 ----
    builder.add_node(NODE_PLAN, _node_plan)
    builder.add_node(NODE_EXECUTE, _node_execute)
    builder.add_node(NODE_AGGREGATE, _node_aggregate)

    # ---- 连线 ----
    builder.set_entry_point(NODE_PLAN)
    builder.add_edge(NODE_PLAN, NODE_EXECUTE)
    builder.add_edge(NODE_EXECUTE, NODE_AGGREGATE)
    builder.add_edge(NODE_AGGREGATE, END)

    # ---- 编译 ----
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
