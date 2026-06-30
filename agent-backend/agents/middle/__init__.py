"""
中层 Agent 包 —— 分析综合层。

职责：
- 调度底层 Agent（搜索 + LLM 筛选 + 归类 + 报告）
- 审核底层报告质量 → 驳回重做（最多 3 轮）
- 调 LLM 综合分析 → 输出 DepartmentState

核心：
- BaseMiddleLeader：模板引擎，构造函数注入 dept_key + display_name
- DEPARTMENT_NAME_MAP：部门标识 → 中文名（唯一真源）
- KNOWN_PROMPT_BUILDERS：预置部门 → 专用 prompt 映射（自创部门用通用 prompt）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from agents.bottom.search import SearchAgent
from llm.base import BaseLLMProvider
from prompts.templates import (
    build_review_prompt,
    build_search_strategy_prompt,
    build_market_leader_prompt,
    build_competitor_leader_prompt,
    build_product_leader_prompt,
    build_future_leader_prompt,
    build_change_leader_prompt,
    build_generic_department_prompt,
)
from schemas import (
    AgentStatus,
    BottomReport,
    DepartmentState,
    DepartmentTask,
    RejectionEntry,
    ReviewResult,
    SearchStrategy,
    SubAgentReview,
    SubAgentSlot,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error
from utils.progress import ProgressTracker

# =============================================================================
# 部门标识 → 中文名（唯一真源，SSE / 控制台 / dag/nodes.py 共用）
# =============================================================================

DEPARTMENT_NAME_MAP: dict[str, str] = {
    "market_research": "市场调研",
    "competitor_analysis": "竞品分析",
    "product_design": "产品设计",
    "future_direction": "未来方向",
    "change_plan": "当下改变",
}

# =============================================================================
# 预置部门 → 专用 prompt builder 映射（自创部门不在映射中 → 通用 prompt）
# =============================================================================

KNOWN_PROMPT_BUILDERS: dict[str, Callable[..., list[dict[str, str]]]] = {
    "market_research": build_market_leader_prompt,
    "competitor_analysis": build_competitor_leader_prompt,
    "product_design": build_product_leader_prompt,
    "future_direction": build_future_leader_prompt,
    "change_plan": build_change_leader_prompt,
}


def _get_prompt_builder(dept_key: str) -> Callable[..., list[dict[str, str]]]:
    """根据部门类型获取 prompt builder。预置 → 专用 prompt；未知 → 通用 prompt。"""
    return KNOWN_PROMPT_BUILDERS.get(dept_key, build_generic_department_prompt)


# =============================================================================
# 底层搜索工具函数
# =============================================================================

async def _search_one(
    sub_id: str,
    query: str,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    department: str | None = None,
    tracker: ProgressTracker | None = None,
) -> tuple[str, BottomReport | None, str | None]:
    """执行一次搜索，永不抛异常 —— 异常内化为返回三元组的第三个元素。"""
    try:
        agent = SearchAgent(
            agent_id=sub_id,
            llm=llm,
            search_provider=search_provider,
            department=department,
            tracker=tracker,
        )
        report = await agent.run(search_query=query, max_results=5)
        return (sub_id, report, None)
    except Exception as exc:
        if tracker is not None:
            tracker.error(
                f"搜索异常: {type(exc).__name__}: {exc}",
                department=department,
                agent_id=sub_id,
            )
        return (sub_id, None, f"{type(exc).__name__}: {exc}")


# =============================================================================
# 中层 Leader 模板引擎
# =============================================================================

class BaseMiddleLeader:
    """中层 Leader 模板 —— 所有部门共享同一套 6 步分析流程。

    构造函数注入部门标识 + 显示名，prompt builder 自动查表：
    - 预置部门 → 手写专用 prompt
    - 自创部门 → 通用 prompt（读取 task.task_description + metrics）
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
        *,
        tracker: ProgressTracker | None = None,
        dept_key: str,
        display_name: str,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.tracker = tracker
        self.dept_key = dept_key
        self.display_name = display_name
        # 自动选择 prompt builder
        self._prompt_builder = _get_prompt_builder(dept_key)

    # ------------------------------------------------------------------
    # 核心方法：模板 run()
    # ------------------------------------------------------------------

    async def run(self, project_summary: str, task: DepartmentTask) -> DepartmentState:
        """执行本部门的完整分析流程。

        Args:
            project_summary: 项目描述摘要
            task: 顶层下发的专属任务（含 task_description / focus_areas / metrics / instruction）

        Returns:
            DepartmentState 实例
        """

        # ---- 步骤 1：LLM 生成搜索关键词 ----
        search_queries = await self._generate_search_queries(task, project_summary)
        print(f"  [{self.display_name}] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：初始化子 Agent 卡槽 ----
        # sub_id 前缀 = dept_key 去下划线取前 20 字符
        prefix = self.dept_key.replace("_", "")[:20]
        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"{prefix}_{i + 1}"
            sub_slots[sub_id] = SubAgentSlot(
                sub_id=sub_id,
                search_query=query,
                latest_output=None,
                round_number=0,
                rejection_log=[],
                status=AgentStatus.IDLE,
            )

        # ---- 步骤 3：审核 + 驳回循环（最多 3 轮） ----
        cycle_count = await self._run_review_loop(sub_slots, project_summary, task=task)

        # ---- 步骤 4：汇总底层发现 → 格式化文本 ----
        findings_text = self._format_all_findings(sub_slots)

        # ---- 步骤 5：调 LLM 综合分析 ----
        messages = self._prompt_builder(
            project_summary=project_summary,
            findings_text=findings_text,
            task=task,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=DepartmentState,
                max_tokens=4096,
            )
        except Exception as e:
            log_error(self.display_name, f"LLM 综合分析失败: {type(e).__name__}: {e}")
            if self.tracker is not None:
                self.tracker.error(f"LLM 综合分析失败: {e}", department=self.dept_key)
            return self._build_fallback_state(project_summary, task, sub_slots, cycle_count, str(e))

        # ---- 步骤 6：构造最终 State ----
        state = self._build_state(raw_result, project_summary, task, sub_slots, cycle_count)

        # SSE: 部门完成
        if self.tracker is not None:
            self.tracker.department_done(
                dept=self.dept_key,
                summary=state.summary or "",
                key_points_count=len(state.key_points),
                confidence=state.overall_confidence,
                status=state.status.value,
                call_count=self.llm.call_count,
            )

        # ---- 步骤 7：打印输出 ----
        log_agent_output(
            agent_name=self.display_name,
            agent_emoji="",
            input_summary=f"项目: {project_summary[:100]} | 审核轮次: {cycle_count} | 关注: {task.focus_areas}",
            output={
                "summary": state.summary[:200] if state.summary else "无",
                "key_points_count": len(state.key_points),
                "key_points": [kp.title for kp in state.key_points],
                "overall_confidence": state.overall_confidence,
                "metrics_coverage": state.metrics_coverage,
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
    # 审核循环
    # ------------------------------------------------------------------

    async def _run_review_loop(
        self,
        sub_slots: dict[str, SubAgentSlot],
        project_summary: str,
        task: DepartmentTask | None = None,
    ) -> int:
        """审核 + 驳回循环（最多 3 轮），驳回时回写 task.instruction。"""
        max_cycles = 3
        cycle_count = 0
        rejection_reasons: list[str] = []

        for cycle in range(1, max_cycles + 1):
            cycle_count = cycle

            pending_ids = [
                sid for sid, slot in sub_slots.items()
                if slot.status in (AgentStatus.IDLE, AgentStatus.REJECTED)
            ]
            if not pending_ids:
                break

            print(f"  [{self.display_name}] 第 {cycle}/{max_cycles} 轮审核 — "
                  f"待执行: {len(pending_ids)} 个子 Agent")

            # SSE: 子 Agent 启动
            for sid in pending_ids:
                if self.tracker is not None:
                    self.tracker.sub_agent_start(
                        dept=self.dept_key, agent_id=sid,
                        search_query=sub_slots[sid].search_query,
                        call_count=self.llm.call_count,
                    )

            # 并行搜索
            tasks = [
                _search_one(sid, sub_slots[sid].search_query, self.llm, self.search_provider,
                            department=self.dept_key, tracker=self.tracker)
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

            # 审核
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
                    rejection_reasons.append(review.reason)
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

                if self.tracker is not None:
                    self.tracker.sub_agent_review(
                        dept=self.dept_key, agent_id=review.sub_id,
                        verdict=review.verdict,
                        overall=review.overall_score,
                        credibility=review.credibility,
                        reason=review.reason,
                        call_count=self.llm.call_count,
                    )

            if all_passed:
                print(f"  [{self.display_name}] 全部通过审核")
                break

        for slot in sub_slots.values():
            if slot.status == AgentStatus.REJECTED:
                slot.status = AgentStatus.UNCERTAIN

        if rejection_reasons and task is not None:
            summary = "; ".join(rejection_reasons[:3])
            task.instruction = f"上一轮搜索问题：{summary}"

        return cycle_count

    # ------------------------------------------------------------------
    # 审核
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
            log_error(f"{self.display_name}.review", f"审核调用失败: {type(e).__name__}: {e}")
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
    # 搜索结果格式化
    # ------------------------------------------------------------------

    def _format_all_findings(self, sub_slots: dict[str, SubAgentSlot]) -> str:
        """将所有底层 Agent 的发现格式化为一段文本（含审核状态）。"""
        parts: list[str] = []
        finding_index = 0

        for sub_id, slot in sub_slots.items():
            status_label = {
                AgentStatus.PASSED: "通过",
                AgentStatus.UNCERTAIN: "存疑（多轮未达标）",
                AgentStatus.REJECTED: "已驳回",
                AgentStatus.RUNNING: "执行中",
                AgentStatus.IDLE: "待执行",
                AgentStatus.SKIPPED: "已跳过",
            }.get(slot.status, "未知")

            parts.append(f"=== 搜索方向: {slot.search_query} ===")
            parts.append(f"Agent: {sub_id} | 状态: {status_label} | 第 {slot.round_number} 轮")

            if slot.rejection_log:
                parts.append(f"驳回记录 ({len(slot.rejection_log)} 次):")
                for r in slot.rejection_log:
                    parts.append(f"  - 第 {r.round} 轮: {r.reason}")

            if slot.latest_output is None:
                parts.append("(无结果)")
                continue

            output = slot.latest_output
            parts.append(f"研究报告: {output.report}")
            parts.append(f"关键发现 ({len(output.key_findings)} 条):")
            parts.append("")

            for finding in output.key_findings:
                parts.append(f"  [{finding_index}] {finding.insight}")
                parts.append(f"      来源: {finding.source_url}")
                parts.append(f"      类型: {finding.source_type} | 相关度: {finding.relevance} | 可信度: {finding.confidence}")
                parts.append("")
                finding_index += 1

        parts.append(f"--- 以上共 {finding_index} 条发现 ---")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 搜索策略生成（LLM 自主 + 字符串拼接兜底）
    # ------------------------------------------------------------------

    async def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        """LLM 自主生成搜索关键词，失败时 fallback 到 core_topic + focus_areas 拼接。"""
        try:
            messages = build_search_strategy_prompt(task, project_summary)
            strategy: SearchStrategy = await self.llm.chat_structured(
                messages=messages,
                output_schema=SearchStrategy,
                max_tokens=1024,
            )
            if strategy.queries:
                print(f"  [{self.display_name}] LLM 搜索策略: {strategy.reasoning}")
                return strategy.queries
        except Exception as e:
            log_error(self.display_name, f"搜索策略 LLM 失败: {e}，fallback 拼接")

        # Fallback
        core_topic = task.core_topic or ""
        if not core_topic and project_summary:
            core_topic = project_summary[:15]
        queries = []
        for area in task.focus_areas[:2]:
            prefix = f"{core_topic} " if core_topic else ""
            queries.append(f"{prefix}{area}")
        return queries

    # ------------------------------------------------------------------
    # State 构造
    # ------------------------------------------------------------------

    def _build_state(
        self,
        raw_result: object,
        project_summary: str,
        task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot],
        cycle_count: int,
    ) -> DepartmentState:
        """从 LLM 输出 + 运行时上下文构造完整的 DepartmentState。"""
        return DepartmentState(
            summary=getattr(raw_result, "summary", None),
            key_points=getattr(raw_result, "key_points", []),
            overall_confidence=getattr(raw_result, "overall_confidence", 0.0),
            status=AgentStatus.PASSED,
            conclusion=getattr(raw_result, "conclusion", ""),
            recommendations=getattr(raw_result, "recommendations", []),
            gaps=getattr(raw_result, "gaps", []),
            metrics_coverage=getattr(raw_result, "metrics_coverage", {}),
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=cycle_count,
            department_type=self.dept_key,
        )

    def _build_fallback_state(
        self,
        project_summary: str,
        task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot],
        cycle_count: int,
        error_msg: str,
    ) -> DepartmentState:
        """LLM 综合分析失败时的兜底 State。"""
        return DepartmentState(
            summary=f"{self.display_name}分析失败: {error_msg[:200]}",
            key_points=[],
            overall_confidence=0.0,
            status=AgentStatus.UNCERTAIN,
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=cycle_count,
            department_type=self.dept_key,
        )
