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
        # 失败时使用默认计划
        plan = ExecutionPlan(
            steps=[MiddleAgentType.MARKET_RESEARCH],
            skipped=[m for m in MiddleAgentType if m != MiddleAgentType.MARKET_RESEARCH],
            skip_reasons={
                m.value: "MVP 阶段仅启用市场调研"
                for m in MiddleAgentType
                if m != MiddleAgentType.MARKET_RESEARCH
            },
            focus_areas=["市场规模", "用户画像"],
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
    new_calls = state.total_api_calls + 1
    log_budget(new_calls, state.max_api_calls)

    return {
        "execution_plan": plan,
        "total_api_calls": new_calls,
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
    # 中层 Leader 调用 LLM 1 次
    # 每个底层 Agent 调用 LLM 1 次（搜索 + 提取）
    bottom_count = len(market_state.sub_agents)
    new_calls = state.total_api_calls + 1 + bottom_count

    log_budget(new_calls, state.max_api_calls)

    return {
        "market_research": market_state,
        "total_api_calls": new_calls,
        "current_phase": "market_done",
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
            confidence_label = {
                "high": "🟢高",
                "medium": "🟡中",
                "low": "🟠低",
                "uncertain": "🔴存疑",
            }.get(point.confidence_level, "⚪未知")

            print(f"\n    {i}. [{confidence_label}] {point.title}")
            print(f"       {point.content}")
            print(f"       📎 来源数: {point.source_count}")
    else:
        print(f"\n  【市场调研】⚠️ 无数据")
        errors.append("市场调研未产生结果")

    # ---- 其余中层（MVP 为 None） ----
    for name in ["competitor_analysis", "product_design", "future_direction", "change_plan"]:
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
