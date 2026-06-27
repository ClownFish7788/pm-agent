"""
中层市场调研 Leader Agent。

职责：
1. 接收顶层下发的项目信息 + 关注方向
2. 根据关注方向生成 1-3 个搜索关键词
3. 每个关键词调度一个底层 SearchAgent
4. 审核底层报告质量 → 低分驳回重做（最多 3 轮）
5. 收集底层发现，调 LLM 综合分析
6. 填充 MarketResearchState 的 Public 字段
7. 打印中间过程和最终输出

Phase 2 新增：
- 审核 + 驳回循环（SubAgentReview + ReviewResult）
- 四维打分（completeness/credibility/freshness/relevance）
- 超限标记 UNCERTAIN

使用示例：
    llm = DeepSeekProvider()
    search = TavilyProvider()

    leader = MarketLeader(llm, search)
    state = await leader.run(project_summary="宠物社交App", task=DepartmentTask(...))
    # state.key_points 是整理好的分析要点
"""

from __future__ import annotations

from datetime import datetime, timezone

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from prompts.templates import build_market_leader_prompt, build_review_prompt
from schemas import (
    AnalysisPoint,
    AgentStatus,
    DepartmentTask,
    MarketResearchState,
    RejectionEntry,
    ReviewResult,
    SubAgentReview,
    SubAgentSlot,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error


class MarketLeader:
    """市场调研中层 Leader。

    管理底层搜索 Agent，审核报告质量，综合多源发现为市场分析报告。

    属性：
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（依赖注入，传给底层 Agent）
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
    ) -> None:
        """初始化市场调研 Leader。

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
    ) -> MarketResearchState:
        """执行市场调研分析（含审核 + 驳回循环）。

        参数：
            project_summary：项目描述摘要（来自顶层 Agent）
            task：顶层下发的专属任务（含 focus_areas + instruction + core_topic）

        返回：
            MarketResearchState 实例
        """
        # ---- 步骤 1：生成搜索关键词 ----
        search_queries = self._generate_search_queries(task, project_summary)
        print(f"  📊 [MarketLeader] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：初始化子 Agent 卡槽 ----
        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"market_query_{i + 1}"
            sub_slots[sub_id] = SubAgentSlot(
                sub_id=sub_id,
                search_query=query,
                latest_output=None,
                round_number=0,
                rejection_log=[],
                status=AgentStatus.IDLE,
            )

        # ---- 步骤 3：审核 + 驳回循环（最多 3 轮） ----
        max_cycles = 3
        cycle_count = 0

        for cycle in range(1, max_cycles + 1):
            cycle_count = cycle

            # 3a：找出本轮需要执行的子 Agent
            pending_ids = [
                sid for sid, slot in sub_slots.items()
                if slot.status in (AgentStatus.IDLE, AgentStatus.REJECTED)
            ]
            if not pending_ids:
                break

            print(f"  📊 [MarketLeader] 第 {cycle}/{max_cycles} 轮审核 — "
                  f"待执行: {len(pending_ids)} 个子 Agent")

            # 3b：执行搜索
            for sub_id in pending_ids:
                slot = sub_slots[sub_id]
                print(f"      🔍 {sub_id}: {slot.search_query}")
                sub_agent = SearchAgent(
                    agent_id=sub_id,
                    llm=self.llm,
                    search_provider=self.search_provider,
                )
                slot.latest_output = await sub_agent.run(
                    search_query=slot.search_query,
                    max_results=5,
                )
                slot.round_number = cycle

            # 3c：调 LLM 审核本轮执行的子 Agent
            pending_slots = {sid: sub_slots[sid] for sid in pending_ids}
            reviews = await self._review_sub_agents(pending_slots, project_summary)

            # 3d：处理审核结果
            all_passed = True
            for review in reviews:
                slot = sub_slots.get(review.sub_id)
                if slot is None:
                    continue

                if review.verdict == "passed":
                    slot.status = AgentStatus.PASSED
                    print(f"      ✅ {review.sub_id}: 通过 "
                          f"(overall={review.overall_score:.1f}, cred={review.credibility:.1f})")
                else:
                    all_passed = False
                    slot.rejection_log.append(RejectionEntry(
                        round=cycle,
                        reason=review.reason,
                        instruction=review.improved_query,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                    if cycle < max_cycles:
                        # 还有重试机会：更新搜索词，标记 REJECTED
                        slot.status = AgentStatus.REJECTED
                        old_query = slot.search_query
                        slot.search_query = review.improved_query
                        print(f"      ❌ {review.sub_id}: 驳回 (overall={review.overall_score:.1f})")
                        print(f"         原因: {review.reason}")
                        print(f"         新搜索词: {review.improved_query}")
                    else:
                        # 最后一轮仍不通过 → 放弃
                        slot.status = AgentStatus.UNCERTAIN
                        print(f"      ⚠️  {review.sub_id}: 超限放弃 (overall={review.overall_score:.1f})")
                        print(f"         原因: {review.reason}")

            if all_passed:
                print(f"  📊 [MarketLeader] 全部通过审核 ✅")
                break

        # 步骤 3e：标记仍然 REJECTED 的为 UNCERTAIN（兜底）
        for slot in sub_slots.values():
            if slot.status == AgentStatus.REJECTED:
                slot.status = AgentStatus.UNCERTAIN

        # ---- 步骤 4：汇总底层发现 → 格式化文本 ----
        findings_text = self._format_all_findings(sub_slots)

        # ---- 步骤 5：调 LLM 综合分析 ----
        messages = build_market_leader_prompt(
            project_summary=project_summary,
            findings_text=findings_text,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=MarketResearchState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error("MarketLeader", f"LLM 综合分析失败: {type(e).__name__}: {e}")
            return MarketResearchState(
                summary=f"市场调研分析失败: {str(e)[:200]}",
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.UNCERTAIN,
                project={"summary": project_summary},
                focus_direction=", ".join(task.focus_areas),
                sub_agents=sub_slots,
                cycle_count=cycle_count,
            )

        # ---- 步骤 6：补填 Internal 字段 ----
        state = MarketResearchState(
            summary=raw_result.summary,
            key_points=raw_result.key_points,
            overall_confidence=raw_result.overall_confidence,
            status=AgentStatus.PASSED,
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=cycle_count,
        )

        # ---- 步骤 7：打印输出 ----
        log_agent_output(
            agent_name="MarketLeader",
            agent_emoji="📊",
            input_summary=f"项目: {project_summary[:100]} | 审核轮次: {cycle_count} | 关注: {task.focus_areas}",
            output={
                "summary": state.summary[:200] if state.summary else "无",
                "key_points_count": len(state.key_points),
                "key_points": [kp.title for kp in state.key_points],
                "overall_confidence": state.overall_confidence,
                "sub_agents": {
                    sid: {
                        "query": slot.search_query,
                        "status": slot.status.value,
                        "round": slot.round_number,
                        "rejections": len(slot.rejection_log),
                        "findings_count": len(slot.latest_output.key_findings) if slot.latest_output else 0,
                    }
                    for sid, slot in sub_slots.items()
                },
            },
        )

        return state

    # ------------------------------------------------------------------
    # 审核方法
    # ------------------------------------------------------------------

    async def _review_sub_agents(
        self,
        pending_slots: dict[str, SubAgentSlot],
        project_summary: str,
    ) -> list[SubAgentReview]:
        """调 LLM 审核待审子 Agent 的研究报告。

        收集所有待审 slot 的报告信息，构建 prompt，调 LLM 一次性审核全部。

        参数：
            pending_slots：本轮待审核的子 Agent 卡槽
            project_summary：项目描述（给 reviewer 做上下文）

        返回：
            SubAgentReview 列表（与 pending_slots 一一对应）
        """
        # 构建审核所需的信息摘要
        sub_slots_info: list[dict] = []
        for sub_id, slot in pending_slots.items():
            info: dict = {
                "sub_id": sub_id,
                "search_query": slot.search_query,
                "report": "",
                "findings_count": 0,
                "key_findings_summary": [],
            }
            if slot.latest_output is not None:
                info["report"] = slot.latest_output.report
                info["findings_count"] = len(slot.latest_output.key_findings)
                for f in slot.latest_output.key_findings:
                    info["key_findings_summary"].append(
                        f"[{f.source_type}] {f.insight[:120]}"
                    )
            sub_slots_info.append(info)

        messages = build_review_prompt(sub_slots_info, project_summary)

        try:
            result: ReviewResult = await self.llm.chat_structured(
                messages=messages,
                output_schema=ReviewResult,
                max_tokens=2048,
            )
            return result.reviews
        except Exception as e:
            log_error("MarketLeader.review", f"审核调用失败: {type(e).__name__}: {e}")
            # 审核失败 → 全部默认通过（不阻塞流程）
            return [
                SubAgentReview(
                    sub_id=info["sub_id"],
                    overall_score=5.0,
                    completeness=5.0,
                    credibility=5.0,
                    freshness=5.0,
                    relevance=5.0,
                    verdict="passed",
                    reason="审核 LLM 调用失败，默认通过",
                    improved_query="",
                )
                for info in sub_slots_info
            ]

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        """根据 Top Agent 下发的 core_topic + focus_areas 生成搜索关键词。

        Phase 2 可以让顶层 Agent 直接生成完整搜索策略。

        参数：
            task：Top Agent 下发的专属任务（含 core_topic + focus_areas）
            project_summary：项目描述（仅当 core_topic 为空时 fallback 用）

        返回：
            搜索关键词列表（1-2 个）
        """
        queries: list[str] = []
        # 优先用 Top Agent LLM 提取的 core_topic
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
        """将所有底层 Agent 的发现格式化为一段文本（含审核状态）。

        中层 Leader 将此文本喂给 LLM 做综合分析。
        UNCERTAIN 的子 Agent 会标注驳回历史，LLM 能据此判断数据可信度。

        参数：
            sub_slots：底层 Agent 管理槽字典

        返回：
            格式化的多行文本
        """
        parts: list[str] = []
        finding_index = 0  # 全局索引（从 0 开始，供 AnalysisPoint 引用）

        for sub_id, slot in sub_slots.items():
            status_label = {
                AgentStatus.PASSED: "✅ 已通过",
                AgentStatus.UNCERTAIN: "⚠️ 存疑（多轮审核未达标）",
                AgentStatus.REJECTED: "❌ 已驳回",
                AgentStatus.RUNNING: "🔄 执行中",
                AgentStatus.IDLE: "⏳ 待执行",
                AgentStatus.SKIPPED: "⏭️ 已跳过",
            }.get(slot.status, "❓ 未知")

            parts.append(f"=== 搜索方向: {slot.search_query} ===")
            parts.append(f"Agent ID: {sub_id} | 状态: {status_label} | 第 {slot.round_number} 轮")

            # 驳回历史
            if slot.rejection_log:
                parts.append(f"驳回记录 ({len(slot.rejection_log)} 次):")
                for r in slot.rejection_log:
                    parts.append(f"  ⤷ 第 {r.round} 轮: {r.reason}")
                    parts.append(f"     改进指令: {r.instruction}")

            if slot.latest_output is None:
                parts.append("(无结果)")
                continue

            output = slot.latest_output
            parts.append(f"研究报告: {output.report}")
            parts.append(f"共 {len(output.key_findings)} 条关键发现:")
            parts.append("")

            for finding in output.key_findings:
                parts.append(f"  [{finding_index}] {finding.insight}")
                parts.append(f"      来源: {finding.source_url}")
                parts.append(f"      类型: {finding.source_type} | 相关度: {finding.relevance} | 可信度: {finding.confidence}")
                parts.append("")
                finding_index += 1

        parts.append(f"--- 以上共 {finding_index} 条发现 ---")
        return "\n".join(parts)
