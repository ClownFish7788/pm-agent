"""
底层研究员 Agent —— 数据采集、筛选和初步分析的最小单元。

职责（升级版）：
1. 调用 Search Provider（Tavily）执行一次搜索
2. 筛选：去掉低质、重复、广告、过时内容
3. 归类：按主题聚合相关结果，发现矛盾和共识
4. 撰写报告：≤500字综合分析，包含判断和缺口
5. 附索引：保留关键发现的 source_url，中层可回查

不再是纯数据提取器——有筛选、有判断、有报告。

使用示例：
    llm = DeepSeekProvider()
    search = TavilyProvider()
    agent = SearchAgent("market_query_1", llm, search)
    report = await agent.run(search_query="宠物社交App 市场规模 2025")
    # report.report 是研究报告，report.key_findings 是数据索引
"""

from __future__ import annotations

from llm.base import BaseLLMProvider
from prompts.templates import build_search_agent_prompt, format_search_results_for_prompt
from schemas import SearchOptions, BottomReport
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class SearchAgent:
    """底层研究员 Agent —— 搜索、筛选、归类、写报告。

    不保存状态 —— 每次 run() 是独立的幂等调用。
    状态由中层 SubAgentSlot 管理。

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
        self.agent_id = agent_id
        self.llm = llm
        self.search_provider = search_provider

    async def run(
        self,
        search_query: str,
        max_results: int = 5,
    ) -> BottomReport:
        """执行一次搜索调研。

        流程：
        1. 调 Tavily 搜索
        2. 格式化结果 → LLM 可读文本
        3. LLM 筛选 + 归类 + 撰写报告 → BottomReport

        参数：
            search_query：搜索关键词
            max_results：最多返回多少条原始结果

        返回：
            BottomReport（report + key_findings + total_sources）
        """
        print(f"\n  🔍 [{self.agent_id}] 开始搜索: \"{search_query}\"")

        # ---- 步骤 1：搜索 ----
        try:
            raw_results = await self.search_provider.search(
                query=search_query,
                options=SearchOptions(max_results=max_results),
            )
            print(f"  🔍 [{self.agent_id}] 搜索完成，返回 {len(raw_results)} 条结果")
        except Exception as e:
            log_error(self.agent_id, f"搜索失败: {type(e).__name__}: {e}")
            return BottomReport(
                report=f"搜索失败: {str(e)[:200]}",
                key_findings=[],
                total_sources=0,
            )

        if not raw_results:
            log_agent_output(
                agent_name=self.agent_id,
                agent_emoji="🔍",
                input_summary=f"搜索词: {search_query}",
                output={"report": "无搜索结果", "key_findings": [], "total_sources": 0},
            )
            return BottomReport(
                report=f"未找到与 '{search_query}' 相关的搜索结果。建议更换搜索词或扩展搜索范围。",
                key_findings=[],
                total_sources=0,
            )

        # ---- 步骤 2：格式化搜索结果 ----
        formatted_text = format_search_results_for_prompt(raw_results)

        # ---- 步骤 3：LLM 筛选 + 归类 + 撰写报告 ----
        messages = build_search_agent_prompt(
            search_query=search_query,
            raw_results_text=formatted_text,
            total_results=len(raw_results),
        )

        try:
            # 8192 tokens：研究报告（500字）+ 5条finding + JSON结构
            result = await self.llm.chat_structured(
                messages=messages,
                output_schema=BottomReport,
                max_tokens=8192,
            )
        except Exception as e:
            log_error(self.agent_id, f"LLM 调用失败: {type(e).__name__}: {e}")
            return BottomReport(
                report=f"LLM 分析失败: {str(e)[:200]}",
                key_findings=[],
                total_sources=len(raw_results),
            )

        # ---- 步骤 4：打印输出 ----
        log_agent_output(
            agent_name=self.agent_id,
            agent_emoji="🔍",
            input_summary=f"搜索词: {search_query} ({len(raw_results)} 条原始结果)",
            output={
                "report": result.report[:200] + "...",
                "key_findings_count": len(result.key_findings),
                "total_sources": result.total_sources,
            },
        )

        return result
