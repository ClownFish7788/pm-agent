"""
PM Agent 后端入口。

两种运行模式：
  === 模式 1：控制台脚本（MVP） ===
  python main.py "你的项目描述"

  示例：
  python main.py "我想做一个宠物社交App，连接同城的宠物主人"

  === 模式 2：FastAPI 服务（Phase 2 预留） ===
  路由：
    POST /analyze  — SSE 流式分析端点（Phase 2 启用）
    GET  /health   — 健康检查

  启动：
  uvicorn main:app --reload --port 8000

环境变量要求：
  DEEPSEEK_API_KEY  — DeepSeek API 密钥（必需）
  TAVILY_API_KEY    — Tavily Search API 密钥（必需）

使用前请先：
  1. cp .env.example .env
  2. 编辑 .env 填入真实 API Key
  3. poetry install
"""

from __future__ import annotations

import os
import sys

# ---- 加载 .env 文件（必须在其他 import 之前） ----
# python-dotenv 会把 .env 中的变量注入 os.environ
try:
    from dotenv import load_dotenv
    # 查找 agent-backend 目录下的 .env 文件
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(_env_path)
    print(f"✅ 已加载环境变量: {_env_path}")
except ImportError:
    print("⚠️  python-dotenv 未安装，跳过 .env 加载。安装: pip install python-dotenv")
except Exception as e:
    print(f"⚠️  .env 加载失败: {e}")

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

async def run_console(project_description: str) -> None:
    """控制台模式 —— 完整分析链路，所有输出打印到终端。

    这是 MVP 的主要运行方式。创建 Provider，构建 DAG，
    调用 graph.ainvoke() 执行全链路分析。

    参数：
        project_description：用户的项目描述文本
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
    initial_state = GlobalState(
        project=ProjectInfo(description=project_description),
    )

    # ---- 步骤 3：构建 LangGraph 图并执行 ----
    print("🔧 构建 DAG...")
    graph = _build_graph(llm, search)
    print("  ✅ DAG 编译完成")

    print(f"\n🚀 开始分析...\n")
    try:
        final_state = await graph.ainvoke(initial_state)
        print("\n✅ 分析流程结束")
    except Exception as e:
        print(f"\n❌ 分析过程出错: {type(e).__name__}: {e}")
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

    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法:")
        print("  python main.py \"你的项目描述\"")
        print()
        print("示例:")
        print("  python main.py \"我想做一个宠物社交App，连接同城的宠物主人\"")
        print()
        print("或启动 FastAPI 服务:")
        print("  uvicorn main:app --reload --port 8000")
        sys.exit(0)

    project_description = sys.argv[1]

    # 运行控制台模式
    asyncio.run(run_console(project_description))
