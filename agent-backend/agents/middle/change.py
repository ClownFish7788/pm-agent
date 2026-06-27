"""
中层当下改变 Leader Agent。

职责：
1. 接收顶层下发的项目信息 + 关注方向
2. 根据关注方向生成 1-3 个启动策略搜索关键词
3. 每个关键词调度一个底层 SearchAgent
4. 收集底层发现，调 LLM 综合分析
5. 填充 ChangeState 的 Public 字段
6. 打印中间过程和最终输出

MVP 简化：
- 只生成 1-2 个搜索词
- 不分步处理（一次性喂给 LLM）
- 不启用驳回逻辑

使用示例：
    leader = ChangeLeader(llm, search)
    state = await leader.run(project_summary="宠物社交App", focus_areas=["冷启动", "资源需求"])
"""

from __future__ import annotations

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from prompts.templates import build_change_leader_prompt
from schemas import (
    ChangeState,
    SubAgentOutput,
    SubAgentSlot,
    AgentStatus,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class ChangeLeader:
    """当下改变中层 Leader。

    管理底层搜索 Agent，综合启动数据为行动清单。
    关注"今天该干什么"——最务实的中层。

    属性：
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（依赖注入，传给底层 Agent）
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider

    async def run(
        self,
        project_summary: str,
        focus_areas: list[str],
    ) -> ChangeState:
        """执行当下改变分析。"""
        search_queries = self._generate_search_queries(project_summary, focus_areas)
        print(f"  ⚡ [ChangeLeader] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"change_query_{i + 1}"
            sub_agent = SearchAgent(
                agent_id=sub_id,
                llm=self.llm,
                search_provider=self.search_provider,
            )
            sub_output: SubAgentOutput = await sub_agent.run(
                search_query=query, max_results=5
            )
            sub_slots[sub_id] = SubAgentSlot(
                sub_id=sub_id,
                search_query=query,
                latest_output=sub_output,
                round_number=1,
                rejection_log=[],
                status=AgentStatus.PASSED,
            )

        findings_text = self._format_all_findings(sub_slots)
        messages = build_change_leader_prompt(
            project_summary=project_summary,
            findings_text=findings_text,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=ChangeState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error("ChangeLeader", f"LLM 综合分析失败: {type(e).__name__}: {e}")
            return ChangeState(
                summary=f"当下改变分析失败: {str(e)[:200]}",
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.UNCERTAIN,
                project={"summary": project_summary},
                sub_agents=sub_slots,
                cycle_count=0,
            )

        state = ChangeState(
            summary=raw_result.summary,
            key_points=raw_result.key_points,
            overall_confidence=raw_result.overall_confidence,
            status=AgentStatus.PASSED,
            project={"summary": project_summary},
            sub_agents=sub_slots,
            cycle_count=0,
        )

        log_agent_output(
            agent_name="ChangeLeader",
            agent_emoji="⚡",
            input_summary=f"项目: {project_summary[:100]} | 搜索方向: {len(search_queries)} 个 | 关注: {focus_areas}",
            output={
                "summary": state.summary[:200] if state.summary else "无",
                "key_points_count": len(state.key_points),
                "key_points": [kp.title for kp in state.key_points],
                "overall_confidence": state.overall_confidence,
                "sub_agents": {
                    sid: {
                        "query": slot.search_query,
                        "status": slot.status.value,
                        "findings_count": len(slot.latest_output.top_findings) if slot.latest_output else 0,
                    }
                    for sid, slot in sub_slots.items()
                },
            },
        )

        return state

    def _generate_search_queries(
        self,
        project_summary: str,
        focus_areas: list[str],
    ) -> list[str]:
        queries: list[str] = []
        core_topic = project_summary[:10] if len(project_summary) > 10 else project_summary

        if focus_areas:
            for area in focus_areas[:2]:
                queries.append(f"{core_topic} {area} 启动 策略 2025")

        if not queries:
            queries.append(f"{core_topic} 冷启动 增长策略 必要条件 2025")

        return queries

    def _format_all_findings(self, sub_slots: dict[str, SubAgentSlot]) -> str:
        parts: list[str] = []
        finding_index = 0

        for sub_id, slot in sub_slots.items():
            parts.append(f"=== 搜索方向: {slot.search_query} ===")
            parts.append(f"Agent ID: {sub_id}")

            if slot.latest_output is None:
                parts.append("(无结果)")
                continue

            output = slot.latest_output
            parts.append(f"总结: {output.summary}")
            parts.append(f"共 {len(output.top_findings)} 条发现:")
            parts.append("")

            for finding in output.top_findings:
                parts.append(f"  [{finding_index}] {finding.insight}")
                parts.append(f"      来源: {finding.source_url}")
                parts.append(f"      类型: {finding.source_type} | 相关度: {finding.relevance} | 可信度: {finding.confidence}")
                parts.append("")
                finding_index += 1

        parts.append(f"--- 以上共 {finding_index} 条发现 ---")
        return "\n".join(parts)
