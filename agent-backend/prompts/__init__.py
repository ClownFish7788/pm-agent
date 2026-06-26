"""
Prompt 模板包 —— 所有 Agent 的 System Prompt 集中管理。

设计原则：
- 每个 Agent 对应一个 build_xxx_prompt() 函数
- 函数返回标准 messages 列表，可直接喂给 LLM Provider
- 动态参数（项目描述、搜索词等）通过函数参数注入
- MVP 用 Python 常量，Phase 2 可迁移到 YAML 文件
"""
