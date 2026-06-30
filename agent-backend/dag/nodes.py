"""
DAG 节点实现 —— 每个节点 = 一次 Agent 调度。

Phase 2 Agent化：从 7 个独立节点简化为 3 个。
- node_top_planning：Top LLM 动态生成 3-7 个部门的执行计划
- node_execute_departments：asyncio.gather 并发执行所有部门
- node_aggregate：CEO 跨部门交叉分析 + 打印报告
"""

from __future__ import annotations

import asyncio

from agents.middle import (
    DEPARTMENT_NAME_MAP,
    BaseMiddleLeader,
)
from llm.base import BaseLLMProvider
from prompts.templates import (
    build_top_agent_prompt,
    build_ceo_summary_prompt,
)
from schemas import (
    DepartmentState,
    DepartmentTask,
    ExecutionPlan,
    FinalReport,
    GlobalState,
)
from search.base import BaseSearchProvider
from utils.logger import (
    log_agent_output,
    log_budget,
    log_error,
    log_phase,
    log_skip,
)
from utils.progress import ProgressTracker


# =============================================================================
# 节点 1：顶层规划
# =============================================================================

async def node_top_planning(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    tracker: ProgressTracker | None = None,
) -> dict:
    """DAG 节点 1 —— Top LLM 动态生成执行计划（3-7 个部门）。

    返回：execution_plan、total_api_calls、current_phase 更新。
    """
    log_phase("DAG 节点 1/3: 顶层规划")

    if state.execution_plan is not None:
        print("  ⏭️  执行计划已存在，跳过（checkpoint 恢复）")
        log_budget(llm.call_count, state.max_api_calls)
        return {"current_phase": "planning_done"}

    messages = build_top_agent_prompt(state.project.description)

    try:
        plan: ExecutionPlan = await llm.chat_structured(
            messages=messages,
            output_schema=ExecutionPlan,
        )
    except Exception as e:
        log_error("node_top_planning", f"LLM 调用失败: {e}")
        # Fallback: 5 个预置部门全部执行
        from schemas import KNOWN_DEPARTMENT_TYPES, KNOWN_DEPARTMENT_NAMES
        plan = ExecutionPlan(
            tasks=[
                DepartmentTask(
                    agent_type=dt,
                    display_name=KNOWN_DEPARTMENT_NAMES.get(dt, dt),
                    core_topic="",
                    focus_areas=["市场规模", "用户画像"],
                )
                for dt in KNOWN_DEPARTMENT_TYPES
            ],
            skipped=[],
            skip_reasons={},
            max_cycles=3,
        )

    log_agent_output(
        agent_name="DAG节点:TopPlanning",
        agent_emoji="",
        input_summary=f"项目: {state.project.description[:100]}",
        output={
            "task_count": len(plan.tasks),
            "tasks": {t.agent_type: t.display_name for t in plan.tasks},
            "skipped": plan.skipped,
        },
    )

    for skipped_type in plan.skipped:
        reason = plan.skip_reasons.get(skipped_type, "无")
        log_skip(f"计划跳过: {skipped_type}", reason)

    if tracker is not None:
        tracker.plan_generated(
            plan_data={
                "task_count": len(plan.tasks),
                "skipped_count": len(plan.skipped),
                "tasks": {t.agent_type: {"display_name": t.display_name, "focus_areas": t.focus_areas, "metrics": t.metrics} for t in plan.tasks},
                "skipped": plan.skipped,
            },
            call_count=llm.call_count,
        )
        tracker.budget(llm.call_count, state.max_api_calls)

    log_budget(llm.call_count, state.max_api_calls)

    return {
        "execution_plan": plan,
        "total_api_calls": llm.call_count,
        "current_phase": "planning_done",
    }


# =============================================================================
# 节点 2：动态执行所有部门
# =============================================================================

async def node_execute_departments(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    *,
    tracker: ProgressTracker | None = None,
) -> dict:
    """DAG 节点 2 —— 读 plan.tasks，asyncio.gather 并发执行所有部门。

    每个部门的执行流程（BaseMiddleLeader.run）：
    1. LLM 生成搜索策略
    2. 并行搜索 + LLM 筛选
    3. 审核 + 驳回循环（最多 3 轮）
    4. LLM 综合分析（含 metrics 自评）
    """

    plan = state.execution_plan
    if plan is None or not plan.tasks:
        log_error("node_execute_departments", "执行计划为空，无部门可执行")
        return {"errors": state.errors + ["执行计划为空"]}

    log_phase(f"DAG 节点 2/3: 执行 {len(plan.tasks)} 个部门")
    for t in plan.tasks:
        print(f"  ▸ {t.display_name or t.agent_type}: {len(t.focus_areas)} 个方向, "
              f"{len(t.metrics)} 个指标")

    async def run_one(task: DepartmentTask) -> tuple[str, DepartmentState | None, str | None]:
        """执行一个部门，异常内部化。"""
        dept_key = task.agent_type
        try:
            display_name = task.display_name or DEPARTMENT_NAME_MAP.get(dept_key, dept_key)
            leader = BaseMiddleLeader(
                llm=llm,
                search_provider=search_provider,
                tracker=tracker,
                dept_key=dept_key,
                display_name=display_name,
            )
            result = await leader.run(
                project_summary=state.project.description,
                task=task,
            )
            return (dept_key, result, None)
        except Exception as exc:
            log_error(dept_key, f"部门执行异常: {exc}")
            if tracker is not None:
                tracker.error(f"部门 {dept_key} 执行异常: {exc}", department=dept_key)
            return (dept_key, None, str(exc))

    # 并行执行
    results = await asyncio.gather(*[run_one(task) for task in plan.tasks])

    # 汇总结果
    department_results: dict[str, DepartmentState] = dict(state.department_results)
    for dept_key, dept_state, error in results:
        if dept_state is not None:
            department_results[dept_key] = dept_state
        elif error is not None:
            dept_name = DEPARTMENT_NAME_MAP.get(dept_key, dept_key)
            department_results[dept_key] = DepartmentState(
                summary=f"执行失败: {error[:200]}",
            )

    log_budget(llm.call_count, state.max_api_calls)

    return {
        "department_results": department_results,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 3：CEO 智能汇总
# =============================================================================

async def node_aggregate(
    state: GlobalState,
    llm: BaseLLMProvider,
    *,
    tracker: ProgressTracker | None = None,
) -> dict:
    """DAG 节点 3 —— CEO 跨部门交叉分析。

    从 state.department_results 读取所有部门的输出，调 LLM 产出 FinalReport。
    """
    log_phase("DAG 节点 3/3: CEO 汇总 — 跨部门交叉分析")

    errors: list[str] = list(state.errors)
    departments: dict[str, object | None] = dict(state.department_results)

    messages = build_ceo_summary_prompt(
        project_description=state.project.description,
        departments=departments,
    )

    try:
        report: FinalReport = await llm.chat_structured(
            messages=messages,
            output_schema=FinalReport,
            max_tokens=16384,
        )
    except Exception as e:
        log_error("node_aggregate", f"CEO 汇总失败: {e}")
        errors.append(f"CEO 汇总失败: {e}")
        if tracker is not None:
            tracker.error(f"CEO 汇总失败: {e}", phase="completed")
        return {
            "current_phase": "completed",
            "errors": errors,
            "total_api_calls": llm.call_count,
        }

    if tracker is not None:
        tracker.budget(llm.call_count, state.max_api_calls)
        tracker.final_report_done(report, llm.call_count)

    _print_ceo_report(report, state)

    return {
        "current_phase": "completed",
        "errors": errors,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# FinalReport 打印
# =============================================================================

def _print_ceo_report(report: FinalReport, state: GlobalState) -> None:
    """格式化打印 CEO 综合报告，从 department_results 动态读取。"""

    dept_labels = {
        key: f"{DEPARTMENT_NAME_MAP.get(key, '')} " + ("" if DEPARTMENT_NAME_MAP.get(key) else f"({key})")
        for key in state.department_results
    }

    print(f"\n  {'=' * 64}")
    print(f"  📋 PM Agent CEO 综合分析报告")
    print(f"  {'=' * 64}")

    # 一、执行摘要
    print(f"\n  {'─' * 64}")
    print(f"  一、执行摘要")
    print(f"  {'─' * 64}")
    print(f"  {report.executive_summary}")

    # 二、各部门报告
    print(f"\n  {'─' * 64}")
    print(f"  二、各部门分析报告")
    print(f"  {'─' * 64}")

    for dept_key, dept_state in state.department_results.items():
        dept_label = DEPARTMENT_NAME_MAP.get(dept_key, dept_key)
        ceo_summary = report.department_summaries.get(dept_key, "")

        print(f"\n  📊 {dept_label}")
        print(f"  {'─' * 48}")

        if ceo_summary:
            print(f"  CEO 提炼: {ceo_summary}")
        else:
            print(f"  (无 CEO 提炼)")

        conf = getattr(dept_state, "overall_confidence", 0.0)
        status = getattr(dept_state, "status", None)
        status_str = status.value if hasattr(status, "value") else "?"
        conclusion = getattr(dept_state, "conclusion", "") or ""
        recommendations = getattr(dept_state, "recommendations", []) or []
        gaps = getattr(dept_state, "gaps", []) or []
        metrics_coverage = getattr(dept_state, "metrics_coverage", {}) or {}

        print(f"  可信度: {conf:.0%} | 状态: {status_str}")

        if conclusion:
            print(f"  ┌ 部门结论: {conclusion}")
        if recommendations:
            print(f"  ┌ 部门建议:")
            for r in recommendations:
                print(f"  │ • {r}")
        if gaps:
            print(f"  ┌ 数据缺口:")
            for g in gaps:
                print(f"  │ • {g}")
        if metrics_coverage:
            print(f"  ┌ 指标完成:")
            for metric, coverage in metrics_coverage.items():
                print(f"  │ [{coverage}] {metric}")

        key_points = getattr(dept_state, "key_points", [])
        if key_points:
            print(f"  ┌ 分析要点 ({len(key_points)} 条):")
            for kp in key_points:
                title = getattr(kp, "title", "")
                conf_level = getattr(kp, "confidence_level", "")
                print(f"  │ [{conf_level}] {title}")

    # 三、综合评分
    score = report.overall_score
    score_bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
    score_emoji = "🟢" if score >= 70 else ("🟡" if score >= 40 else "🔴")
    print(f"\n  {'─' * 64}")
    print(f"  三、综合可行性评分")
    print(f"  {'─' * 64}")
    print(f"  {score_emoji} {score:.0f}/100  [{score_bar}]")

    # 四、交叉洞察
    print(f"\n  {'─' * 64}")
    print(f"  四、跨部门交叉洞察 ({len(report.cross_insights)} 条)")
    print(f"  {'─' * 64}")
    for i, ci in enumerate(report.cross_insights, 1):
        dims = ", ".join(ci.involved_dimensions)
        print(f"\n  {i}. {ci.title}")
        print(f"     {ci.insight}")
        print(f"     🏷️ 涉及: {dims} | 置信度: {ci.confidence:.0%}")

    # 五、战略建议
    print(f"\n  {'─' * 64}")
    print(f"  五、综合战略建议 ({len(report.recommendations)} 条)")
    print(f"  {'─' * 64}")
    for i, rec in enumerate(report.recommendations, 1):
        dims = ", ".join(rec.related_dimensions)
        print(f"\n  P{rec.priority} [{i}] {rec.title}")
        print(f"     {rec.rationale}")
        print(f"     🏷️ 依据: {dims}")

    # 六、风险
    print(f"\n  {'─' * 64}")
    print(f"  六、风险与不确定性 ({len(report.risks)} 条)")
    print(f"  {'─' * 64}")
    for i, risk in enumerate(report.risks, 1):
        sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk.severity, "⚪")
        print(f"\n  {sev_emoji} [{risk.severity}] {risk.title}")
        print(f"     {risk.description}")
        print(f"     🏷️ 来源: {risk.related_dimension}")

    # 七、可信度
    print(f"\n  {'─' * 64}")
    print(f"  七、各部门可信度")
    print(f"  {'─' * 64}")
    for dim, conf in report.dimension_confidence.items():
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        label = DEPARTMENT_NAME_MAP.get(dim, dim)
        print(f"  {label:20s} {conf:.0%} [{bar}]")

    # 全局统计
    print(f"\n  {'=' * 64}")
    print(f"  📊 LLM API 调用: {state.total_api_calls} / {state.max_api_calls}")
    print(f"  📊 非致命错误: {len(state.errors)} 条")
    for err in state.errors:
        print(f"    ⚠️  {err}")
    print(f"\n  分析完成")
    print(f"  {'=' * 64}\n")
