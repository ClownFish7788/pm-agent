"""
DAG 节点实现 —— 每个节点 = 一次 Agent 调度。

设计原则（来自 CLAUDE.md）：
- 每个节点是单一职责的 Agent 调用
- 输入/输出均为结构化数据（通过 GlobalState）
- 不可在一个节点内塞多个分析任务
- 节点只返回自己修改的字段，LangGraph 自动合并到全局 State

MVP 节点：
    node_top_planning()     → 调顶层 Agent 生成执行计划
    node_market_research()  → 调中层 MarketLeader 执行市场调研
    node_aggregate()        → 汇总各中层结果，打印最终报告

每个节点的签名（LangGraph 要求）：
    async def node_xxx(state: GlobalState) -> dict:
        # state 是当前全局状态（只读）
        # 返回 dict 只包含此节点修改的字段（局部更新）
"""

from __future__ import annotations

from agents.middle.market import MarketLeader
from agents.middle.competitor import CompetitorLeader
from agents.middle.product import ProductLeader
from agents.middle.future import FutureLeader
from agents.middle.change import ChangeLeader
from llm.base import BaseLLMProvider
from prompts.templates import build_top_agent_prompt, build_ceo_summary_prompt
from schemas import (
    ExecutionPlan,
    FinalReport,
    GlobalState,
    MarketResearchState,
    Message,
    MiddleAgentType,
    ProjectInfo,
    AgentStatus,
)
from search.base import BaseSearchProvider
from utils.logger import (
    log_agent_output,
    log_budget,
    log_error,
    log_phase,
    log_skip,
)


# =============================================================================
# 辅助函数
# =============================================================================

def _confidence_emoji(level: str) -> str:
    """将置信度等级转为 emoji 标签。"""
    return {
        "high": "🟢高",
        "medium": "🟡中",
        "low": "🟠低",
        "uncertain": "🔴存疑",
    }.get(level, "⚪未知")


# =============================================================================
# 节点 1：顶层规划
# =============================================================================

async def node_top_planning(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 1 —— 顶层 Agent 生成执行计划。

    职责：
    1. 调 LLM 分析用户项目描述
    2. 生成 ExecutionPlan（决定分析哪些维度）
    3. 打印计划到控制台

    参数：
        state：当前 GlobalState
        llm：LLM Provider（从外部注入，节点不自己创建）
        search_provider：Search Provider（传给下层用）

    返回：
        dict 包含 execution_plan、total_api_calls 的更新
    """
    log_phase("DAG 节点 1/3: 顶层规划 — 生成执行计划")

    project_text = state.project.description

    # ---- 调 LLM 生成执行计划 ----
    messages = build_top_agent_prompt(project_text)

    try:
        plan: ExecutionPlan = await llm.chat_structured(
            messages=messages,
            output_schema=ExecutionPlan,
        )
    except Exception as e:
        log_error("node_top_planning", f"LLM 调用失败: {type(e).__name__}: {e}")
        # 失败时使用默认计划（全部 5 个中层并行）
        plan = ExecutionPlan(
            steps=list(MiddleAgentType),
            skipped=[],
            skip_reasons={},
            focus_areas=["市场规模", "用户画像", "商业模式"],
            max_cycles=3,
        )

    # ---- 打印输出 ----
    log_agent_output(
        agent_name="DAG节点:TopPlanning",
        agent_emoji="🔷",
        input_summary=f"项目: {project_text[:100]}",
        output={
            "steps": [s.value for s in plan.steps],
            "skipped": [s.value for s in plan.skipped],
            "focus_areas": plan.focus_areas,
        },
    )

    for skipped_type in plan.skipped:
        reason = plan.skip_reasons.get(skipped_type.value, "无")
        log_skip(f"计划跳过: {skipped_type.value}", reason)

    # ---- 返回状态更新 ----
    # call_count 由 LLM Provider 内部自动计数（chat/chat_structured 每次调用 +1）
    # 因为整个调用链共享同一个 llm 实例，直接读 llm.call_count 就是精确值
    log_budget(llm.call_count, state.max_api_calls)

    return {
        "execution_plan": plan,
        "total_api_calls": llm.call_count,
        "current_phase": "planning_done",
    }


# =============================================================================
# 节点 2：市场调研
# =============================================================================

async def node_market_research(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 2 —— 中层市场调研 Leader 执行。

    职责：
    1. 读取顶层 ExecutionPlan 中的 focus_areas
    2. 创建 MarketLeader 并执行
    3. 将结果填入 state.market_research

    参数：
        state：当前 GlobalState
        llm：LLM Provider
        search_provider：Search Provider

    返回：
        dict 包含 market_research、total_api_calls 的更新
    """
    log_phase("DAG 节点 2/3: 市场调研 — 中层 Leader 执行")

    plan = state.execution_plan
    if plan is None:
        log_error("node_market_research", "执行计划为空，跳过市场调研")
        return {"errors": state.errors + ["执行计划为空，市场调研跳过"]}

    project_summary = state.project.description
    focus_areas = plan.focus_areas if plan.focus_areas else ["市场规模", "用户画像"]

    # ---- 创建并运行 MarketLeader ----
    market_leader = MarketLeader(
        llm=llm,
        search_provider=search_provider,
    )

    market_state: MarketResearchState = await market_leader.run(
        project_summary=project_summary,
        focus_areas=focus_areas,
    )

    # ---- 统计 API 调用 ----
    # 不估算，直接读 llm.call_count——中层和底层每次 chat/chat_structured 都自动 +1
    log_budget(llm.call_count, state.max_api_calls)

    return {
        "market_research": market_state,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 2b：竞品分析（可与市场调研并行）
# =============================================================================

async def node_competitor_analysis(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 2b —— 中层竞品分析 Leader 执行。

    与市场调研节点结构一致，可并行执行（LangGraph 自动 fan-out）。

    职责：
    1. 读取顶层 ExecutionPlan 中的 focus_areas
    2. 创建 CompetitorLeader 并执行
    3. 将结果填入 state.competitor_analysis

    参数：
        state：当前 GlobalState
        llm：LLM Provider
        search_provider：Search Provider

    返回：
        dict 包含 competitor_analysis、total_api_calls 的更新
    """
    log_phase("DAG 节点 2b: 竞品分析 — 中层 Leader 执行")

    plan = state.execution_plan
    if plan is None:
        log_error("node_competitor_analysis", "执行计划为空，跳过竞品分析")
        return {"errors": state.errors + ["执行计划为空，竞品分析跳过"]}

    project_summary = state.project.description
    # 竞品分析使用独立的搜索方向
    competitor_focus = ["直接竞品", "功能对比", "差异化机会"]

    competitor_leader = CompetitorLeader(
        llm=llm,
        search_provider=search_provider,
    )

    competitor_state = await competitor_leader.run(
        project_summary=project_summary,
        focus_areas=competitor_focus,
    )

    log_budget(llm.call_count, state.max_api_calls)

    return {
        "competitor_analysis": competitor_state,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 2c：产品设计（可与市场/竞品并行）
# =============================================================================

async def node_product_design(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 2c —— 中层产品设计 Leader 执行。

    职责：
    1. 创建 ProductLeader 并执行
    2. 将结果填入 state.product_design

    返回：
        dict 包含 product_design、total_api_calls 的更新
    """
    log_phase("DAG 节点 2c: 产品设计 — 中层 Leader 执行")

    plan = state.execution_plan
    if plan is None:
        log_error("node_product_design", "执行计划为空，跳过产品设计")
        return {"errors": state.errors + ["执行计划为空，产品设计跳过"]}

    project_summary = state.project.description
    product_focus = ["功能设计", "MVP范围", "用户体验"]

    product_leader = ProductLeader(
        llm=llm,
        search_provider=search_provider,
    )

    product_state = await product_leader.run(
        project_summary=project_summary,
        focus_areas=product_focus,
    )

    log_budget(llm.call_count, state.max_api_calls)

    return {
        "product_design": product_state,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 2d：未来方向（可与其他中层并行）
# =============================================================================

async def node_future_direction(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 2d —— 中层未来方向 Leader 执行。"""
    log_phase("DAG 节点 2d: 未来方向 — 中层 Leader 执行")

    future_leader = FutureLeader(llm=llm, search_provider=search_provider)
    future_state = await future_leader.run(
        project_summary=state.project.description,
        focus_areas=["技术趋势", "市场演进", "新兴机会"],
    )

    log_budget(llm.call_count, state.max_api_calls)
    return {
        "future_direction": future_state,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 2e：当下改变（可与其他中层并行）
# =============================================================================

async def node_change_plan(
    state: GlobalState,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
) -> dict:
    """DAG 节点 2e —— 中层当下改变 Leader 执行。"""
    log_phase("DAG 节点 2e: 当下改变 — 中层 Leader 执行")

    change_leader = ChangeLeader(llm=llm, search_provider=search_provider)
    change_state = await change_leader.run(
        project_summary=state.project.description,
        focus_areas=["冷启动", "资源需求", "增长策略"],
    )

    log_budget(llm.call_count, state.max_api_calls)
    return {
        "change_plan": change_state,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# 节点 3：汇总报告
# =============================================================================

async def node_aggregate(
    state: GlobalState,
    llm: BaseLLMProvider,
) -> dict:
    """DAG 节点 3 —— CEO 智能汇总：跨部门交叉分析。

    职责：
    1. 收集所有中层 State 的 Public 字段
    2. 调 LLM 做跨部门交叉分析 → FinalReport
    3. 格式化打印 CEO 综合报告

    参数：
        state：当前 GlobalState（含所有中层结果）
        llm：LLM Provider（注入用）

    返回：
        dict 包含 current_phase、errors、total_api_calls 的更新
    """
    log_phase("DAG 节点 3/3: CEO 汇总 — 跨部门交叉分析")

    errors: list[str] = list(state.errors)

    # ---- 构建部门数据字典 ----
    departments: dict[str, object | None] = {
        "market_research": state.market_research,
        "competitor_analysis": state.competitor_analysis,
        "product_design": state.product_design,
        "future_direction": state.future_direction,
        "change_plan": state.change_plan,
    }

    # ---- 调 LLM 做交叉分析 ----
    messages = build_ceo_summary_prompt(
        project_description=state.project.description,
        departments=departments,
    )

    try:
        report: FinalReport = await llm.chat_structured(
            messages=messages,
            output_schema=FinalReport,
            max_tokens=16384,  # CEO 七段报告，需大量输出
        )
    except Exception as e:
        log_error("node_aggregate", f"CEO 汇总分析失败: {type(e).__name__}: {e}")
        errors.append(f"CEO 汇总分析失败: {e}")
        return {
            "current_phase": "completed",
            "errors": errors,
            "total_api_calls": llm.call_count,
        }

    # ---- 打印 FinalReport ----
    _print_ceo_report(report, state)

    return {
        "current_phase": "completed",
        "errors": errors,
        "total_api_calls": llm.call_count,
    }


# =============================================================================
# FinalReport 打印辅助函数
# =============================================================================

def _print_ceo_report(report: FinalReport, state: GlobalState) -> None:
    """格式化打印多段式 CEO 综合分析报告。

    参数：
        report：LLM 产出的 FinalReport
        state：全局状态（用于统计）
    """
    dept_icons = {
        "market_research": "📊 市场调研",
        "competitor_analysis": "🏢 竞品分析",
        "product_design": "🎨 产品设计",
        "future_direction": "🔮 未来方向",
        "change_plan": "⚡ 当下改变",
    }

    print(f"\n  {'=' * 64}")
    print(f"  📋 PM Agent CEO 综合分析报告")
    print(f"  {'=' * 64}")

    # === 一、执行摘要 ===
    print(f"\n  {'─' * 64}")
    print(f"  一、执行摘要")
    print(f"  {'─' * 64}")
    print(f"  {report.executive_summary}")

    # === 二、各部门报告 ===
    print(f"\n  {'─' * 64}")
    print(f"  二、各部门分析报告")
    print(f"  {'─' * 64}")

    for dept_key, dept_label in dept_icons.items():
        ceo_summary = report.department_summaries.get(dept_key, "")
        dept_state = getattr(state, dept_key, None)

        print(f"\n  {dept_label}")
        print(f"  {'─' * 48}")

        if ceo_summary:
            print(f"  CEO 提炼: {ceo_summary}")
        elif dept_state is None:
            print(f"  ⚠️ 该部门未产出结果")
            continue
        else:
            print(f"  (无 CEO 提炼)")

        if dept_state is not None:
            conf = getattr(dept_state, "overall_confidence", 0.0)
            status = getattr(dept_state, "status", None)
            status_str = status.value if hasattr(status, "value") else "?"
            conclusion = getattr(dept_state, "conclusion", "") or ""
            recommendations = getattr(dept_state, "recommendations", []) or []
            gaps = getattr(dept_state, "gaps", []) or []

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

            key_points = getattr(dept_state, "key_points", [])
            if key_points:
                print(f"  ┌ 分析要点 ({len(key_points)} 条):")
                for kp in key_points:
                    title = getattr(kp, "title", "")
                    conf_level = getattr(kp, "confidence_level", "")
                    print(f"  │ [{conf_level}] {title}")

    # === 三、综合评分 ===
    score = report.overall_score
    score_bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
    score_emoji = "🟢" if score >= 70 else ("🟡" if score >= 40 else "🔴")
    print(f"\n  {'─' * 64}")
    print(f"  三、综合可行性评分")
    print(f"  {'─' * 64}")
    print(f"  {score_emoji} {score:.0f}/100  [{score_bar}]")

    # === 四、跨部门交叉洞察 ===
    print(f"\n  {'─' * 64}")
    print(f"  四、跨部门交叉洞察 ({len(report.cross_insights)} 条)")
    print(f"  {'─' * 64}")
    for i, ci in enumerate(report.cross_insights, 1):
        dims = ", ".join(ci.involved_dimensions) if ci.involved_dimensions else "无"
        print(f"\n  {i}. {ci.title}")
        print(f"     {ci.insight}")
        print(f"     🏷️ 涉及: {dims} | 置信度: {ci.confidence:.0%}")
    if not report.cross_insights:
        print(f"  (无交叉洞察)")

    # === 五、战略建议 ===
    print(f"\n  {'─' * 64}")
    print(f"  五、综合战略建议 ({len(report.recommendations)} 条)")
    print(f"  {'─' * 64}")
    for i, rec in enumerate(report.recommendations, 1):
        dims = ", ".join(rec.related_dimensions) if rec.related_dimensions else "无"
        print(f"\n  P{rec.priority} [{i}] {rec.title}")
        print(f"     {rec.rationale}")
        print(f"     🏷️ 依据: {dims}")

    # === 六、风险 ===
    print(f"\n  {'─' * 64}")
    print(f"  六、风险与不确定性 ({len(report.risks)} 条)")
    print(f"  {'─' * 64}")
    for i, risk in enumerate(report.risks, 1):
        sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk.severity, "⚪")
        print(f"\n  {sev_emoji} [{risk.severity}] {risk.title}")
        print(f"     {risk.description}")
        print(f"     🏷️ 来源: {risk.related_dimension}")
    if not report.risks:
        print(f"  (无显著风险)")

    # === 七、各部门可信度 ===
    print(f"\n  {'─' * 64}")
    print(f"  七、各部门可信度")
    print(f"  {'─' * 64}")
    for dim, conf in report.dimension_confidence.items():
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        label = dept_icons.get(dim, dim)
        print(f"  {label:20s} {conf:.0%} [{bar}]")

    # === 全局统计 ===
    print(f"\n  {'=' * 64}")
    print(f"  📊 LLM API 调用: {state.total_api_calls} / {state.max_api_calls}")
    print(f"  📊 非致命错误: {len(state.errors)} 条")
    for err in state.errors:
        print(f"    ⚠️  {err}")
    print(f"\n  ✅ 分析完成")
    print(f"  {'=' * 64}\n")
