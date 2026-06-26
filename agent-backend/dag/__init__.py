"""
DAG 编排层 —— LangGraph StateGraph 定义与编译。

职责：
- 定义 DAG 拓扑（谁先谁后，谁并行，条件路由）
- 编译为可执行的 Runnable
- 不写业务逻辑（业务逻辑在 agents/ 中）

三个角色：
    nodes.py       → 节点函数（每个节点调用一个 Agent）
    conditions.py  → 条件边判断（纯 Python 代码，不调 LLM）
    graph.py       → 图组装 + compile()

LangGraph 概念映射：
    Node  = 一个 async 函数（接收 state dict，返回 state 更新 dict）
    Edge  = A → B（执行完 A 后执行 B）
    Cond  = A → judge → B 或 C（根据 judge 返回值决定走哪条边）
    Loop  = 条件边指回自身（驳回重做，MVP 不启用）
"""
