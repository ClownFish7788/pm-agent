"""
Search Provider 包 —— 搜索引擎抽象层。

提供统一的搜索接口，使上层 Agent 不依赖具体搜索引擎。
切换搜索引擎时只需换一个 Provider 实现。

当前实现：
- TavilyProvider：Tavily Search API（MVP）
- base.BaseSearchProvider：抽象基类，定义 search() 合同
"""
