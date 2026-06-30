"""
中层市场调研 Leader Agent。

职责：
- 接收顶层下发的项目信息 + 关注方向
- 搜索市场数据 → 审核 → 驳回循环 → 综合分析
- 填充 MarketResearchState 的 Public 字段

所有核心逻辑由 BaseMiddleLeader 提供，本类仅提供部门配置。
"""

from __future__ import annotations

from agents.middle import BaseMiddleLeader, MiddleLeaderConfig
from prompts.templates import build_market_leader_prompt
from schemas import MarketResearchState


class MarketLeader(BaseMiddleLeader):
    """市场调研中层 Leader —— 关注市场规模、用户画像、商业模式。"""

    config = MiddleLeaderConfig(
        dept_key="market_research",
        display_name="市场调研",
        sub_id_prefix="market_query",
        state_cls=MarketResearchState,
        prompt_builder=build_market_leader_prompt,
    )
