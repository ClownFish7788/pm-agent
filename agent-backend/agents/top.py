"""
顶层决策 Agent（CEO）—— 整个分析流程的入口。

职责：
1. 读取用户的项目描述
2. 调 LLM 生成 ExecutionPlan（决定分析哪些维度）
3. 按 ExecutionPlan 调度中层 Agent
4. 收集中层结果，打印汇总报告

MVP 简化：
- 不追问用户边界条件（假设用户输入已足够）
- 只调度 market_research 一个中层
- 不做驳回/重做
- 不生成 PDF/MD 导出（只打印到控制台）

使用示例：
    llm = DeepSeekProvider()
    search = TavilyProvider()

    ceo = TopAgent(llm, search)
    state = await ceo.run("我想做一个宠物社交App，帮助宠物主人互相认识、分享养宠经验")
    # state.market_research.key_points 是最终的分析结果
"""

from __future__ import annotations

from agents.middle.market import MarketLeader
from agents.middle.competitor import CompetitorLeader
from agents.middle.product import ProductLeader
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
from utils.logger import log_agent_output, log_error, log_phase, log_skip, log_budget


class TopAgent:
    """顶层决策 Agent —— 项目经理（CEO 角色）。

    不自己搜索数据，只做决策和调度。
    类比：项目会议上的 PM —— 问清楚需求，分配任务给各组长，最后汇总出报告。

    属性：
        llm：LLM Provider（依赖注入）
        search_provider：Search Provider（注入后传给中层）
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        search_provider: BaseSearchProvider,
    ) -> None:
        """初始化顶层 Agent。

        参数：
            llm：LLM Provider 实例
            search_provider：Search Provider 实例（传给中层用）
        """
        self.llm = llm
        self.search_provider = search_provider

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    async def run(self, project_description: str) -> GlobalState:
        """执行完整的分析流程。

        这是用户调用的唯一入口。一次调用走完：
        规划 → 调度中层 → 收集结果 → 汇总报告

        参数：
            project_description：用户的项目描述文本

        返回：
            GlobalState 实例（含执行计划和所有中层结果）
        """
        # ---- 初始化全局 State ----
        state = GlobalState(
            project=ProjectInfo(description=project_description),
            conversation_history=[
                Message(role="user", content=project_description)
            ],
            total_api_calls=0,
            max_api_calls=30,
            current_phase="init",
        )

        print()
        print("=" * 64)
        print("  🏗️  PM Agent — AI 项目经理分析系统")
        print("=" * 64)
        print(f"  用户输入: {project_description[:100]}")
        print("=" * 64)

        # ---- 阶段 1：顶层规划（生成执行计划） ----
        await self._phase_plan(state)

        # ---- 阶段 2：调度中层 —— MVP 只跑 market_research ----
        await self._phase_execute(state)

        # ---- 阶段 3：汇总报告 ----
        await self._phase_summarize(state)

        return state

    # ------------------------------------------------------------------
    # 阶段方法
    # ------------------------------------------------------------------

    async def _phase_plan(self, state: GlobalState) -> None:
        """阶段 1：顶层决策 —— 生成执行计划。

        调 LLM 分析用户的项目描述，决定分析哪些维度。

        参数：
            state：全局状态（会被原地修改，execution_plan 被填充）
        """
        log_phase("顶层规划 — 生成执行计划")

        project_text = state.project.description

        # 调 LLM 生成执行计划
        messages = build_top_agent_prompt(project_text)

        try:
            plan: ExecutionPlan = await self.llm.chat_structured(
                messages=messages,
                output_schema=ExecutionPlan,
            )
            state.execution_plan = plan
            state.total_api_calls = self.llm.call_count  # LLM Provider 内部自动计数
        except Exception as e:
            log_error("TopAgent", f"生成执行计划失败: {type(e).__name__}: {e}")
            # 失败时使用默认计划（市场 + 竞品 + 产品并行）
            enabled = (MiddleAgentType.MARKET_RESEARCH, MiddleAgentType.COMPETITOR_ANALYSIS, MiddleAgentType.PRODUCT_DESIGN)
            state.execution_plan = ExecutionPlan(
                steps=list(enabled),
                skipped=[m for m in MiddleAgentType if m not in enabled],
                skip_reasons={m.value: "MVP 阶段未实现" for m in MiddleAgentType if m not in enabled},
                focus_areas=["市场规模", "用户画像", "商业模式"],
                max_cycles=3,
            )

        # 类型收窄：execution_plan 在上述 try/except 两个分支中都会赋值
        plan = state.execution_plan
        assert plan is not None, "execution_plan 应在 _phase_plan 中赋值"

        # 打印执行计划
        log_agent_output(
            agent_name="TopAgent (CEO)",
            agent_emoji="🔷",
            input_summary=f"项目描述: {project_text[:100]}",
            output={
                "steps": [s.value for s in plan.steps],
                "skipped": [s.value for s in plan.skipped],
                "focus_areas": plan.focus_areas,
                "max_cycles": plan.max_cycles,
            },
        )

        # 打印跳过的中层
        for skipped_type in plan.skipped:
            reason = plan.skip_reasons.get(skipped_type.value, "无")
            log_skip(skipped_type.value, reason)

        # 打印预算
        log_budget(state.total_api_calls, state.max_api_calls)

    async def _phase_execute(self, state: GlobalState) -> None:
        """阶段 2：调度中层 Agent。

        按 ExecutionPlan 依次调度中层 Leader。
        MVP：只调 MarketLeader。

        参数：
            state：全局状态（会被原地修改，market_research 字段被填充）
        """
        plan = state.execution_plan
        if plan is None:
            log_error("TopAgent", "执行计划为空，跳过阶段 2")
            return

        log_phase("中层执行 — 市场调研")

        project_summary = state.project.description

        for step_type in plan.steps:
            if step_type == MiddleAgentType.MARKET_RESEARCH:
                state.current_phase = "market_research"

                # 创建中层 Leader
                market_leader = MarketLeader(
                    llm=self.llm,
                    search_provider=self.search_provider,
                )

                # 执行市场调研
                market_state: MarketResearchState = await market_leader.run(
                    project_summary=project_summary,
                    focus_areas=plan.focus_areas,
                )

                # 填入全局 State
                state.market_research = market_state

                # LLM 调用次数由 Provider 内部自动计数，直接读即可
                state.total_api_calls = self.llm.call_count

            elif step_type == MiddleAgentType.COMPETITOR_ANALYSIS:
                state.current_phase = "competitor_analysis"

                competitor_leader = CompetitorLeader(
                    llm=self.llm,
                    search_provider=self.search_provider,
                )

                competitor_state = await competitor_leader.run(
                    project_summary=project_summary,
                    focus_areas=["直接竞品", "功能对比", "差异化机会"],
                )

                state.competitor_analysis = competitor_state
                state.total_api_calls = self.llm.call_count

            elif step_type == MiddleAgentType.PRODUCT_DESIGN:
                state.current_phase = "product_design"

                product_leader = ProductLeader(
                    llm=self.llm,
                    search_provider=self.search_provider,
                )

                product_state = await product_leader.run(
                    project_summary=project_summary,
                    focus_areas=["功能设计", "MVP范围", "用户体验"],
                )

                state.product_design = product_state
                state.total_api_calls = self.llm.call_count

            else:
                # 其他中层类型（MVP 阶段不会走到这里）
                log_skip(step_type.value, "MVP 阶段未实现")

        log_budget(state.total_api_calls, state.max_api_calls)

    async def _phase_summarize(self, state: GlobalState) -> None:
        """阶段 3：汇总报告。

        将各中层的结果汇总，打印最终分析看板。
        MVP：只有 market_research 一个中层，所以汇总 = 打印市场调研结论。

        参数：
            state：全局状态（只读）
        """
        log_phase("汇总报告 — 分析看板")

        print(f"\n  {'─' * 56}")
        print(f"  📋 最终分析报告")
        print(f"  {'─' * 56}")

        # ---- 市场调研看板 ----
        market = state.market_research

        if market is not None:
            print(f"\n  【市场调研】")
            print(f"  可信度: {market.overall_confidence:.0%}")
            print(f"  状态: {market.status.value}")
            if market.summary:
                print(f"  摘要: {market.summary}")
            print(f"\n  分析要点 ({len(market.key_points)} 条):")

            for i, point in enumerate(market.key_points, 1):
                print(f"    {i}. [{point.confidence_level}] {point.title}")
                print(f"       {point.content[:120]}...")
                print(f"       来源数: {point.source_count}")
                print()

        # ---- 其余中层看板（MVP 为 None，跳过） ----
        if state.competitor_analysis is not None:
            print(f"\n  【竞品分析】(预留)")
        if state.product_design is not None:
            print(f"\n  【产品设计】(预留)")
        if state.future_direction is not None:
            print(f"\n  【未来方向】(预留)")
        if state.change_plan is not None:
            print(f"\n  【当下改变】(预留)")

        # ---- 全局统计 ----
        print(f"  {'─' * 56}")
        print(f"  📊 统计")
        print(f"  LLM API 调用次数: {state.total_api_calls} / {state.max_api_calls}")
        print(f"  非致命错误: {len(state.errors)} 条")

        if state.errors:
            for err in state.errors:
                print(f"    ⚠️  {err}")

        print(f"\n  ✅ 分析完成")
        print(f"  {'─' * 56}\n")
