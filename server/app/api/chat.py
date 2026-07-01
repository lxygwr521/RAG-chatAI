"""POST /api/chat — SSE streaming chat endpoint with Agent support."""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db
from app.core.sse import SSEEvent
from app.models.conversation import Conversation as ConversationModel
from app.schemas.chat import ChatRequest
from app.services.agent_service import agent_service
from app.services.llm_service import (
    persist_user_message,
    persist_assistant_message,
)

router = APIRouter(prefix="/api")


async def _chat_event_generator(
    request: ChatRequest,
    db: AsyncSession,
    abort_event: asyncio.Event,
) -> AsyncGenerator[SSEEvent | str, None]:
    """Generate SSE events for a chat request, persisting messages to DB."""
    conv_id = request.conversation_id

    # Create conversation if not provided or doesn't exist in DB
    if not conv_id:
        conv_id = str(uuid.uuid4())
 # 1.对话准备与持久化
# 1.1获取或创建对话
    existing = await db.get(ConversationModel, conv_id)
    if not existing:
        existing = ConversationModel(
            id=conv_id,
            title="新对话",
            model=request.model,
        )
        db.add(existing)
        await db.flush()
    else:
        existing.updated_at = int(time.time() * 1000)
#1.2 持久化用户问题，存入数据库
    # Persist user message
    user_content = request.messages[-1]["content"] if request.messages else ""
    files_json = None
    if request.files:
        files_json = json.dumps([f.model_dump() for f in request.files])
    user_msg = persist_user_message(conv_id, user_content, files_json)
# 1.3生成对话标题
    # Auto-generate title from first user message if conversation is new
    if existing.title == "新对话" and user_content:
        existing.title = user_content[:20] + ("..." if len(user_content) > 20 else "")

    db.add(user_msg)
    await db.commit()  # 显式提交用户消息，EventSourceResponse 不会触发 get_db 的自动 commit
# 2. 构建 LLM 消息列表（上下文压缩由 AgentService 的 SummarizationMiddleware 自动处理）
    # SummarizationMiddleware 在 token > 60K 或消息 > 80 条时自动将旧消息压缩为摘要
    llm_messages = [m for m in request.messages]

    # Run via AgentService — Agent decides if/when to call tools (RAG, etc.)
    rag_citations = None
    full_content = ""
    full_thinking = ""
    assistant_persisted = False  # Track whether we already persisted the message
# 3.1调用Agent服务流式生成
    try:
        # llm_messages（包含系统提示词、历史总结、RAG上下文和当前问题）
        async for event in agent_service.run(llm_messages, request.model, abort_event):
            if abort_event.is_set():
                break

            # Extract content for persistence
            if isinstance(event, SSEEvent) and event.event == "delta":
                data = event.data if isinstance(event.data, dict) else json.loads(str(event.data))
                delta = data.get("choices", [{}])[0].get("delta", {})
                c = delta.get("content")
                rc = delta.get("reasoning_content")
                if c:
                    full_content += c
                if rc:
                    full_thinking += rc

            if isinstance(event, SSEEvent) and event.event == "done":
                yield event
                break

            yield event
# 3.2 RAG引用推送：
        # Yield RAG citations if any
        if rag_citations:
            yield SSEEvent(event="citations", data={"citations": rag_citations})
# 3.3 持久化助手消息
        # Persist assistant message (normal completion path)
        if full_content:
            citations_json = json.dumps(rag_citations, ensure_ascii=False) if rag_citations else None
            assistant_msg = persist_assistant_message(
                conv_id,
                full_content,
                full_thinking if full_thinking else None,
                citations_json=citations_json,
            )
            db.add(assistant_msg)
            assistant_persisted = True

        # Update conversation timestamp
        existing.updated_at = int(time.time() * 1000)
        await db.commit()  # 显式提交助手消息和会话时间戳

    finally:
        # Persist partial content on abort (only if not already persisted above)
        if full_content and not assistant_persisted:
            assistant_msg = persist_assistant_message(
                conv_id,
                full_content,
                full_thinking if full_thinking else None,
            )
            db.add(assistant_msg)
            await db.commit()  # 显式提交部分内容


@router.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream a chat response via SSE. Uses AgentService for routing.

    If tools are registered, the Agent can call them in a ReAct loop (Phase 3).
    Otherwise, delegates directly to the LLM provider.
    """
    abort_event = asyncio.Event()

    async def event_generator():
        async for sse_event in _chat_event_generator(request, db, abort_event):
            if await http_request.is_disconnected():
                abort_event.set()
                break
            if isinstance(sse_event, SSEEvent):
                yield sse_event.to_dict()
            elif isinstance(sse_event, dict):
                yield sse_event
            else:
                yield {"data": str(sse_event)}

    return EventSourceResponse(event_generator())
