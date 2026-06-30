"""Agent service — LangChain Agent with Tool calling and context summarization.

Uses:
  - ChatOpenAI (base_url → DeepSeek) for LLM
  - langchain.agents.create_agent for Agent loop
  - SummarizationMiddleware for automatic context compression
  - SSE typed events for streaming + tool call transparency
"""

import asyncio
from typing import AsyncGenerator

from langchain.agents import create_agent
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_openai import ChatOpenAI

from app.config import settings
from app.core.sse import (
    SSEEvent,
    delta_event,
    tool_call_event,
    tool_result_event,
    done_event,
    error_event,
)
from app.tools.search_knowledge import search_knowledge

# Language prompt for Chinese-speaking assistant with tool use
SYSTEM_PROMPT = SYSTEM_PROMPT = """
你是一个智能助手。

# 工具调用策略
1. **必须调用 search_knowledge 工具**：当用户的问题明确涉及公司内部政策、产品专有名词、技术文档内容时。
2. **禁止调用 search_knowledge 工具**：当用户的问题属于通用常识（如“中国的首都是哪里”）、数学计算、闲聊时。
3. **不确定时**：优先使用 `search_knowledge` 工具（因为你即使搜不到，也可以基于自己的知识回答）。
4. 如果 `search_knowledge` 返回了内容，必须基于这些内容回答。
5. 如果 `search_knowledge` 返回为空，基于你的知识回答。
6. 引用来源时，标注返回结果中的文档名称。
7. 始终用中文回答。
"""


class AgentService:
    """ReAct Agent orchestrator using LangGraph with automatic summarization.

    SummarizationMiddleware replaces the custom context_service.py:
    - Before each model call, checks if total tokens exceed trigger threshold
    - If so: oldest messages → summary (via flash model), recent messages kept
    - No manual token counting or summary persistence needed
    """

    def __init__(self):
        self._tools = [search_knowledge]
        self._llm = ChatOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            max_tokens=settings.deepseek_max_tokens,
            temperature=0.7,
        )

        # Summarization middleware — automatic context compression
        # Trigger when 60K tokens OR 80 messages reached (whichever first)
        # Keep the 20 most recent messages verbatim, older ones → summary
        summarization = SummarizationMiddleware(
            model=ChatOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model="deepseek-v4-flash",
                max_tokens=400,
                temperature=0.3,
            ),
            trigger=[
                ("tokens", 60000),
                ("messages", 80),
            ],
            keep=("messages", 20),
        )

        self._agent = create_agent(
            model=self._llm,
            tools=self._tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[summarization],
        )

    @property
    def has_tools(self) -> bool:
        return len(self._tools) > 0

    async def run(
        self,
        messages: list[dict],
        model: str = "deepseek",
        abort_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run the Agent with the given messages, yielding SSE events.

        Streams LLM deltas and tool call/result events transparently.

        ``messages`` should include the full conversation context:
          - user/assistant history
          - the current user message (last)
        SummarizationMiddleware handles compression automatically.
        """
        # Convert all messages to LangChain-compatible format
        input_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") and m.get("content")
        ]

        full_content = ""

        try:
            # LangGraph agent streaming — yields message chunks + tool events
            # SummarizationMiddleware hooks into before_model automatically
            async for chunk in self._agent.astream(
                {"messages": input_messages},
                stream_mode="messages",
            ):
                if abort_event and abort_event.is_set():
                    break

                # chunk is a tuple: (message, metadata)
                if isinstance(chunk, tuple):
                    msg, meta = chunk

                    # LLM text delta
                    if hasattr(msg, "content") and msg.content:
                        text = msg.content if isinstance(msg.content, str) else str(msg.content)
                        full_content += text
                        yield delta_event(content=text)
                #  只是声明“我要调用工具”，此时工具尚未实际执行
                    # Tool call detected
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            yield tool_call_event(
                                tool_name=tc.get("name", "unknown"),
                                tool_call_id=tc.get("id", ""),
                                arguments=tc.get("args", {}),
                            )
            #    当chunk是字典且角色为"tool"时，说明这是工具执行完成后的结果返回：
                # Tool result
                elif isinstance(chunk, dict) and chunk.get("role") == "tool":
                    yield tool_result_event(
                        tool_call_id=chunk.get("tool_call_id", ""),
                        tool_name=chunk.get("name", "unknown"),
                        result=str(chunk.get("content", ""))[:500],
                        success=True,
                    )

            yield done_event()

        except Exception as e:
            yield error_event(str(e))


# Global singleton
agent_service = AgentService()
