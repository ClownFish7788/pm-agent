"""
中层竞品分析 Leader Agent。

职责：
- 接收顶层下发的项目信息 + 关注方向
- 搜索竞品数据 → 审核 → 驳回循环 → 综合分析
- 填充 CompetitorState 的 Public 字段

所有核心逻辑由 BaseMiddleLeader 提供，本类仅提供部门配置。
"""

from __future__ import annotations

from agents.middle import BaseMiddleLeader, MiddleLeaderConfig
from prompts.templates import build_competitor_leader_prompt
from schemas import CompetitorState


class CompetitorLeader(BaseMiddleLeader):
    """竞品分析中层 Leader —— 关注直接/间接竞品、功能对比、差异化机会。"""

    config = MiddleLeaderConfig(
        dept_key="competitor_analysis",
        display_name="竞品分析",
        sub_id_prefix="competitor_query",
        state_cls=CompetitorState,
        prompt_builder=build_competitor_leader_prompt,
    )
