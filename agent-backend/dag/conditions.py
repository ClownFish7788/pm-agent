"""
条件边判断函数 —— LangGraph 的路由逻辑。

每个条件函数接收 GlobalState，返回一个路由键（字符串）。
LangGraph 根据返回值决定走哪条边。

设计原则（来自 CLAUDE.md）：
- 条件边判断函数是纯 Python 代码，不调 LLM
- 迅速判断（< 100ms），不做复杂计算
- 返回值为路径标识符，对应 add_conditional_edges() 中注册的路径

MVP 阶段：
- 所有判断函数返回 "pass"（占位，不启用驳回）
- Phase 2 启用打分逻辑后，此处接入 ItemScore 判断
"""

from __future__ import annotations

from schemas import GlobalState


# =============================================================================
# 市场调研质量判断（MVP 占位 —— 始终通过）
# =============================================================================

def judge_market_quality(state: GlobalState) -> str:
    """判断市场调研结果是否合格，决定下一步走向。

    路由逻辑（Phase 2 启用）：
        "pass"       → 进入下一阶段（node_aggregate）
        "reject"     → 驳回重做（回到 node_market_research）【MVP 不启用】
        "uncertain"  → 标记存疑后继续（超过 3 轮驳回）【MVP 不启用】

    MVP 阶段：
        始终返回 "pass"，不做打分。

    参数：
        state：当前全局状态

    返回：
        "pass" | "reject" | "uncertain"（MVP 固定 "pass"）
    """
    # ===== MVP 占位：不做任何判断，直接通过 =====
    # Phase 2 实现代码（注释保留以便后续启用）：
    #
    # market = state.market_research
    # if market is None:
    #     return "pass"  # 无数据直接跳过
    #
    # if market.overall_confidence < 0.3:
    #     if state.get("retry_count", 0) >= state.execution_plan.max_cycles:
    #         return "uncertain"
    #     return "reject"
    #
    # return "pass"

    return "pass"


# =============================================================================
# 竞品分析质量判断（MVP —— 预留占位）
# =============================================================================

def judge_competitor_quality(state: GlobalState) -> str:
    """判断竞品分析结果是否合格（MVP 占位）。"""
    return "pass"


# =============================================================================
# 全局熔断判断
# =============================================================================

def judge_budget_exceeded(state: GlobalState) -> str:
    """判断是否超过 API 调用预算上限（熔断器）。

    路由逻辑：
        "continue"  → 预算未超，继续执行
        "stop"      → 预算超限，跳过后续节点，直接汇总

    参数：
        state：当前全局状态

    返回：
        "continue" | "stop"
    """
    if state.total_api_calls >= state.max_api_calls:
        print(f"  🔴 熔断！API 调用已达上限 ({state.total_api_calls}/{state.max_api_calls})")
        return "stop"
    return "continue"
