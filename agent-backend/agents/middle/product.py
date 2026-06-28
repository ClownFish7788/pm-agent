"""
中层产品设计 Leader Agent。

职责：
1. 接收顶层下发的项目信息 + 关注方向
2. 根据关注方向生成 1-3 个产品设计搜索关键词
3. 每个关键词调度一个底层 SearchAgent
4. 审核底层报告质量 → 低分驳回重做（最多 3 轮）
5. 收集底层发现，调 LLM 综合分析
6. 填充 ProductDesignState 的 Public 字段
7. 打印中间过程和最终输出

Phase 2 新增：
- 审核 + 驳回循环（与 MarketLeader 相同模式）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from agents.middle import _search_one
from llm.base import BaseLLMProvider
from prompts.templates import build_product_leader_prompt, build_review_prompt
from schemas import (
    AgentStatus,
    DepartmentTask,
    ProductDesignState,
    RejectionEntry,
    ReviewResult,
    SubAgentReview,
    SubAgentSlot,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error
from utils.progress import ProgressTracker


class ProductLeader:
    """产品设计中层 Leader。

    管理底层搜索 Agent，审核报告质量，综合多源发现为产品设计报告。

    属性：
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（依赖注入，传给底层 Agent）
        tracker：ProgressTracker 或 None（SSE 事件推送）
    """

    DEPT = "product_design"

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
        *,
        tracker: ProgressTracker | None = None,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.tracker = tracker

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    async def run(
        self,
        project_summary: str,
        task: DepartmentTask,
    ) -> ProductDesignState:
        """执行产品设计分析（含审核 + 驳回循环）。"""
        # ---- 步骤 1：生成搜索关键词 ----
        search_queries = self._generate_search_queries(task, project_summary)
        print(f"  🎨 [ProductLeader] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：初始化子 Agent 卡槽 ----
        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"product_query_{i + 1}"
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

            pending_ids = [
                sid for sid, slot in sub_slots.items()
                if slot.status in (AgentStatus.IDLE, AgentStatus.REJECTED)
            ]
            if not pending_ids:
                break

            print(f"  🎨 [ProductLeader] 第 {cycle}/{max_cycles} 轮审核 — "
                  f"待执行: {len(pending_ids)} 个子 Agent")

            # 并行搜索 —— 所有待审子 Agent 同时发起搜索 + LLM 分析
            for sid in pending_ids:
                if self.tracker is not None:
                    self.tracker.sub_agent_start(
                        dept=self.DEPT, agent_id=sid,
                        search_query=sub_slots[sid].search_query,
                        call_count=self.llm.call_count,
                    )

            tasks = [
                _search_one(sid, sub_slots[sid].search_query, self.llm, self.search_provider,
                            department=self.DEPT, tracker=self.tracker)
                for sid in pending_ids
            ]
            results = await asyncio.gather(*tasks)

            for sub_id, report, error in results:
                slot = sub_slots[sub_id]
                if error is not None:
                    slot.latest_output = None
                    slot.status = AgentStatus.UNCERTAIN
                    log_error(sub_id, f"搜索异常: {error}")
                else:
                    slot.latest_output = report
                slot.round_number = cycle

            pending_slots = {sid: sub_slots[sid] for sid in pending_ids}
            reviews = await self._review_sub_agents(pending_slots, project_summary)

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
                        slot.status = AgentStatus.REJECTED
                        slot.search_query = review.improved_query
                        print(f"      ❌ {review.sub_id}: 驳回 (overall={review.overall_score:.1f})")
                        print(f"         原因: {review.reason}")
                        print(f"         新搜索词: {review.improved_query}")
                    else:
                        slot.status = AgentStatus.UNCERTAIN
                        print(f"      ⚠️  {review.sub_id}: 超限放弃 (overall={review.overall_score:.1f})")
                        print(f"         原因: {review.reason}")

                # SSE: 审核结果
                if self.tracker is not None:
                    self.tracker.sub_agent_review(
                        dept=self.DEPT, agent_id=review.sub_id,
                        verdict=review.verdict,
                        overall=review.overall_score,
                        credibility=review.credibility,
                        reason=review.reason,
                        call_count=self.llm.call_count,
                    )

            if all_passed:
                print(f"  🎨 [ProductLeader] 全部通过审核 ✅")
                break

        for slot in sub_slots.values():
            if slot.status == AgentStatus.REJECTED:
                slot.status = AgentStatus.UNCERTAIN

        # ---- 步骤 4：汇总 ----
        findings_text = self._format_all_findings(sub_slots)

        # ---- 步骤 5：LLM 综合分析 ----
        messages = build_product_leader_prompt(
            project_summary=project_summary,
            findings_text=findings_text,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=ProductDesignState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error("ProductLeader", f"LLM 综合分析失败: {type(e).__name__}: {e}")
            if self.tracker is not None:
                self.tracker.error(f"LLM 综合分析失败: {e}", department=self.DEPT)
            return ProductDesignState(
                summary=f"产品设计分析失败: {str(e)[:200]}",
                key_points=[],
                overall_confidence=0.0,
                status=AgentStatus.UNCERTAIN,
                project={"summary": project_summary},
                sub_agents=sub_slots,
                cycle_count=cycle_count,
            )

        state = ProductDesignState(
            summary=raw_result.summary,
            key_points=raw_result.key_points,
            overall_confidence=raw_result.overall_confidence,
            status=AgentStatus.PASSED,
            project={"summary": project_summary},
            sub_agents=sub_slots,
            cycle_count=cycle_count,
        )

        # SSE: 部门完成
        if self.tracker is not None:
            self.tracker.department_done(
                dept=self.DEPT,
                summary=state.summary or "",
                key_points_count=len(state.key_points),
                confidence=state.overall_confidence,
                status=state.status.value,
                call_count=self.llm.call_count,
            )

        log_agent_output(
            agent_name="ProductLeader",
            agent_emoji="🎨",
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
        """调 LLM 审核待审子 Agent 的研究报告。"""
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
            log_error("ProductLeader.review", f"审核调用失败: {type(e).__name__}: {e}")
            return [
                SubAgentReview(
                    sub_id=info["sub_id"],
                    overall_score=5.0, completeness=5.0,
                    credibility=5.0, freshness=5.0, relevance=5.0,
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
        """根据 Top Agent 下发的 core_topic + focus_areas 生成产品搜索关键词。"""
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
        """将所有底层 Agent 的发现格式化为一段文本（含审核状态）。"""
        parts: list[str] = []
        finding_index = 0

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
