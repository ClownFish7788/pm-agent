"""
中层 Agent 包 —— 分析综合层。

职责：
- 调度底层 Agent（决定搜索什么、搜几次）
- 收集底层发现，调 LLM 综合分析
- 输出 AnalysisPoint[] + MarketResearchState
"""
