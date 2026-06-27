"""
中层未来方向 Leader Agent。

职责：
1. 接收顶层下发的项目信息 + 关注方向
2. 根据关注方向生成 1-3 个未来趋势搜索关键词
3. 每个关键词调度一个底层 SearchAgent
4. 收集底层发现，调 LLM 综合分析
5. 填充 FutureState 的 Public 字段
6. 打印中间过程和最终输出

MVP 简化：
- 只生成 1-2 个搜索词
- 不分步处理（一次性喂给 LLM）
- 不启用驳回逻辑
- 未来部门天然低可信度（0.4-0.7 正常）

使用示例：
    leader = FutureLeader(llm, search)
    state = await leader.run(project_summary="宠物社交App", focus_areas=["技术趋势", "市场演进"])
"""

from __future__ import annotations

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from prompts.templates import build_future_leader_prompt
from schemas import (
    DepartmentTask,
    FutureState,
    SubAgentSlot,
    AgentStatus,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class FutureLeader:
    """未来方向中层 Leader。

    管理底层搜索 Agent，综合趋势数据为未来战略报告。
    这是最推测性的部门——数据天然少，低置信度正常。

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
        task: DepartmentTask,
    ) -> FutureState:
        """执行未来方向分析。"""
        search_queries = self._generate_search_queries(task, project_summary)
        print(f"  🔮 [FutureLeader] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"future_query_{i + 1}"
            sub_agent = SearchAgent(
                agent_id=sub_id,
                llm=self.llm,
                search_provider=self.search_provider,
            )
            sub_output = await sub_agent.run(
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
        messages = build_future_leader_prompt(
            project_summary=project_summary,
            findings_text=findings_text,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=FutureState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error("FutureLeader", f"LLM 综合分析失败: {type(e).__name__}: {e}")
            return FutureState(
                summary=f"未来方向分析失败: {str(e)[:200]}",
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.UNCERTAIN,
                project={"summary": project_summary},
                sub_agents=sub_slots,
                cycle_count=0,
            )

        state = FutureState(
            summary=raw_result.summary,
            key_points=raw_result.key_points,
            overall_confidence=raw_result.overall_confidence,
            status=AgentStatus.PASSED,
            project={"summary": project_summary},
            sub_agents=sub_slots,
            cycle_count=0,
        )

        log_agent_output(
            agent_name="FutureLeader",
            agent_emoji="🔮",
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

    def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        """根据 Top Agent 下发的 core_topic + focus_areas 生成未来趋势搜索关键词。"""
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
            parts.append(f"研究报告: {output.report}")
            parts.append(f"共 {len(output.key_findings)} 条发现:")
            parts.append("")

            for finding in output.key_findings:
                parts.append(f"  [{finding_index}] {finding.insight}")
                parts.append(f"      来源: {finding.source_url}")
                parts.append(f"      类型: {finding.source_type} | 相关度: {finding.relevance} | 可信度: {finding.confidence}")
                parts.append("")
                finding_index += 1

        parts.append(f"--- 以上共 {finding_index} 条发现 ---")
        return "\n".join(parts)
