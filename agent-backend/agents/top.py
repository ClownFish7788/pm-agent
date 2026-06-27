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
            # 失败时使用默认计划（全部 5 个中层并行）
            state.execution_plan = ExecutionPlan(
                steps=list(MiddleAgentType),
                skipped=[],
                skip_reasons={},
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

            elif step_type == MiddleAgentType.FUTURE_DIRECTION:
                state.current_phase = "future_direction"
                future_leader = FutureLeader(llm=self.llm, search_provider=self.search_provider)
                future_state = await future_leader.run(
                    project_summary=project_summary,
                    focus_areas=["技术趋势", "市场演进", "新兴机会"],
                )
                state.future_direction = future_state
                state.total_api_calls = self.llm.call_count

            elif step_type == MiddleAgentType.CHANGE_PLAN:
                state.current_phase = "change_plan"
                change_leader = ChangeLeader(llm=self.llm, search_provider=self.search_provider)
                change_state = await change_leader.run(
                    project_summary=project_summary,
                    focus_areas=["冷启动", "资源需求", "增长策略"],
                )
                state.change_plan = change_state
                state.total_api_calls = self.llm.call_count

            else:
                # 其他中层类型（MVP 阶段不会走到这里）
                log_skip(step_type.value, "MVP 阶段未实现")

        log_budget(state.total_api_calls, state.max_api_calls)

    async def _phase_summarize(self, state: GlobalState) -> None:
        """阶段 3：CEO 智能汇总。

        调 LLM 对全部中层结果做跨部门交叉分析，产出 FinalReport。
        不再简单打印各部门数据——而是提炼交叉洞察、战略建议和风险。

        参数：
            state：全局状态（含所有中层结果）
        """
        log_phase("CEO 汇总分析 — 跨部门交叉分析")

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
            report: FinalReport = await self.llm.chat_structured(
                messages=messages,
                output_schema=FinalReport,
                max_tokens=16384,  # CEO 七段报告，需大量输出
            )
        except Exception as e:
            log_error("TopAgent(CEO)", f"汇总分析失败: {type(e).__name__}: {e}")
            # 失败时打印简单统计
            print(f"\n  ❌ CEO 汇总分析失败: {e}")
            print(f"  LLM API 调用: {self.llm.call_count} / {state.max_api_calls}")
            return

        state.total_api_calls = self.llm.call_count

        # ---- 打印 FinalReport 看板 ----
        self._print_final_report(report, state)

    # ------------------------------------------------------------------
    # 打印 FinalReport
    # ------------------------------------------------------------------

    def _print_final_report(self, report: FinalReport, state: GlobalState) -> None:
        """格式化打印多段式 CEO 综合分析报告。

        参数：
            report：LLM 产出的 FinalReport
            state：全局状态（用于统计）
        """
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

        dept_names = {
            "market_research": "📊 市场调研",
            "competitor_analysis": "🏢 竞品分析",
            "product_design": "🎨 产品设计",
            "future_direction": "🔮 未来方向",
            "change_plan": "⚡ 当下改变",
        }

        for dept_key, dept_label in dept_names.items():
            # 打印 CEO 提炼
            ceo_summary = report.department_summaries.get(dept_key, "")
            # 读原始部门数据
            dept_state = getattr(state, dept_key, None)

            print(f"\n  {dept_label}")
            print(f"  {'─' * 48}")

            if ceo_summary:
                print(f"  CEO 提炼: {ceo_summary}")
            elif dept_state is None:
                print(f"  ⚠️ 该部门未产出结果")
                continue
            else:
                print(f"  (CEO 未提炼)")

            # 部门原始指标
            if dept_state is not None:
                conf = getattr(dept_state, "overall_confidence", 0.0)
                status = getattr(dept_state, "status", None)
                status_str = status.value if hasattr(status, "value") else "?"
                conclusion = getattr(dept_state, "conclusion", "") or ""
                recommendations = getattr(dept_state, "recommendations", []) or []
                gaps = getattr(dept_state, "gaps", []) or []

                print(f"  可信度: {conf:.0%} | 状态: {status_str}")

                if conclusion:
                    print(f"  ┌ 部门结论:")
                    print(f"  │ {conclusion}")

                if recommendations:
                    print(f"  ┌ 部门建议:")
                    for r in recommendations:
                        print(f"  │ • {r}")

                if gaps:
                    print(f"  ┌ 数据缺口:")
                    for g in gaps:
                        print(f"  │ • {g}")

                # 分析要点
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
            label = dept_names.get(dim, dim)
            print(f"  {label:20s} {conf:.0%} [{bar}]")

        # === 全局统计 ===
        print(f"\n  {'=' * 64}")
        print(f"  📊 LLM API 调用: {state.total_api_calls} / {state.max_api_calls}")
        print(f"  📊 非致命错误: {len(state.errors)} 条")
        for err in state.errors:
            print(f"    ⚠️  {err}")
        print(f"\n  ✅ 分析完成")
        print(f"  {'=' * 64}\n")
