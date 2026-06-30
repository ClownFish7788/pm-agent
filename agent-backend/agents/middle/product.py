"""
中层产品设计 Leader Agent。

职责：
- 接收顶层下发的项目信息 + 关注方向
- 搜索产品设计数据 → 审核 → 驳回循环 → 综合分析
- 填充 ProductDesignState 的 Public 字段

所有核心逻辑由 BaseMiddleLeader 提供，本类仅提供部门配置。
"""

from __future__ import annotations

from agents.middle import BaseMiddleLeader, MiddleLeaderConfig
from prompts.templates import build_product_leader_prompt
from schemas import ProductDesignState


class ProductLeader(BaseMiddleLeader):
    """产品设计中层 Leader —— 关注功能优先级、MVP 范围、技术可行性。"""

    config = MiddleLeaderConfig(
        dept_key="product_design",
        display_name="产品设计",
        sub_id_prefix="product_query",
        state_cls=ProductDesignState,
        prompt_builder=build_product_leader_prompt,
    )
