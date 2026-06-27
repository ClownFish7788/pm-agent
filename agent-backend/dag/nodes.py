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
from prompts.templates import build_top_agent_prompt
from schemas import (
    ExecutionPlan,
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

async def node_aggregate(state: GlobalState) -> dict:
    """DAG 节点 3 —— 汇总所有中层结果，打印最终分析看板。

    职责：
    1. 读取各中层 State 的 Public 字段
    2. 打印结构化看板
    3. 收集统计信息

    MVP：只有 market_research 一个中层有数据，其余为 None。

    参数：
        state：当前 GlobalState（只读）

    返回：
        dict 包含 current_phase 和 errors 的更新
    """
    log_phase("DAG 节点 3/3: 汇总报告 — 分析看板")

    print(f"\n  {'─' * 56}")
    print(f"  📋 PM Agent 最终分析报告")
    print(f"  {'─' * 56}")

    errors: list[str] = list(state.errors)

    # ---- 市场调研看板 ----
    market = state.market_research
    if market is not None:
        print(f"\n  【市场调研】")
        print(f"  整体可信度: {market.overall_confidence:.0%}")
        print(f"  状态: {market.status.value}")
        if market.summary:
            print(f"  摘要: {market.summary}")
        print(f"\n  分析要点 ({len(market.key_points)} 条):")

        for i, point in enumerate(market.key_points, 1):
            confidence_label = _confidence_emoji(point.confidence_level)
            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【市场调研】⚠️ 无数据")
        errors.append("市场调研未产生结果")

    # ---- 竞品分析看板 ----
    competitor = state.competitor_analysis
    if competitor is not None:
        print(f"\n  【竞品分析】")
        print(f"  整体可信度: {competitor.overall_confidence:.0%}")
        print(f"  状态: {competitor.status.value}")
        if competitor.summary:
            print(f"  摘要: {competitor.summary}")
        print(f"\n  分析要点 ({len(competitor.key_points)} 条):")

        for i, point in enumerate(competitor.key_points, 1):
            confidence_label = _confidence_emoji(point.confidence_level)
            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【竞品分析】⚠️ 无数据")
        errors.append("竞品分析未产生结果")

    # ---- 产品设计看板 ----
    product = state.product_design
    if product is not None:
        print(f"\n  【产品设计】")
        print(f"  整体可信度: {product.overall_confidence:.0%}")
        print(f"  状态: {product.status.value}")
        if product.summary:
            print(f"  摘要: {product.summary}")
        print(f"\n  分析要点 ({len(product.key_points)} 条):")

        for i, point in enumerate(product.key_points, 1):
            confidence_label = _confidence_emoji(point.confidence_level)
            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【产品设计】⚠️ 无数据")
        errors.append("产品设计未产生结果")

    # ---- 未来方向看板 ----
    future = state.future_direction
    if future is not None:
        print(f"\n  【未来方向】")
        print(f"  整体可信度: {future.overall_confidence:.0%}")
        print(f"  状态: {future.status.value}")
        if future.summary:
            print(f"  摘要: {future.summary}")
        print(f"\n  分析要点 ({len(future.key_points)} 条):")

        for i, point in enumerate(future.key_points, 1):
            confidence_label = _confidence_emoji(point.confidence_level)
            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【未来方向】⚠️ 无数据")
        errors.append("未来方向未产生结果")

    # ---- 当下改变看板 ----
    change = state.change_plan
    if change is not None:
        print(f"\n  【当下改变】")
        print(f"  整体可信度: {change.overall_confidence:.0%}")
        print(f"  状态: {change.status.value}")
        if change.summary:
            print(f"  摘要: {change.summary}")
        print(f"\n  分析要点 ({len(change.key_points)} 条):")

        for i, point in enumerate(change.key_points, 1):
            confidence_label = _confidence_emoji(point.confidence_level)
            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【当下改变】⚠️ 无数据")
        errors.append("当下改变未产生结果")

    # ---- 其余中层（MVP 全部实现） ----
    for name in []:
        val = getattr(state, name, None)
        if val is not None:
            print(f"\n  【{name}】(预留)")

    # ---- 全局统计 ----
    print(f"\n  {'─' * 56}")
    print(f"  📊 统计")
    print(f"  LLM API 调用次数: {state.total_api_calls} / {state.max_api_calls}")
    if state.total_api_calls >= state.max_api_calls:
        print(f"  🔴 已达到 API 调用上限！")
    print(f"  非致命错误: {len(errors)} 条")
    for err in errors:
        print(f"    ⚠️  {err}")

    print(f"\n  ✅ 分析完成")
    print(f"  {'─' * 56}\n")

    return {
        "current_phase": "completed",
        "errors": errors,
    }
