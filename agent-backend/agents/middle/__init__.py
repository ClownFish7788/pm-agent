"""
中层 Agent 包 —— 分析综合层。

职责：
- 调度底层 Agent（搜索 + LLM 筛选 + 归类 + 报告）
- LangGraph 子图管理 search→review 循环（每轮批量审核，passed 筛掉，rejected 继续）
- 调 LLM 综合分析 → 输出 DepartmentState

核心：
- BaseMiddleLeader：模板引擎，构造函数注入 dept_key + display_name
- _build_review_subgraph：部门内 search→review 循环的 LangGraph 子图
- ReviewState / AgentSlot：子图 State（checkpoint 到 agent 级）
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

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
    AgentSlot,
    AgentStatus,
    BottomReport,
    DepartmentState,
    DepartmentTask,
    ReviewResult,
    ReviewState,
    SearchStrategy,
    SubAgentReview,
    SubAgentSlot,
)
from search.base import BaseSearchProvider
from utils.logger import log_agent_output, log_error
from utils.progress import ProgressTracker

# =============================================================================
# 部门标识 → 中文名（唯一真源）
# =============================================================================

DEPARTMENT_NAME_MAP: dict[str, str] = {
    "market_research": "市场调研",
    "competitor_analysis": "竞品分析",
    "product_design": "产品设计",
    "future_direction": "未来方向",
    "change_plan": "当下改变",
}

# =============================================================================
# 预置部门 → 专用 prompt builder 映射
# =============================================================================

KNOWN_PROMPT_BUILDERS: dict[str, Callable[..., list[dict[str, str]]]] = {
    "market_research": build_market_leader_prompt,
    "competitor_analysis": build_competitor_leader_prompt,
    "product_design": build_product_leader_prompt,
    "future_direction": build_future_leader_prompt,
    "change_plan": build_change_leader_prompt,
}


def _get_prompt_builder(dept_key: str) -> Callable[..., list[dict[str, str]]]:
    return KNOWN_PROMPT_BUILDERS.get(dept_key, build_generic_department_prompt)


# =============================================================================
# 底层搜索
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
    """执行一次搜索，永不抛异常。"""
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
            tracker.error(f"搜索异常: {type(exc).__name__}: {exc}", department=department, agent_id=sub_id)
        return (sub_id, None, f"{type(exc).__name__}: {exc}")


# =============================================================================
# LangGraph 审核子图
# =============================================================================

async def _batch_review(
    candidates: dict[str, AgentSlot],
    project_summary: str,
    llm: BaseLLMProvider,
    display_name: str,
) -> list[SubAgentReview]:
    """批量调 LLM 审核一批子 Agent 的研究报告（被 subgraph 节点调用）。"""
    sub_slots_info: list[dict] = []
    for sub_id, slot in candidates.items():
        info: dict = {
            "sub_id": sub_id,
            "search_query": slot.search_query,
            "report": "",
            "findings_count": 0,
            "key_findings_summary": [],
        }
        if slot.report is not None:
            info["report"] = slot.report.report
            info["findings_count"] = len(slot.report.key_findings)
            for f in slot.report.key_findings:
                info["key_findings_summary"].append(f"[{f.source_type}] {f.insight[:120]}")
        sub_slots_info.append(info)

    messages = build_review_prompt(sub_slots_info, project_summary)

    try:
        result: ReviewResult = await llm.chat_structured(
            messages=messages, output_schema=ReviewResult, max_tokens=8192,
        )
        return result.reviews
    except Exception as e:
        log_error(f"{display_name}.review", f"审核调用失败: {type(e).__name__}: {e}")
        return [
            SubAgentReview(
                sub_id=info["sub_id"],
                overall_score=0.0, completeness=0.0,
                credibility=0.0, freshness=0.0, relevance=0.0,
                verdict="passed",
                reason=f"审核 LLM 异常（{type(e).__name__}），未经审核放行",
                improved_query="",
            )
            for info in sub_slots_info
        ]


def _build_review_subgraph(
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    tracker: ProgressTracker | None = None,
) -> Any:
    """构建部门内 search→review 循环的 LangGraph 子图。

    两节点 + 条件边：

        [search] → [review] → 条件边
                      ├── done   → END
                      └── search → [search]（只搜 unresolved）

    每轮：asyncio.gather 并行搜 unresolved → 批量 LLM 审核 → passed 筛掉 → rejected 下一轮。
    """

    builder = StateGraph(ReviewState)

    # ---- search 节点 ----
    async def _node_search(state: ReviewState) -> dict:
        ids = state.unresolved_ids
        if not ids:
            return {}

        print(f"  [{state.display_name}] 搜索 {len(ids)} 个方向:")
        for sid in ids:
            slot = state.agent_slots[sid]
            print(f"      {sid}: \"{slot.search_query}\" (第 {slot.round + 1} 轮)")

        # SSE
        for sid in ids:
            if tracker is not None:
                tracker.sub_agent_start(
                    dept=state.dept_key, agent_id=sid,
                    search_query=state.agent_slots[sid].search_query,
                    call_count=llm.call_count,
                )

        # 并行搜索
        tasks = [
            _search_one(sid, state.agent_slots[sid].search_query, llm, search_provider,
                        department=state.dept_key, tracker=tracker)
            for sid in ids
        ]
        results = await asyncio.gather(*tasks)

        # 写入结果
        for sub_id, report, error in results:
            slot = state.agent_slots[sub_id]
            if error is not None:
                slot.status = AgentStatus.UNCERTAIN
                log_error(sub_id, f"搜索异常: {error}")
            else:
                slot.report = report
                slot.key_findings_summary = [f.insight[:150] for f in (report.key_findings or [])]
            slot.round += 1

        return {"agent_slots": state.agent_slots}

    # ---- review 节点 ----
    async def _node_review(state: ReviewState) -> dict:
        ids = state.unresolved_ids
        # 只审核本轮有搜索结果的 agent
        candidates = {
            sid: state.agent_slots[sid]
            for sid in ids
            if state.agent_slots[sid].status != AgentStatus.UNCERTAIN
            and state.agent_slots[sid].report is not None
        }
        if not candidates:
            return {}

        reviews = await _batch_review(candidates, state.project_summary, llm, state.display_name)

        rejections: list[str] = []
        for review in reviews:
            slot = state.agent_slots.get(review.sub_id)
            if slot is None:
                continue
            slot.review = review

            if review.verdict == "passed":
                slot.status = AgentStatus.PASSED
                print(f"      {review.sub_id}: 通过 "
                      f"(overall={review.overall_score:.1f}, cred={review.credibility:.1f})")
            elif review.verdict == "abandon":
                slot.status = AgentStatus.UNCERTAIN
                print(f"      {review.sub_id}: 放弃 (overall={review.overall_score:.1f})")
                print(f"         原因: {review.reason}")
            else:  # rejected
                rejections.append(review.reason)
                if slot.round >= state.max_rounds_per_agent:
                    slot.status = AgentStatus.UNCERTAIN
                    print(f"      {review.sub_id}: 超限放弃 (round={slot.round})")
                else:
                    slot.status = AgentStatus.REJECTED
                    slot.search_query = review.improved_query or slot.search_query
                    print(f"      {review.sub_id}: 驳回 (overall={review.overall_score:.1f})")
                    print(f"         原因: {review.reason}")
                    print(f"         新搜索词: {review.improved_query}")

            # SSE
            if tracker is not None:
                tracker.sub_agent_review(
                    dept=state.dept_key, agent_id=review.sub_id,
                    verdict=review.verdict,
                    overall=review.overall_score,
                    credibility=review.credibility,
                    reason=review.reason,
                    call_count=llm.call_count,
                )

        # instruction 回写
        if rejections and state.task is not None:
            summary = "; ".join(rejections[:3])
            state.task.instruction = f"上一轮搜索问题：{summary}"

        return {"agent_slots": state.agent_slots, "task": state.task}

    # ---- 条件路由 ----
    def _route(state: ReviewState) -> str:
        return "done" if state.is_done else "search"

    # ---- 装配 ----
    builder.add_node("search", _node_search)
    builder.add_node("review", _node_review)
    builder.set_entry_point("search")
    builder.add_edge("search", "review")
    builder.add_conditional_edges("review", _route, {"done": END, "search": "search"})

    return builder.compile(checkpointer=MemorySaver())


# =============================================================================
# 中层 Leader 模板引擎
# =============================================================================

class BaseMiddleLeader:
    """中层 Leader 模板 —— 所有部门共享同一套 6 步分析流程。

    内层审核循环由 LangGraph 子图管理（_build_review_subgraph），
    支持暂停注入 + checkpoint 恢复。
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
        self._prompt_builder = _get_prompt_builder(dept_key)

    # ------------------------------------------------------------------
    # 核心方法：模板 run()
    # ------------------------------------------------------------------

    async def run(self, project_summary: str, task: DepartmentTask) -> DepartmentState:
        """执行本部门的完整分析流程。

        步骤 3 为 LangGraph 子图：search → review → 条件路由 → 循环直到所有 agent 被处理。
        """

        # ---- 步骤 1：LLM 生成搜索关键词 ----
        search_queries = await self._generate_search_queries(task, project_summary)
        print(f"  [{self.display_name}] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：初始化 AgentSlot（子图 State） ----
        prefix = self.dept_key.replace("_", "")[:20]
        agent_slots: dict[str, AgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"{prefix}_{i + 1}"
            agent_slots[sub_id] = AgentSlot(
                sub_id=sub_id,
                search_query=query,
                status=AgentStatus.IDLE,
            )

        # ---- 步骤 3：LangGraph 子图 search→review 循环 ----
        review_graph = _build_review_subgraph(self.llm, self.search_provider, tracker=self.tracker)
        initial_state = ReviewState(
            dept_key=self.dept_key,
            display_name=self.display_name,
            project_summary=project_summary,
            task=task,
            agent_slots=agent_slots,
        )
        final_state: ReviewState = await review_graph.ainvoke(initial_state)

        # ---- 步骤 4：汇总底层发现 → 格式化文本（AgentSlot → SubAgentSlot 转换） ----
        sub_slots: dict[str, SubAgentSlot] = {}
        for sid, slot in final_state.agent_slots.items():
            sub_slots[sid] = SubAgentSlot(
                sub_id=sid,
                search_query=slot.search_query,
                latest_output=slot.report,
                round_number=slot.round,
                status=slot.status,
            )
        findings_text = self._format_all_findings(final_state.agent_slots)

        # ---- 步骤 5：调 LLM 综合分析 ----
        messages = self._prompt_builder(
            project_summary=project_summary,
            findings_text=findings_text,
            task=task,
        )
        try:
            raw_result = await self.llm.chat_structured(
                messages=messages, output_schema=DepartmentState, max_tokens=4096,
            )
        except Exception as e:
            log_error(self.display_name, f"LLM 综合分析失败: {type(e).__name__}: {e}")
            if self.tracker is not None:
                self.tracker.error(f"LLM 综合分析失败: {e}", department=self.dept_key)
            return self._build_fallback_state(project_summary, task, sub_slots, str(e))

        # ---- 步骤 6：构造最终 State ----
        state = self._build_state(raw_result, project_summary, task, sub_slots)

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
            input_summary=f"项目: {project_summary[:100]} | 关注: {task.focus_areas}",
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
                        "findings_count": len(slot.latest_output.key_findings) if slot.latest_output else 0,
                    }
                    for sid, slot in sub_slots.items()
                },
            },
        )

        return state

    # ------------------------------------------------------------------
    # 搜索结果格式化（AgentSlot）
    # ------------------------------------------------------------------

    def _format_all_findings(self, agent_slots: dict[str, AgentSlot]) -> str:
        parts: list[str] = []
        finding_index = 0

        for sub_id, slot in agent_slots.items():
            status_label = {
                AgentStatus.PASSED: "通过",
                AgentStatus.UNCERTAIN: "存疑",
                AgentStatus.REJECTED: "已驳回",
                AgentStatus.RUNNING: "执行中",
                AgentStatus.IDLE: "待执行",
                AgentStatus.SKIPPED: "已跳过",
            }.get(slot.status, "未知")

            parts.append(f"=== 搜索方向: {slot.search_query} ===")
            parts.append(f"Agent: {sub_id} | 状态: {status_label} | 第 {slot.round} 轮")

            if slot.review and slot.review.verdict != "passed":
                parts.append(f"审核: {slot.review.verdict} (overall={slot.review.overall_score:.1f}) — {slot.review.reason}")

            if slot.report is None:
                parts.append("(无结果)")
                continue

            output = slot.report
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
    # 搜索策略生成
    # ------------------------------------------------------------------

    async def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        try:
            messages = build_search_strategy_prompt(task, project_summary)
            strategy: SearchStrategy = await self.llm.chat_structured(
                messages=messages, output_schema=SearchStrategy, max_tokens=1024,
            )
            if strategy.queries:
                print(f"  [{self.display_name}] LLM 搜索策略: {strategy.reasoning}")
                return strategy.queries
        except Exception as e:
            log_error(self.display_name, f"搜索策略 LLM 失败: {e}，fallback")

        core_topic = task.core_topic or project_summary[:15]
        return [f"{core_topic} {area}" for area in task.focus_areas[:2]]

    # ------------------------------------------------------------------
    # State 构造
    # ------------------------------------------------------------------

    def _build_state(
        self, raw_result: object, project_summary: str, task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot],
    ) -> DepartmentState:
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
            cycle_count=max((s.round_number for s in sub_slots.values()), default=0),
            department_type=self.dept_key,
        )

    def _build_fallback_state(
        self, project_summary: str, task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot], error_msg: str,
    ) -> DepartmentState:
        return DepartmentState(
            summary=f"{self.display_name}分析失败: {error_msg[:200]}",
            key_points=[], overall_confidence=0.0,
            status=AgentStatus.UNCERTAIN,
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=0,
            department_type=self.dept_key,
        )
