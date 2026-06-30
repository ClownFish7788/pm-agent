"""
中层 Agent 包 —— 分析综合层。

职责：
- 调度底层 Agent（决定搜索什么、搜几次）
- 收集底层发现，调 LLM 综合分析
- 输出 AnalysisPoint[] + 对应中层 State

核心类：
- BaseMiddleLeader：中层 Leader 模板基类，封装审核+驳回循环、底层调度、综合分析
- MiddleLeaderConfig：即插即用配置，5 个部门各一份
- DEPARTMENT_NAME_MAP：部门标识 → 中文名映射，前端可用
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
# 部门标识 → 中文名映射（前端 SSE 事件消费 / 控制台打印 共用）
# =============================================================================

DEPARTMENT_NAME_MAP: dict[str, str] = {
    "market_research": "市场调研",
    "competitor_analysis": "竞品分析",
    "product_design": "产品设计",
    "future_direction": "未来方向",
    "change_plan": "当下改变",
}


# =============================================================================
# 中层配置容器 —— 传入 BaseMiddleLeader 即插即用
# =============================================================================

class MiddleLeaderConfig:
    """一个中层部门的全部差异化信息。

    5 个部门各自一份配置实例，传给 BaseMiddleLeader 后全部行为确定。
    """

    __slots__ = ("dept_key", "display_name", "sub_id_prefix", "state_cls", "prompt_builder")

    def __init__(
        self,
        *,
        dept_key: str,
        display_name: str,
        sub_id_prefix: str,
        state_cls: type,
        prompt_builder: Callable[..., list[dict[str, str]]],
    ) -> None:
        self.dept_key = dept_key                 # "market_research"
        self.display_name = display_name          # "市场调研"
        self.sub_id_prefix = sub_id_prefix        # "market_query"
        self.state_cls = state_cls                # MarketResearchState
        self.prompt_builder = prompt_builder      # build_market_leader_prompt()


# =============================================================================
# 5 个部门预置配置（当前由调用的 DAG 节点 / TopAgent 直接使用）
# 未来 Top Agent 可动态生成 MiddleLeaderConfig 传入 BaseMiddleLeader
# =============================================================================

MARKET_LEADER_CONFIG = MiddleLeaderConfig(
    dept_key="market_research",
    display_name="市场调研",
    sub_id_prefix="market_query",
    state_cls=DepartmentState,
    prompt_builder=build_market_leader_prompt,
)

COMPETITOR_LEADER_CONFIG = MiddleLeaderConfig(
    dept_key="competitor_analysis",
    display_name="竞品分析",
    sub_id_prefix="competitor_query",
    state_cls=DepartmentState,
    prompt_builder=build_competitor_leader_prompt,
)

PRODUCT_LEADER_CONFIG = MiddleLeaderConfig(
    dept_key="product_design",
    display_name="产品设计",
    sub_id_prefix="product_query",
    state_cls=DepartmentState,
    prompt_builder=build_product_leader_prompt,
)

FUTURE_LEADER_CONFIG = MiddleLeaderConfig(
    dept_key="future_direction",
    display_name="未来方向",
    sub_id_prefix="future_query",
    state_cls=DepartmentState,
    prompt_builder=build_future_leader_prompt,
)

CHANGE_LEADER_CONFIG = MiddleLeaderConfig(
    dept_key="change_plan",
    display_name="当下改变",
    sub_id_prefix="change_query",
    state_cls=DepartmentState,
    prompt_builder=build_change_leader_prompt,
)


# =============================================================================
# 底层搜索工具函数 —— 中层共享
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
    """执行一次搜索，永不抛异常 —— 异常内化为返回三元组的第三个元素。

    Args:
        sub_id: 子 Agent ID
        query: 搜索关键词
        llm: LLM Provider（共享实例）
        search_provider: Search Provider
        department: 所属部门名（用于 SSE 事件）
        tracker: ProgressTracker 或 None

    Returns:
        (sub_id, report_or_None, error_msg_or_None)
    """
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
# 中层 Leader 模板基类
# =============================================================================

class BaseMiddleLeader:
    """中层 Leader 模板 —— 所有部门共享同一套 6 步分析流程。

    通过构造函数注入 MiddleLeaderConfig，即插即用：
    - 当前：DAG 节点/ TopAgent 传入预置常量（MARKET_LEADER_CONFIG 等）
    - 未来：TopAgent LLM 动态生成 config 后直接传入
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
        *,
        tracker: ProgressTracker | None = None,
        config: MiddleLeaderConfig,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.tracker = tracker
        self.config = config

    # ------------------------------------------------------------------
    # 核心方法：模板 run()
    # ------------------------------------------------------------------

    async def run(self, project_summary: str, task: DepartmentTask) -> object:
        """执行本部门的完整分析流程（6 步模板方法）。

        Args:
            project_summary: 项目描述摘要（来自顶层 Agent）
            task: 顶层下发的专属任务（含 focus_areas + instruction + core_topic）

        Returns:
            对应部门的 Pydantic State 实例
        """
        cfg = self.config

        # ---- 步骤 1：LLM 生成搜索关键词 ----
        search_queries = await self._generate_search_queries(task, project_summary)
        print(f"  [{cfg.display_name}] 准备搜索 {len(search_queries)} 个方向:")
        for i, q in enumerate(search_queries, 1):
            print(f"      {i}. {q}")

        # ---- 步骤 2：初始化子 Agent 卡槽 ----
        sub_slots: dict[str, SubAgentSlot] = {}
        for i, query in enumerate(search_queries):
            sub_id = f"{cfg.sub_id_prefix}_{i + 1}"
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

        # ---- 步骤 5：调 LLM 综合分析（传入 task 以注入 metrics/instruction） ----
        messages = cfg.prompt_builder(
            project_summary=project_summary,
            findings_text=findings_text,
            task=task,
        )

        try:
            raw_result = await self.llm.chat_structured(
                messages=messages,
                output_schema=cfg.state_cls,
                max_tokens=4096,
            )
        except Exception as e:
            log_error(cfg.display_name, f"LLM 综合分析失败: {type(e).__name__}: {e}")
            if self.tracker is not None:
                self.tracker.error(f"LLM 综合分析失败: {e}", department=cfg.dept_key)
            return self._build_fallback_state(project_summary, task, sub_slots, cycle_count, str(e))

        # ---- 步骤 6：构造最终 State ----
        state = self._build_state(raw_result, project_summary, task, sub_slots, cycle_count)

        # SSE: 部门完成
        if self.tracker is not None:
            self.tracker.department_done(
                dept=cfg.dept_key,
                summary=state.summary or "",
                key_points_count=len(state.key_points),
                confidence=state.overall_confidence,
                status=state.status.value,
                call_count=self.llm.call_count,
            )

        # ---- 步骤 7：打印输出 ----
        log_agent_output(
            agent_name=cfg.display_name,
            agent_emoji="",
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
    # 审核循环
    # ------------------------------------------------------------------

    async def _run_review_loop(
        self,
        sub_slots: dict[str, SubAgentSlot],
        project_summary: str,
        task: DepartmentTask | None = None,
    ) -> int:
        """审核 + 驳回循环（最多 3 轮），返回实际执行轮数。

        驳回时将原因摘要回写到 task.instruction，供下一轮 _generate_search_queries 使用。
        """
        cfg = self.config
        max_cycles = 3
        cycle_count = 0
        rejection_reasons: list[str] = []  # 本轮驳回原因收集

        for cycle in range(1, max_cycles + 1):
            cycle_count = cycle

            pending_ids = [
                sid for sid, slot in sub_slots.items()
                if slot.status in (AgentStatus.IDLE, AgentStatus.REJECTED)
            ]
            if not pending_ids:
                break

            print(f"  [{cfg.display_name}] 第 {cycle}/{max_cycles} 轮审核 — "
                  f"待执行: {len(pending_ids)} 个子 Agent")

            # SSE: 子 Agent 启动
            for sid in pending_ids:
                if self.tracker is not None:
                    self.tracker.sub_agent_start(
                        dept=cfg.dept_key, agent_id=sid,
                        search_query=sub_slots[sid].search_query,
                        call_count=self.llm.call_count,
                    )

            # 并行搜索
            tasks = [
                _search_one(sid, sub_slots[sid].search_query, self.llm, self.search_provider,
                            department=cfg.dept_key, tracker=self.tracker)
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
                        print(f"         原因: {review.reason}")

                # SSE: 审核结果
                if self.tracker is not None:
                    self.tracker.sub_agent_review(
                        dept=cfg.dept_key, agent_id=review.sub_id,
                        verdict=review.verdict,
                        overall=review.overall_score,
                        credibility=review.credibility,
                        reason=review.reason,
                        call_count=self.llm.call_count,
                    )

            if all_passed:
                print(f"  [{cfg.display_name}] 全部通过审核")
                break

        # 兜底：标记仍然 REJECTED 的为 UNCERTAIN
        for slot in sub_slots.values():
            if slot.status == AgentStatus.REJECTED:
                slot.status = AgentStatus.UNCERTAIN

        # 驳回反馈回写：task.instruction 供下一轮 _generate_search_queries 读取
        if rejection_reasons and task is not None:
            summary = "; ".join(rejection_reasons[:3])
            task.instruction = (
                f"上一轮搜索存在以下问题，请调整搜索策略：{summary}"
            )

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
        cfg = self.config

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
            log_error(f"{cfg.display_name}.review", f"审核调用失败: {type(e).__name__}: {e}")
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

    # ------------------------------------------------------------------
    # 搜索词生成
    # ------------------------------------------------------------------

    async def _generate_search_queries(
        self, task: DepartmentTask, project_summary: str = ""
    ) -> list[str]:
        """根据 DepartmentTask 生成搜索关键词 —— LLM 自主决定（带字符串拼接兜底）。

        Phase 2 Agent化：调 LLM 输出 SearchStrategy，失败时 fallback 到
        原有的 core_topic + focus_areas 拼接逻辑。
        """
        cfg = self.config

        try:
            messages = build_search_strategy_prompt(task, project_summary)
            strategy: SearchStrategy = await self.llm.chat_structured(
                messages=messages,
                output_schema=SearchStrategy,
                max_tokens=1024,
            )
            if strategy.queries:
                print(f"  [{cfg.display_name}] LLM 搜索策略: {strategy.reasoning}")
                return strategy.queries
        except Exception as e:
            log_error(cfg.display_name, f"搜索策略 LLM 调用失败: {type(e).__name__}: {e}，"
                      f"fallback 到字符串拼接")

        # ---- Fallback: 原有拼接逻辑 ----
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

    # ------------------------------------------------------------------
    # State 构造（统一）
    # ------------------------------------------------------------------

    def _build_state(
        self,
        raw_result: object,
        project_summary: str,
        task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot],
        cycle_count: int,
    ) -> object:
        """从 LLM 输出构造本部门 State。"""
        cfg = self.config
        return cfg.state_cls(
            summary=getattr(raw_result, "summary", None),
            key_points=getattr(raw_result, "key_points", []),
            overall_confidence=getattr(raw_result, "overall_confidence", 0.0),
            status=AgentStatus.PASSED,
            conclusion=getattr(raw_result, "conclusion", ""),
            recommendations=getattr(raw_result, "recommendations", []),
            gaps=getattr(raw_result, "gaps", []),
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=cycle_count,
        )

    def _build_fallback_state(
        self,
        project_summary: str,
        task: DepartmentTask,
        sub_slots: dict[str, SubAgentSlot],
        cycle_count: int,
        error_msg: str,
    ) -> object:
        """LLM 调用失败时的兜底 State。"""
        cfg = self.config
        return cfg.state_cls(
            summary=f"{cfg.display_name}分析失败: {error_msg[:200]}",
            key_points=[],
            overall_confidence=0.0,
            status=AgentStatus.UNCERTAIN,
            project={"summary": project_summary},
            focus_direction=", ".join(task.focus_areas),
            sub_agents=sub_slots,
            cycle_count=cycle_count,
        )
