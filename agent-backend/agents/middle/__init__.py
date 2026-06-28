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


async def _search_one(
    sub_id: str,
    query: str,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> tuple[str, BottomReport | None, str | None]:
    """执行一次搜索，永不抛异常 —— 异常内化为返回三元组的第三个元素。

    设计要点：
    - 异常被内部 try/except 捕获，不向外传播导致其他 task 结果丢失
    - sub_id 始终由函数返回，不依赖 zip 索引对应，gather 顺序变化也不影响匹配
    - 调用侧通过三元组判断：error 非 None → 标记 UNCERTAIN

    Args:
        sub_id: 子 Agent ID
        query: 搜索关键词
        llm: LLM Provider（共享实例，asyncio 单线程下 call_count += 1 安全）
        search_provider: Search Provider

    Returns:
        (sub_id, report_or_None, error_msg_or_None)
        恰好一个非 None：要么 report 有值，要么 error_msg 有值
    """
    try:
        agent = SearchAgent(
            agent_id=sub_id,
            llm=llm,
            search_provider=search_provider,
        )
        report = await agent.run(search_query=query, max_results=5)
        return (sub_id, report, None)
    except Exception as exc:
        return (sub_id, None, f"{type(exc).__name__}: {exc}")
