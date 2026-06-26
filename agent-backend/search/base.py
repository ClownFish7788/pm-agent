"""
Search Provider 抽象基类。

定义了所有搜索引擎 Provider 必须遵守的「合同」。
上层 Agent 只依赖这个抽象类，不关心底层是 Tavily、Google 还是 Bing。

类比：和 LLM Provider 一样的「插头标准」模式。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from schemas import SearchOptions, SearchResult


class BaseSearchProvider(ABC):
    """Search Provider 抽象基类 —— 所有搜索引擎的统一入口。

    每个具体 Provider 必须实现：
    - search()：执行搜索并返回统一的 SearchResult 列表
    """

    # ------------------------------------------------------------------
    # 子类必须填写的元信息
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称，如 'Tavily'、'Google'。

        用于日志打印和错误追踪。
        """
        ...

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    @abstractmethod
    async def search(
        self,
        query: str,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """执行搜索并返回统一格式的结果列表。

        参数：
            query：搜索关键词，如 "宠物社交App 市场规模 2025"
            options：搜索选项（最大结果数、域名过滤、搜索深度）。
                     None = 使用默认选项（5 条结果，basic 深度，无域名过滤）

        返回：
            list[SearchResult]：统一格式的搜索结果列表。
                               即使没有结果也返回空列表，不抛异常。

        用法：
            results = await provider.search(
                query="宠物经济 用户画像",
                options=SearchOptions(max_results=3, search_depth="advanced"),
            )
            for r in results:
                print(r.title, r.url, r.content[:100])
        """
        ...
