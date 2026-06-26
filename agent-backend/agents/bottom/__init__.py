"""
底层 Agent 包 —— 数据采集层。

职责：
- 调用 Search Provider 获取网络数据
- 调 LLM 从原始搜索结果中提取结构化发现
- 输出统一的 SubAgentOutput 格式
"""
