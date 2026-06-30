"""
中层未来方向 Leader Agent。

职责：
- 接收顶层下发的项目信息 + 关注方向
- 搜索趋势数据 → 审核 → 驳回循环 → 综合分析
- 填充 FutureState 的 Public 字段

未来部门天然低可信度（0.4-0.7 正常），所有核心逻辑由 BaseMiddleLeader 提供。
"""

from __future__ import annotations

from agents.middle import BaseMiddleLeader, MiddleLeaderConfig
from prompts.templates import build_future_leader_prompt
from schemas import FutureState


class FutureLeader(BaseMiddleLeader):
    """未来方向中层 Leader —— 关注技术趋势、市场演进、中长期风险。"""

    config = MiddleLeaderConfig(
        dept_key="future_direction",
        display_name="未来方向",
        sub_id_prefix="future_query",
        state_cls=FutureState,
        prompt_builder=build_future_leader_prompt,
    )
