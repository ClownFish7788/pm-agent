"""
底层搜索 Agent —— 数据采集的最小单元。

职责：
1. 调用 Search Provider（Tavily）执行一次搜索
2. 将原始搜索结果格式化
3. 调 LLM 从搜索结果中提取结构化发现（SubAgentOutput）
4. 打印输出到控制台

这是整个 Agent 链的「数据源头」。每个底层 Agent 负责一个搜索方向，
中层 Leader 可以同时调度多个底层 Agent 覆盖不同维度。

使用示例：
    # 注入依赖（由外部创建，Agent 不自己 new Provider）
    llm = DeepSeekProvider()
    search = TavilyProvider()

    # 创建 Agent
    agent = SearchAgent(llm, search)

    # 执行一次搜索
    result = await agent.run(search_query="宠物社交App 市场规模 2025")
    # result 是 SubAgentOutput 实例
"""

from __future__ import annotations

from llm.base import BaseLLMProvider
from prompts.templates import build_search_agent_prompt, format_search_results_for_prompt
from schemas import SearchOptions, SubAgentOutput
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class SearchAgent:
    """底层搜索 Agent —— 执行一次搜索并从结果中提取关键发现。

    不保存状态 —— 每次 run() 是独立的、幂等的调用。
    状态（search_query、latest_output、status）由中层 SubAgentSlot 管理。

    属性：
        agent_id：唯一标识，如 "market_size_query"，用于日志
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（依赖注入）
    """

    def __init__(
        self,
        agent_id: str,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
    ) -> None:
        """初始化底层搜索 Agent。

        参数：
            agent_id：Agent 唯一标识，用于日志追踪
            llm：LLM Provider 实例（如 DeepSeekProvider）
            search_provider：Search Provider 实例（如 TavilyProvider）
        """
        self.agent_id = agent_id
        self.llm = llm
        self.search_provider = search_provider

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    async def run(
        self,
        search_query: str,
        max_results: int = 5,
    ) -> SubAgentOutput:
        """执行一次搜索并提取结构化发现。

        这是底层 Agent 的唯一对外接口。整个流程分三步：
        1. 搜索 → 调 Search Provider 获取原始结果
        2. 格式化 → 将 SearchResult 转为 LLM 可读的文本
        3. 提取 → 调 LLM 从文本中提取 SubAgentOutput

        参数：
            search_query：搜索关键词，如 "宠物社交App 市场规模 2025"
            max_results：最多返回多少条原始结果（默认 5）

        返回：
            SubAgentOutput 实例（summary + top_findings + total_results）
        """
        # ---- 步骤 0：打印开始 ----
        print(f"\n  🔍 [{self.agent_id}] 开始搜索: \"{search_query}\"")

        # ---- 步骤 1：搜索 ----
        try:
            raw_results = await self.search_provider.search(
                query=search_query,
                options=SearchOptions(max_results=max_results),
            )
            print(f"  🔍 [{self.agent_id}] 搜索完成，返回 {len(raw_results)} 条结果")
        except Exception as e:
            # 搜索失败：打印错误，返回一个「空壳」SubAgentOutput
            log_error(self.agent_id, f"搜索失败: {type(e).__name__}: {e}")
            return SubAgentOutput(
                summary=f"搜索失败: {str(e)[:80]}",
                top_findings=[],
                total_results=0,
            )

        # 如果没有搜索结果，提前返回
        if not raw_results:
            log_agent_output(
                agent_name=self.agent_id,
                agent_emoji="🔍",
                input_summary=f"搜索词: {search_query}",
                output={"summary": "无搜索结果", "top_findings": [], "total_results": 0},
            )
            return SubAgentOutput(
                summary=f"未找到与 '{search_query}' 相关的搜索结果",
                top_findings=[],
                total_results=0,
            )

        # ---- 步骤 2：格式化搜索结果 → LLM 可读文本 ----
        formatted_text = format_search_results_for_prompt(raw_results)

        # ---- 步骤 3：调 LLM 提取结构化发现 ----
        messages = build_search_agent_prompt(
            search_query=search_query,
            raw_results_text=formatted_text,
            total_results=len(raw_results),
        )

        try:
            result = await self.llm.chat_structured(
                messages=messages,
                output_schema=SubAgentOutput,
            )
        except Exception as e:
            log_error(self.agent_id, f"LLM 调用失败: {type(e).__name__}: {e}")
            return SubAgentOutput(
                summary=f"LLM 提取失败: {str(e)[:80]}",
                top_findings=[],
                total_results=len(raw_results),
            )

        # ---- 步骤 4：打印输出 ----
        log_agent_output(
            agent_name=self.agent_id,
            agent_emoji="🔍",
            input_summary=f"搜索词: {search_query} ({len(raw_results)} 条原始结果)",
            output=result.model_dump(),
        )

        return result
