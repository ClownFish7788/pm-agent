"""
Agent 包 —— 三层 Agent 架构的实现。

层级结构：
    agents/top.py             → 第 1 层：顶层决策 Agent（CEO）
    agents/middle/market.py    → 第 2 层：中层市场调研 Leader
    agents/bottom/search.py    → 第 3 层：底层搜索 Agent

依赖原则：上层依赖下层，下层不依赖上层。
"""
