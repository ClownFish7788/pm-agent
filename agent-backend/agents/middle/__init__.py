"""
中层 Agent 包 —— 分析综合层。

职责：
- 调度底层 Agent（决定搜索什么、搜几次）
- 收集底层发现，调 LLM 综合分析
- 输出 AnalysisPoint[] + MarketResearchState
"""

from __future__ import annotations

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from schemas import BottomReport
from search.base import BaseSearchProvider
from utils.progress import ProgressTracker


async def _search_one(
    sub_id: str,
    query: str,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    department: str | None = None,
    tracker: ProgressTracker | None = None,
) -> tuple[str, BottomReport | None, str | None]:
    """执行一次搜索，永不抛异常 —— 异常内化为返回三元组的第三个元素。

    Args:
        sub_id: 子 Agent ID
        query: 搜索关键词
        llm: LLM Provider（共享实例）
        search_provider: Search Provider
        department: 所属部门名（用于 SSE 事件）
        tracker: ProgressTracker 或 None

    Returns:
        (sub_id, report_or_None, error_msg_or_None)
    """
    try:
        agent = SearchAgent(
            agent_id=sub_id,
            llm=llm,
            search_provider=search_provider,
            department=department,
            tracker=tracker,
        )
        report = await agent.run(search_query=query, max_results=5)
        return (sub_id, report, None)
    except Exception as exc:
        if tracker is not None:
            tracker.error(
                f"搜索异常: {type(exc).__name__}: {exc}",
                department=department,
                agent_id=sub_id,
            )
        return (sub_id, None, f"{type(exc).__name__}: {exc}")
