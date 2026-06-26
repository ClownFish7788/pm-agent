"""
LLM Provider 包 —— 大模型调用抽象层。

提供统一的 LLM 调用接口，使上层 Agent 不依赖具体模型厂商。
切换模型时只需换一个 Provider 实现，Agent 代码零修改。

当前实现：
- DeepSeekProvider：DeepSeek API（兼容 OpenAI 格式）
- base.BaseLLMProvider：抽象基类，定义 chat / chat_structured 合同
"""
