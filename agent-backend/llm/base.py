"""
LLM Provider 抽象基类。

定义了所有 LLM Provider 必须遵守的「合同」（接口）。
上层 Agent 只依赖这个抽象类，不依赖具体的 DeepSeek / OpenAI / 通义千问。

类比：USB-C 充电口标准
- BaseLLMProvider = USB-C 接口规范（只定义形状和电压）
- DeepSeekProvider = 华为充电头（具体实现）
- OpenAIProvider = 小米充电头（具体实现，未来加）

上层 Agent 只认 USB-C（Base），不关心插的是华为还是小米。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类 —— 所有大模型实现的统一入口。

    每个具体 Provider（如 DeepSeekProvider）必须实现以下方法：
    - chat()：自由文本对话
    - chat_structured()：返回结构化 JSON（由 Pydantic 校验）

    内置 call_count 计数器：因为整个调用链共享同一个 LLM 实例，
    子类在 chat()/chat_structured() 中 +1，顶层直接读 llm.call_count
    就是精确的总调用次数，不需要上层"猜"底层做了几次调用。
    """

    def __init__(self) -> None:
        """初始化 Provider，设置调用计数器为 0。"""
        self.call_count: int = 0

    # ------------------------------------------------------------------
    # 子类必须填写的元信息
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称，如 'DeepSeek'、'OpenAI'。

        用于日志打印和错误追踪，不参与业务逻辑。
        """
        ...

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """发送消息列表给 LLM，返回自由文本。

        参数：
            messages：标准消息列表，每条格式 {"role": "user"|"assistant"|"system", "content": "..."}
            temperature：创造性温度（0=几乎不变，1=最创造）。分析任务建议 0.1-0.4
            max_tokens：最大输出 token 数
            **kwargs：传给底层 SDK 的额外参数（预留扩展）

        返回：
            LLM 回复的纯文本字符串

        用法：
            reply = await llm.chat([
                {"role": "system", "content": "你是一个市场分析专家"},
                {"role": "user", "content": "分析宠物经济趋势"},
            ])
            # reply = "根据调研，宠物经济呈现以下趋势..."
        """
        ...

    @abstractmethod
    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> BaseModel:
        """发送消息给 LLM，要求返回结构化 JSON，并校验为 Pydantic 对象。

        这是 Agent 间通信的核心方法——保证输出格式一定正确，
        下一个 Agent 可以安全地读取字段。

        参数：
            messages：同 chat()
            output_schema：期望的 Pydantic 模型类。LLM 输出的 JSON 会被解析为此类的实例
            temperature：结构化输出建议 0.1-0.2（更低的创造性 = 更高的格式一致性）
            max_tokens：最大输出 token 数
            **kwargs：传给底层 SDK 的额外参数

        返回：
            经过 Pydantic 校验的模型实例（如 SubAgentOutput、AnalysisPoint 等）

        用法：
            result = await llm.chat_structured(
                messages=[...],
                output_schema=SubAgentOutput,
            )
            # result.summary      ← 可以直接 . 访问字段，IDE 自动补全
            # result.top_findings ← 类型安全
        """
        ...
