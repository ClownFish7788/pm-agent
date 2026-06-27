"""
PM Agent 后端入口。

两种运行模式：
  === 模式 1：控制台脚本（MVP） ===
  poetry run python main.py "你的项目描述"

  示例：
  poetry run python main.py "我想做一个宠物社交App，连接同城的宠物主人"

  === 模式 2：FastAPI 服务（Phase 2 预留） ===
  路由：
    POST /analyze  — SSE 流式分析端点（Phase 2 启用）
    GET  /health   — 健康检查

  启动：
  poetry run uvicorn main:app --reload --port 8000

环境变量要求：
  DEEPSEEK_API_KEY  — DeepSeek API 密钥（必需）
  TAVILY_API_KEY    — Tavily Search API 密钥（必需）

使用前请先：
  1. cp .env.example .env
  2. 编辑 .env 填入真实 API Key
  3. poetry install

如果 IDE 提示 "无法解析导入"：
  请将 VS Code 的 Python 解释器切换到 .venv/Scripts/python.exe
  Ctrl+Shift+P → Python: Select Interpreter → 选择 .venv
"""

from __future__ import annotations

import os
import sys

# =============================================================================
# 0. 立即修复 Windows 终端编码（必须在任何 print 之前）
# =============================================================================
# Windows 中文版终端默认 GBK 编码，无法输出 emoji（🔧✅❌ 等）。
# 这会导致 UnicodeEncodeError，表现为程序直接崩溃无输出。
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 极少数环境不支持 reconfigure，忽略

# =============================================================================
# 0.5 自动检测并切换到 Poetry venv（如果当前 Python 不是 venv 里的）
# =============================================================================

def _find_venv_python() -> str | None:
    """查找本项目的 Poetry venv Python 可执行文件路径。

    Poetry 配置了 virtualenvs.in-project=true，所以 venv 在
    本项目 agent-backend/.venv 下。

    返回：
        venv Python 的完整路径，找不到则返回 None
    """
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _venv_dir = os.path.join(_script_dir, ".venv")

    if not os.path.isdir(_venv_dir):
        return None

    if sys.platform == "win32":
        _candidate = os.path.join(_venv_dir, "Scripts", "python.exe")
    else:
        _candidate = os.path.join(_venv_dir, "bin", "python")

    if os.path.isfile(_candidate):
        return _candidate
    return None


def _is_running_in_venv() -> bool:
    """判断当前 Python 进程是否已经在 Poetry venv 中运行。

    对比当前可执行文件路径和 venv 中的 Python 路径。
    """
    _venv = _find_venv_python()
    if _venv is None:
        return False
    return os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(os.path.abspath(_venv))


# 如果不在 venv 中，自动重新用 venv Python 启动自己
if not _is_running_in_venv():
    _venv_python = _find_venv_python()
    if _venv_python is not None:
        # 用 venv Python 重新执行当前脚本，传递相同参数
        os.execv(_venv_python, [_venv_python] + sys.argv)
    # 如果找不到 venv，继续用当前 Python（依赖可能不全，但让后续 import 报错）

# =============================================================================
# 1. 加载 .env 文件（必须在其他项目内 import 之前）
# =============================================================================
# python-dotenv 会把 .env 中的变量注入 os.environ
try:
    from dotenv import load_dotenv  # noqa: E402  (import 必须在 venv 检测之后)

    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
    print(f"[dotenv] 已加载环境变量: {_env_path}")
except ImportError:
    print("[dotenv] python-dotenv 未安装，跳过 .env 加载")
    print("         安装: pip install python-dotenv")
except Exception as e:
    print(f"[dotenv] .env 加载失败: {e}")

# ---- 项目内 import ----
from agents.middle.market import MarketLeader
from agents.top import TopAgent
from dag.graph import build_graph as _build_graph
from llm.deepseek import DeepSeekProvider
from schemas import GlobalState, ProjectInfo
from search.tavily import TavilyProvider


# =============================================================================
# 模式 1：控制台脚本
# =============================================================================

async def run_console(project_description: str, thread_id: str | None = None) -> None:
    """控制台模式 —— 完整分析链路，所有输出打印到终端。

    这是 MVP 的主要运行方式。创建 Provider，构建 DAG，
    调用 graph.ainvoke() 执行全链路分析。

    Checkpoint 支持：
    - 每次执行自动保存状态到 MemorySaver
    - 中断后可用 --resume <thread_id> 恢复
    - thread_id 默认为 "console-{timestamp}"

    参数：
        project_description：用户的项目描述文本
        thread_id：可选，用于 checkpoint 恢复的会话 ID
    """
    # ---- 步骤 1：创建 Provider ----
    print("🔧 初始化 Provider...")

    try:
        llm = DeepSeekProvider()
        print(f"  ✅ LLM: {llm.provider_name} ({llm.model})")
    except ValueError as e:
        print(f"  ❌ LLM 初始化失败: {e}")
        sys.exit(1)

    try:
        search = TavilyProvider()
        print(f"  ✅ Search: {search.provider_name}")
    except (ValueError, ImportError) as e:
        print(f"  ❌ Search 初始化失败: {e}")
        sys.exit(1)

    # ---- 步骤 2：构建初始 State ----
    import time
    if thread_id is None:
        thread_id = f"console-{int(time.time())}"

    config = {"configurable": {"thread_id": thread_id}}

    initial_state = GlobalState(
        project=ProjectInfo(description=project_description),
    )

    # ---- 步骤 3：构建 LangGraph 图并执行 ----
    print("🔧 构建 DAG...")
    graph = _build_graph(llm, search)
    print(f"  ✅ DAG 编译完成 (checkpoint: MemorySaver, thread: {thread_id})")

    print(f"\n🚀 开始分析...\n")
    try:
        final_state = await graph.ainvoke(initial_state, config)
        print(f"\n✅ 分析流程结束 (thread: {thread_id})")
    except Exception as e:
        print(f"\n❌ 分析过程出错: {type(e).__name__}: {e}")
        print(f"   💡 可用相同 thread_id 恢复: python main.py --resume {thread_id}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# =============================================================================
# 模式 2：FastAPI 服务（Phase 2 预留骨架）
# =============================================================================

# 尝试导入 FastAPI（如果未安装 poetry 依赖，跳过）
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn

    _fastapi_available = True
except ImportError:
    _fastapi_available = False


if _fastapi_available:
    # ---- 创建 FastAPI 应用 ----
    app = FastAPI(
        title="PM Agent Backend",
        description="AI 项目经理分析系统的 Agent 后端",
        version="0.1.0",
    )

    @app.get("/health")
    async def health_check():
        """健康检查端点。

        返回后端服务状态。前端可在发起分析前调此端点确认后端存活。
        """
        return {
            "status": "ok",
            "service": "pm-agent-backend",
            "version": "0.1.0",
        }

    @app.post("/analyze")
    async def analyze(request_data: dict):
        """分析端点 —— 【Phase 2 预留，MVP 未实现】。

        计划接收前端发来的项目描述，通过 SSE 流式推送分析进度。
        MVP 阶段返回占位响应，请使用控制台模式。

        参数：
            request_data：{"description": "用户项目描述", ...}

        返回：
            占位 JSON
        """
        return JSONResponse(
            status_code=501,
            content={
                "status": "not_implemented",
                "message": "SSE 分析端点尚未实现，请使用控制台模式: python main.py '项目描述'",
            },
        )

else:
    # FastAPI 未安装时，app 变量为 None
    app = None


# =============================================================================
# 入口
# =============================================================================

if __name__ == "__main__":
    import asyncio

    # === 解析命令行参数 ===
    if len(sys.argv) < 2:
        print("用法:")
        print("  python main.py \"你的项目描述\"")
        print("  python main.py --resume <thread_id>  # 从 checkpoint 恢复")
        print()
        print("示例:")
        print("  python main.py \"我想做一个宠物社交App，连接同城的宠物主人\"")
        print("  python main.py --resume console-1719500000")
        print()
        print("或启动 FastAPI 服务:")
        print("  uvicorn main:app --reload --port 8000")
        sys.exit(0)

    if sys.argv[1] == "--resume":
        if len(sys.argv) < 3:
            print("❌ --resume 需要指定 thread_id")
            print("   示例: python main.py --resume console-1719500000")
            sys.exit(1)
        thread_id = sys.argv[2]
        # 恢复模式：传入空项目描述（实际从 checkpoint 恢复，不需要）
        asyncio.run(run_console("(从 checkpoint 恢复)", thread_id=thread_id))
    else:
        project_description = sys.argv[1]
        asyncio.run(run_console(project_description))
