"""LLM Provider abstraction — unified interface for different model backends.

Usage:
    from app.services.llm_provider import get_provider
    provider = get_provider("deepseek")  # or "mock"
    async for sse_data in provider.stream_chat(messages, "deepseek"):
        ...
"""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator

import httpx

from app.config import settings


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract base for LLM streaming providers."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completions as SSE delta JSON strings.

        Yields strings like:
            {"choices":[{"delta":{"content":"Hello"}}]}
            {"choices":[{"delta":{"reasoning_content":"..."}}]}
            [DONE]
        """
        ...


# ---------------------------------------------------------------------------
# DeepSeek provider
# ---------------------------------------------------------------------------

class DeepSeekProvider(LLMProvider):
    """Streaming provider for DeepSeek API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.default_model = default_model or settings.deepseek_model
        self.max_tokens = max_tokens or settings.deepseek_max_tokens

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        """Call DeepSeek streaming API and yield SSE delta strings."""
        thinking_type = "enabled" if model == "deepseek-think" else "disabled"
        reasoning_effort = "high" if model == "deepseek-think" else None

        payload: dict = {
            "model": self.default_model,
            "messages": messages,
            "stream": True,
            "max_tokens": self.max_tokens,
            "thinking": {"type": thinking_type},
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if abort_event and abort_event.is_set():
                        break

                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        content = line[6:]  # strip "data: " prefix
                        if content.strip() == "[DONE]":
                            yield "[DONE]"
                            break
                        yield content
                    elif line.strip().startswith("{"):
                        try:
                            import json
                            json.loads(line.strip())
                            yield line.strip()
                        except json.JSONDecodeError:
                            continue


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

MOCK_TEXT = """# 模拟回复

这是一个**模拟回复**，用于演示 Markdown 渲染效果。

## 代码示例

```typescript
function quickSort(arr: number[]): number[] {
  if (arr.length <= 1) return arr
  const pivot = arr[0]!
  const left = arr.slice(1).filter(x => x < pivot)
  const right = arr.slice(1).filter(x => x >= pivot)
  return [...quickSort(left), pivot, ...quickSort(right)]
}
```

## 数学公式

行内公式：\\(E = mc^2\\)

块级公式：
\\[\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}\\]

## 列表

1. 第一项
2. 第二项
3. 第三项

> 这是一个引用块。

感谢你的提问！
"""


class MockProvider(LLMProvider):
    """Fake streaming provider for development/testing."""

    def __init__(self, chunk_size: int = 100, interval_ms: int = 50):
        self.chunk_size = chunk_size
        self.interval_ms = interval_ms

    async def stream_chat(
        self,
        messages: list[dict],
        model: str = "mock",
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        """Simulate streaming with mock markdown content."""
        import json

        interval = self.interval_ms / 1000.0
        index = 0

        while index < len(MOCK_TEXT):
            if abort_event and abort_event.is_set():
                break
            chunk = MOCK_TEXT[index: index + self.chunk_size]
            yield json.dumps(
                {"choices": [{"delta": {"content": chunk}}]},
                ensure_ascii=False,
            )
            index += self.chunk_size
            await asyncio.sleep(interval)

        yield "[DONE]"


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_providers: dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    """Get or create a named provider instance (singleton per name)."""
    if name not in _providers:
        if name == "mock":
            _providers[name] = MockProvider()
        elif name in ("deepseek", "deepseek-think"):
            _providers[name] = DeepSeekProvider()
        else:
            raise ValueError(f"Unknown provider: {name}")
    return _providers[name]


def register_provider(name: str, provider: LLMProvider) -> None:
    """Register a custom provider."""
    _providers[name] = provider
