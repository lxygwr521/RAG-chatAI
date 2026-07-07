"""SSE streaming helpers — typed events and EventSourceResponse wrapper."""

import json
from dataclasses import dataclass
from typing import AsyncGenerator

from sse_starlette.sse import EventSourceResponse


# ---------------------------------------------------------------------------
# SSE Event types
# ---------------------------------------------------------------------------

@dataclass
class SSEEvent:
    """A typed SSE event with optional event name.

    SSE wire format (via EventSourceResponse):
        event: {event}
        data: {data}
    """

    data: str | dict
    event: str | None = None

    def to_dict(self) -> dict:
        result = {"data": self.data if isinstance(self.data, str) else json.dumps(self.data, ensure_ascii=False)}
        if self.event:
            result["event"] = self.event
        return result


# Factory functions for common event types

def delta_event(content: str | None = None, reasoning_content: str | None = None) -> SSEEvent:
    """LLM text delta: OpenAI-compatible {choices: [{delta: ...}]}."""
    delta: dict = {}
    if content is not None:
        delta["content"] = content
    if reasoning_content is not None:
        delta["reasoning_content"] = reasoning_content
    return SSEEvent(
        event="delta",
        data={"choices": [{"delta": delta}]},
    )


def tool_call_event(tool_name: str, tool_call_id: str, arguments: dict) -> SSEEvent:
    """Agent is calling a tool."""
    return SSEEvent(
        event="tool_call",
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments": arguments,
        },
    )


def tool_result_event(tool_call_id: str, tool_name: str, result: str, success: bool = True) -> SSEEvent:
    """Tool execution result."""
    return SSEEvent(
        event="tool_result",
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "result": result,
            "success": success,
        },
    )


def done_event(summary_text: str | None = None, summarized_count: int = 0) -> SSEEvent:
    """Stream completed. Optionally carries summary metadata for persistence."""
    if summary_text:
        return SSEEvent(
            event="done",
            data={"done": True, "summary_text": summary_text, "summarized_count": summarized_count},
        )
    return SSEEvent(event="done", data="[DONE]")


def error_event(message: str) -> SSEEvent:
    """Stream error."""
    return SSEEvent(event="error", data={"error": message})


