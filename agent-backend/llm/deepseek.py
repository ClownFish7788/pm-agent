"""
DeepSeek LLM Provider 实现。

使用 OpenAI 兼容的 API 协议。DeepSeek API 完全兼容 OpenAI SDK，
只需要改 base_url 和 api_key 即可。

切换方式（未来）：
    只需创建新的 Provider 类（如 OpenAIProvider），继承 BaseLLMProvider，
    实现同样的两个方法。然后在初始化时替换即可。

环境变量：
    DEEPSEEK_API_KEY：DeepSeek API 密钥（必需）
    DEEPSEEK_BASE_URL：API 地址（默认 https://api.deepseek.com）
    DEEPSEEK_MODEL：模型名称（默认 deepseek-chat）

使用示例：
    provider = DeepSeekProvider()
    reply = await provider.chat([
        {"role": "user", "content": "你好"}
    ])
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from .base import BaseLLMProvider


# =============================================================================
# DeepSeek Provider 实现
# =============================================================================


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API 的 Provider 实现。

    底层使用 openai.AsyncOpenAI SDK（因为 DeepSeek API 完全兼容 OpenAI 格式）。
    只需在初始化时指定 DeepSeek 的 base_url 和 api_key 即可。

    属性：
        provider_name：固定返回 "DeepSeek"
        model：当前使用的模型名称
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """初始化 DeepSeek 客户端。

        参数：
            api_key：DeepSeek API 密钥。默认从环境变量 DEEPSEEK_API_KEY 读取
            base_url：API 地址。默认从 DEEPSEEK_BASE_URL 读取，最终回退到 https://api.deepseek.com
            model：模型名。默认从 DEEPSEEK_MODEL 读取，最终回退到 deepseek-chat
        """
        # ---- 读取配置（优先级：参数 > 环境变量 > 默认值） ----
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self._base_url = base_url or os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        if not self._api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY 未设置！请设置环境变量或在初始化时传入 api_key 参数。\n"
                "  export DEEPSEEK_API_KEY=sk-xxxxx\n"
                "或:\n"
                "  provider = DeepSeekProvider(api_key='sk-xxxxx')"
            )

        # ---- 创建 OpenAI 兼容客户端（指向 DeepSeek 服务器） ----
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    # ------------------------------------------------------------------
    # 接口实现
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """返回 Provider 名称，用于日志打印"""
        return "DeepSeek"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """发送消息列表给 DeepSeek，返回自由文本。

        参数说明见 BaseLLMProvider.chat()。

        内部流程：
        1. 将 messages 传给 DeepSeek API
        2. 等待回复
        3. 提取 response.choices[0].message.content
        4. 返回纯文本
        """
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]  # OpenAI SDK 接受 dict
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # 提取回复文本
            content = response.choices[0].message.content
            return content if content is not None else ""

        except Exception as e:
            # 任何错误都包装后上抛，由上层 Agent 决定如何处理
            raise RuntimeError(
                f"[{self.provider_name}] chat() 调用失败: {type(e).__name__}: {e}"
            ) from e

    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> BaseModel:
        """发送消息给 DeepSeek，返回 Pydantic 结构化对象。

        参数说明见 BaseLLMProvider.chat_structured()。

        内部流程：
        1. 在 system prompt 末尾追加「必须返回 JSON，格式如下：{schema}」
        2. 调用 chat()
        3. 尝试解析返回的 JSON 为 output_schema 实例
        4. 如果解析失败，返回一个空壳对象（字段全为默认值）+ 打印错误
           （这样上游不会因为一次格式错误而整个链路崩溃）
        """
        # ---- 步骤 1：构建「强制 JSON 输出」的增强版 messages ----
        schema_json = json.dumps(
            output_schema.model_json_schema(), ensure_ascii=False, indent=2
        )

        # 在最后一条消息后面追加格式约束（作为新的 user message）
        enforced_messages = list(messages)  # 不修改原始列表
        enforced_messages.append({
            "role": "user",
            "content": (
                f"请严格按以下 JSON Schema 格式返回，不要输出任何 JSON 之外的内容：\n"
                f"```json\n{schema_json}\n```\n"
                f"注意：只返回合法的 JSON，不要包裹在 markdown 代码块中。"
            ),
        })

        # ---- 步骤 2：调用 chat ----
        try:
            raw_text = await self.chat(
                enforced_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception:
            raise  # chat() 内部已经包装了异常

        # ---- 步骤 3：解析 JSON 并创建 Pydantic 对象 ----
        # 尝试从回复中提取 JSON（可能被包裹在 ```json ... ``` 中）
        json_str = self._extract_json(raw_text)

        try:
            data = json.loads(json_str)
            return output_schema.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            # JSON 解析失败：打印错误，返回一个空壳对象
            # 空壳对象所有字段取默认值，上游可据此判断「该 Agent 输出无效」
            print(f"  ⚠️  [{self.provider_name}] chat_structured() JSON 解析失败: {e}")
            print(f"  ⚠️  原始回复前 500 字符: {raw_text[:500]}")
            # 尝试构造空壳
            try:
                return output_schema()
            except Exception:
                raise RuntimeError(
                    f"[{self.provider_name}] chat_structured() JSON 解析失败且无法构造空壳对象: {e}"
                ) from e

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(raw_text: str) -> str:
        """从 LLM 回复中提取 JSON 字符串。

        LLM 有时会在 JSON 外面包裹 markdown 代码块标记（```json ... ```），
        有时会加一些解释文字。本方法尽量鲁棒地提取纯 JSON。

        参数：
            raw_text：LLM 的原始回复文本

        返回：
            提取出的 JSON 字符串（去除了包裹标记和首尾空白）
        """
        text = raw_text.strip()

        # 情况 1：被 ```json ... ``` 包裹
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
            return text

        # 情况 2：被 ``` ... ``` 包裹（无语言标记）
        if text.startswith("```"):
            text = text[3:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
            return text

        # 情况 3：找到第一个 { 到最后一个 } 作为 JSON
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            return text[brace_start:brace_end + 1]

        # 情况 4：原样返回
        return text
