"""
中层竞品分析 Leader Agent。

职责：
1. 接收顶层下发的项目信息 + 关注方向
2. 根据关注方向生成 1-3 个竞品搜索关键词
3. 每个关键词调度一个底层 SearchAgent
4. 收集底层发现，调 LLM 综合分析
5. 填充 CompetitorState 的 Public 字段
6. 打印中间过程和最终输出

MVP 简化：
- 只生成 1-2 个搜索词（不是 3 个）
- 不分步处理（一次性喂给 LLM）
- 不启用驳回逻辑

使用示例：
    llm = DeepSeekProvider()
    search = TavilyProvider()

    leader = CompetitorLeader(llm, search)
    state = await leader.run(project_summary="宠物社交App", focus_areas=["直接竞品", "功能对比"])
    # state.key_points 是整理好的竞品分析要点
"""

from __future__ import annotations

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from prompts.templates import build_competitor_leader_prompt
from schemas import (
    AnalysisPoint,
    CompetitorState,
    DepartmentTask,
    SubAgentSlot,
    AgentStatus,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class CompetitorLeader:
    """竞品分析中层 Leader。

    管理底层搜索 Agent，综合多源发现为竞品分析报告。

    属性：
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（依赖注入，传给底层 Agent）
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
    ) -> None:
        """初始化竞品分析 Leader。

        参数：
            llm：LLM Provider 实例
            search_provider：Search Provider 实例（会传给底层 SearchAgent 用）
        """
        self.llm = llm
        self.search_provider = search_provider

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    async def run(
        self,
        project_summary: str,
        task: DepartmentTask,
    ) -> CompetitorState:
        """执行竞品分析。

        流程：
        1. 根据关注方向生成搜索关键词
        2. 每个关键词并行创建底层 SearchAgent
        3. 收集所有 SubAgentOutput
        4. 调 LLM 综合分析 → AnalysisPoint[]
        5. 填充 CompetitorState

        参数：
            project_summary：项目描述摘要（来自顶层 Agent）
            focus_areas：关注维度列表，如 ["直接竞品", "功能对比", "差异化机会"]

        返回：
            CompetitorState 实例（Public 字段已填充）
        """
        # ---- 步骤 1：生成搜索关键词 ----
        search_queries = self._generate_search_queries(task, project_summary)
        print(f"  🏢 [CompetitorLeader] 准备搜索 {len(search_queries)} 个方向:")

        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：调度底层 Agent（MVP：串行执行，Phase 2 改并行） ----
        sub_slots: dict[str, SubAgentSlot] = {}

        for i, query in enumerate(search_queries):
            sub_id = f"competitor_query_{i + 1}"
            sub_agent = SearchAgent(
                agent_id=sub_id,
                llm=self.llm,
                search_provider=self.search_provider,
            )

            sub_output = await sub_agent.run(
                search_query=query,
                max_results=5,
            )

            sub_slots[sub_id] = SubAgentSlot(
                sub_id=sub_id,
                search_query=query,
                latest_output=sub_output,
                round_number=1,
                rejection_log=[],
                status=AgentStatus.PASSED,
            )

        # ---- 步骤 3：汇总底层发现 → 格式化文本 ----
        findings_text = self._format_all_findings(sub_slots)

        # ---- 步骤 4：调 LLM 综合分析 ----
        messages = build_competitor_leader_prompt(
            project_summary=project_summary,
            findings_text=findings_text,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=CompetitorState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error("CompetitorLeader", f"LLM 综合分析失败: {type(e).__name__}: {e}")
            return CompetitorState(
                summary=f"竞品分析失败: {str(e)[:200]}",
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.UNCERTAIN,
                project={"summary": project_summary},
                sub_agents=sub_slots,
                cycle_count=0,
            )

        # ---- 步骤 5：补填 Internal 字段 ----
        state = CompetitorState(
            summary=raw_result.summary,
            key_points=raw_result.key_points,
            overall_confidence=raw_result.overall_confidence,
            status=AgentStatus.PASSED,
            project={"summary": project_summary},
            sub_agents=sub_slots,
            cycle_count=0,
        )

        # ---- 步骤 6：打印输出 ----
        log_agent_output(
            agent_name="CompetitorLeader",
            agent_emoji="🏢",
            input_summary=f"项目: {project_summary[:100]} | 搜索方向: {len(search_queries)} 个 | 关注: {task.focus_areas}",
            output={
                "summary": state.summary[:200] if state.summary else "无",
                "key_points_count": len(state.key_points),
                "key_points": [kp.title for kp in state.key_points],
                "overall_confidence": state.overall_confidence,
                "sub_agents": {
                    sid: {
                        "query": slot.search_query,
                        "status": slot.status.value,
                        "findings_count": len(slot.latest_output.key_findings) if slot.latest_output else 0,
                    }
                    for sid, slot in sub_slots.items()
                },
            },
        )

        return state

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        """根据 Top Agent 下发的 core_topic + focus_areas 生成竞品搜索关键词。

        参数：
            task：Top Agent 下发的专属任务（含 core_topic + focus_areas）
            project_summary：项目描述（仅当 core_topic 为空时 fallback 用）

        返回：
            搜索关键词列表（1-2 个）
        """
        queries: list[str] = []
        if task.core_topic:
            core_topic = task.core_topic
        elif project_summary:
            core_topic = project_summary[:10] if len(project_summary) > 10 else project_summary
        else:
            core_topic = ""

        for area in task.focus_areas[:2]:
            prefix = f"{core_topic} " if core_topic else ""
            queries.append(f"{prefix}{area}")

        return queries

    def _format_all_findings(
        self,
        sub_slots: dict[str, SubAgentSlot],
    ) -> str:
        """将所有底层 Agent 的发现格式化为一段文本。

        中层 Leader 将此文本喂给 LLM 做综合分析。

        参数：
            sub_slots：底层 Agent 管理槽字典

        返回：
            格式化的多行文本
        """
        parts: list[str] = []
        finding_index = 0

        for sub_id, slot in sub_slots.items():
            parts.append(f"=== 搜索方向: {slot.search_query} ===")
            parts.append(f"Agent ID: {sub_id}")

            if slot.latest_output is None:
                parts.append("(无结果)")
                continue

            output = slot.latest_output
            parts.append(f"研究报告: {output.report}")
            parts.append(f"共 {len(output.key_findings)} 条发现:")
            parts.append("")

            for j, finding in enumerate(output.key_findings):
                parts.append(f"  [{finding_index}] {finding.insight}")
                parts.append(f"      来源: {finding.source_url}")
                parts.append(f"      类型: {finding.source_type} | 相关度: {finding.relevance} | 可信度: {finding.confidence}")
                parts.append("")
                finding_index += 1

        parts.append(f"--- 以上共 {finding_index} 条发现 ---")
        return "\n".join(parts)
