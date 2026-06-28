"""Agent service — orchestrates LLM + Tools in a ReAct loop.

Phase 2 (current): Skeleton — delegates to LLM provider directly (no Agent loop yet).
Phase 3 (planned): ReAct / function-calling loop with tool execution.

Architecture:
    AgentService
      ├── LLMProvider    (DeepSeek / Mock)
      ├── ToolRegistry   (registered tools)
      └── SSE events     (delta, tool_call, tool_result, done)
"""

import asyncio
import json
from typing import AsyncGenerator

from app.core.sse import (
    SSEEvent,
    delta_event,
    done_event,
)
from app.services.llm_provider import LLMProvider, get_provider
from app.services.tool_registry import ToolRegistry, tool_registry
from app.tools.base import BaseTool, ToolResult


class AgentService:
    """Orchestrates LLM + Tools.

    Phase 2 behavior:
      - If no tools are registered → straight LLM streaming
      - If tools are registered → skeleton that can be upgraded to ReAct
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.provider = provider or get_provider("deepseek")
        self.registry = registry or tool_registry

    @property
    def has_tools(self) -> bool:
        return len(self.registry) > 0

    async def run(
        self,
        messages: list[dict],
        model: str = "deepseek",
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run the agent with the given messages.

        Yields typed SSEEvent objects (delta, tool_call, tool_result, done).
        """
        if not self.has_tools:
            # Phase 2: no tools → straight LLM streaming
            async for raw in self.provider.stream_chat(messages, model, abort_event):
                if abort_event and abort_event.is_set():
                    break
                if raw == "[DONE]":
                    yield done_event()
                    break
                try:
                    parsed = json.loads(raw)
                    delta = parsed.get("choices", [{}])[0].get("delta", {})
                    yield delta_event(
                        content=delta.get("content"),
                        reasoning_content=delta.get("reasoning_content"),
                    )
                except json.JSONDecodeError:
                    pass
        else:
            # Phase 3 placeholder: ReAct loop
            async for event in self._agent_loop(messages, model, abort_event):
                yield event

    async def _agent_loop(
        self,
        messages: list[dict],
        model: str,
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Placeholder: ReAct agent loop. Will be implemented in Phase 3."""
        # For now, fall back to straight streaming
        async for raw in self.provider.stream_chat(messages, model, abort_event):
            if abort_event and abort_event.is_set():
                break
            if raw == "[DONE]":
                yield done_event()
                break
            try:
                parsed = json.loads(raw)
                delta = parsed.get("choices", [{}])[0].get("delta", {})
                yield delta_event(
                    content=delta.get("content"),
                    reasoning_content=delta.get("reasoning_content"),
                )
            except json.JSONDecodeError:
                pass

    async def execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute a registered tool by name. Used by the Agent loop."""
        tool = self.registry.get(name)
        if not tool:
            return ToolResult(
                success=False,
                content="",
                tool_name=name,
                error=f"Tool not found: {name}",
            )
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                tool_name=name,
                error=str(e),
            )

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool in the agent's registry."""
        self.registry.register(tool)

    def list_tools(self) -> list["BaseTool"]:
        """List all registered tools."""
        return self.registry.get_all()


# Global singleton
agent_service = AgentService()
