"""
Agent 输出日志工具。

在整个 PM Agent 系统中，每个 Agent（顶层/中层/底层）调用完 LLM 后，
必须调用本模块的函数打印输出。这样开发者在控制台可以看到完整的思考链。

设计原则：
- 统一格式：所有 Agent 输出用同一种格式打印，方便对比
- 分层标识：用 emoji 区分 Agent 层级（🔷顶层 / 📊中层 / 🔍底层）
- 不依赖日志框架：纯 print，不引入 loguru / structlog 等额外依赖
"""

import json
from datetime import datetime


# =============================================================================
# 内部工具函数
# =============================================================================

def _timestamp() -> str:
    """生成当前时间戳字符串，格式 HH:MM:SS"""
    return datetime.now().strftime("%H:%M:%S")


def _divider(char: str = "─", width: int = 64) -> str:
    """生成分隔线，默认 64 字符宽"""
    return char * width


# =============================================================================
# 公开 API —— 供所有 Agent 调用
# =============================================================================


def log_phase(phase_name: str) -> None:
    """打印一个分析阶段的开始。

    用法：
        log_phase("市场调研")  →  打印醒目的阶段标题

    每个 DAG 大节点开始时调用一次，方便在控制台区分不同阶段。
    """
    print()
    print(_divider("="))
    print(f"  ⏩ [{_timestamp()}] 阶段开始: {phase_name}")
    print(_divider("="))
    print()


def log_agent_output(
    agent_name: str,
    agent_emoji: str,
    input_summary: str,
    output: dict | str,
) -> None:
    """打印一次 Agent（LLM 调用）的输入和输出。

    这是整个日志系统的核心函数。每次 Agent 调用完 LLM 后必须调用。

    参数：
        agent_name:  Agent 名称，如 "MarketLeader"、"SearchAgent#1"
        agent_emoji: 层级标识 emoji，如 "🔷"(顶层) "📊"(中层) "🔍"(底层)
        input_summary: 输入摘要（一句话描述 Agent 收到了什么）
        output: Agent 的输出，可以是 dict（结构化JSON）或 str（自由文本）

    输出格式示例：
        ┌──────────────────────────────────────────────────────────────
        │ 🔍 [SearchAgent#1]  @ 14:32:05
        │   输入: 搜索关键词 = "宠物社交App 市场规模 2025"
        │   输出:
        │     { "summary": "...", "top_findings": [...] }
        └──────────────────────────────────────────────────────────────
    """
    print(f"┌{_divider('─')}")
    print(f"│ {agent_emoji} [{agent_name}]  @ {_timestamp()}")
    print(f"│   输入: {input_summary}")
    print(f"│   输出:")

    if isinstance(output, dict):
        # dict 类型：用 JSON 格式化打印，ensure_ascii=False 保证中文可读
        output_str = json.dumps(output, ensure_ascii=False, indent=4)
        # 每行前面加 │ 前缀，保持缩进对齐
        for line in output_str.split("\n"):
            print(f"│     {line}")
    else:
        # 字符串类型：直接打印
        for line in str(output).split("\n"):
            print(f"│     {line}")

    print(f"└{_divider('─')}")
    print()


def log_error(agent_name: str, error_msg: str) -> None:
    """打印错误信息。

    用法：
        log_error("SearchAgent#1", "Tavily API 返回 429 限流")

    比 log_agent_output 更简洁，只输出错误信息，
    不会产生大量乱码干扰排查。
    """
    print(f"┌{_divider('─')}")
    print(f"│ ❌ [{agent_name}]  @ {_timestamp()}")
    print(f"│   错误: {error_msg}")
    print(f"└{_divider('─')}")
    print()


def log_skip(agent_name: str, reason: str) -> None:
    """打印跳过信息。

    当顶层计划决定跳过某个中层（如竞品分析不适用于当前项目）时调用。

    用法：
        log_skip("CompetitorLeader", "开源工具类项目无需竞品分析")
    """
    print(f"┌{_divider('─')}")
    print(f"│ ⏭️  [{agent_name}]  @ {_timestamp()}")
    print(f"│   跳过: {reason}")
    print(f"└{_divider('─')}")
    print()


def log_budget(total_calls: int, max_calls: int) -> None:
    """打印 Token 预算使用情况。

    每次 LLM 调用后调用一次，方便监控是否接近熔断线。

    用法：
        log_budget(5, 30)  → "📊 预算: 5 / 30 (剩余 25)"
    """
    remaining = max_calls - total_calls
    pct = total_calls / max_calls * 100
    bar_filled = int(pct / 10)  # 每 10% 一个方块

    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    status = (
        "✅" if pct < 50
        else "⚠️" if pct < 80
        else "🔴"
    )

    print(f"  {status} 预算: {total_calls:2d} / {max_calls}  [{bar}]  剩余 {remaining}")
    print()
