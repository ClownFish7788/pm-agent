"""
中层当下改变 Leader Agent。

职责：
- 接收顶层下发的项目信息 + 关注方向
- 搜索启动策略数据 → 审核 → 驳回循环 → 综合分析
- 填充 ChangeState 的 Public 字段

关注"今天该干什么"——最务实的中层。所有核心逻辑由 BaseMiddleLeader 提供。
"""

from __future__ import annotations

from agents.middle import BaseMiddleLeader, MiddleLeaderConfig
from prompts.templates import build_change_leader_prompt
from schemas import ChangeState


class ChangeLeader(BaseMiddleLeader):
    """当下改变中层 Leader —— 关注 0→1 行动清单、资源需求、增长策略。"""

    config = MiddleLeaderConfig(
        dept_key="change_plan",
        display_name="当下改变",
        sub_id_prefix="change_query",
        state_cls=ChangeState,
        prompt_builder=build_change_leader_prompt,
    )
