"""
Tavily Search Provider 实现。

使用 Tavily Search API 进行网络搜索。Tavily 是专为 AI Agent 设计的搜索 API，
返回结构化结果（标题、URL、摘要、相关度评分），非常适合 LLM 消费。

环境变量：
    TAVILY_API_KEY：Tavily API 密钥（必需）

使用示例：
    provider = TavilyProvider()
    results = await provider.search("宠物社交App 市场分析")
    for r in results:
        print(r.title, r.score)
"""

from __future__ import annotations

import os
from typing import Any

from schemas import SearchOptions, SearchResult

from .base import BaseSearchProvider

# Tavily Python SDK
try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None  # type: ignore[assignment]


class TavilyProvider(BaseSearchProvider):
    """Tavily Search API 的 Provider 实现。

    底层使用 tavily-python SDK。返回的原始结果会被转换为 SearchResult 格式，
    保证所有 Provider 输出格式统一。

    属性：
        provider_name：固定返回 "Tavily"
    """

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        """初始化 Tavily 客户端。

        参数：
            api_key：Tavily API 密钥。默认从环境变量 TAVILY_API_KEY 读取

        异常：
            ImportError：未安装 tavily-python 包
            ValueError：TAVILY_API_KEY 未设置
        """
        # ---- 检查依赖 ----
        if TavilyClient is None:
            raise ImportError(
                "tavily-python 包未安装！请运行:\n"
                "  pip install tavily-python\n"
                "或:\n"
                "  poetry add tavily-python"
            )

        # ---- 读取 API Key ----
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self._api_key:
            raise ValueError(
                "TAVILY_API_KEY 未设置！请设置环境变量或在初始化时传入 api_key 参数。\n"
                "  export TAVILY_API_KEY=tvly-xxxxx\n"
                "或:\n"
                "  provider = TavilyProvider(api_key='tvly-xxxxx')"
            )

        # ---- 创建 Tavily 客户端 ----
        self._client = TavilyClient(api_key=self._api_key)

    # ------------------------------------------------------------------
    # 接口实现
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """返回 Provider 名称"""
        return "Tavily"

    async def search(
        self,
        query: str,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """执行搜索并返回统一格式的结果。

        内部流程：
        1. 合并默认选项和用户选项
        2. 调用 Tavily SDK 的 search() 方法
        3. 将 Tavily 原始结果转换为 SearchResult（schemas 定义的标准格式）
        4. 返回转换后的列表

        参数说明见 BaseSearchProvider.search()。
        """
        # ---- 步骤 1：合并选项 ----
        opts = options or SearchOptions()  # None → 使用默认值

        # ---- 步骤 2：调用 Tavily API ----
        try:
            # Tavily SDK 是同步的，用 run_in_executor 不会阻塞事件循环
            # 对于 MVP 控制台脚本，直接同步调用更简单
            raw_response = self._client.search(
                query=query,
                search_depth=opts.search_depth,
                max_results=opts.max_results,
                include_domains=opts.include_domains if opts.include_domains else None,
                exclude_domains=opts.exclude_domains if opts.exclude_domains else None,
            )
        except Exception as e:
            raise RuntimeError(
                f"[{self.provider_name}] search() 调用失败: {type(e).__name__}: {e}"
            ) from e

        # ---- 步骤 3：转换为统一格式 ----
        results: list[SearchResult] = []
        raw_results: list[dict[str, Any]] = raw_response.get("results", [])

        for item in raw_results:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=float(item.get("score", 0.0)),
                published_date=item.get("published_date"),
            ))

        return results
