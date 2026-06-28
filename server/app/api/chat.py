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
#2. 智能上下文处理与RAG增强
    # Build messages for the LLM, with context compression if needed
    llm_messages = list(request.messages)
# 2.1自动上下文压缩 防止超出上下文 
    # Context compression: check if we need to summarize older messages
    system_prompt = "You are a helpful assistant."
    history = [m for m in llm_messages if m["role"] != "system"]
    # Extract system prompt if present
    for m in llm_messages:
        if m["role"] == "system":
            system_prompt = m["content"]
            break

    from app.services.context_service import build_context, ContextParams

    ctx_result = await build_context(ContextParams(
        system_prompt=system_prompt,
        history=history[:-1] if history else [],  # exclude current user msg
        user_content=history[-1]["content"] if history else user_content,
        existing_summary=existing.summary_text,
        summarized_count=existing.summarized_count,
    ))

    # Persist new summary if compression happened
    if ctx_result.new_summary:
        existing.summary_text = ctx_result.new_summary["text"]
        existing.summarized_count = ctx_result.new_summary["covered_count"]

    # Use compressed messages
    llm_messages = ctx_result.messages
# 2.2 RAG知识库检索增强：
    # RAG: retrieve relevant knowledge base chunks if use_rag is enabled
    rag_citations = None
    if request.use_rag:
        try:
            from app.services.rag_service import augment_chat

            # Extract history from the compressed messages
            rag_history = [m for m in llm_messages if m["role"] in ("user", "assistant")]
            # The last message is the current user message
            rag_user = rag_history[-1]["content"] if rag_history else user_content
            rag_prev = rag_history[:-1] if rag_history else []

            rag_result = await augment_chat(
                system_prompt=system_prompt,
                history=rag_prev,
                user_content=rag_user,
            )

            if rag_result.chunks_used > 0:
                llm_messages = rag_result.messages
                rag_citations = rag_result.citations
        except Exception as e:
            # RAG unavailable — continue without it
            import logging
            logging.getLogger(__name__).warning(f"RAG retrieval failed, continuing without: {e}")
# 3.流式生成与结果保存

    # Run via AgentService — handles both direct LLM and Agent loop
    full_content = ""
    full_thinking = ""
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
        # Persist assistant message
        if full_content:
            citations_json = json.dumps(rag_citations, ensure_ascii=False) if rag_citations else None
            assistant_msg = persist_assistant_message(
                conv_id,
                full_content,
                full_thinking if full_thinking else None,
                citations_json=citations_json,
            )
            db.add(assistant_msg)

        # Update conversation timestamp
        existing.updated_at = int(time.time() * 1000)

    finally:
        # Always persist partial content on abort
        if full_content:
            existing_msg = await _get_last_assistant_msg(db, conv_id)
            if not existing_msg:
                assistant_msg = persist_assistant_message(
                    conv_id,
                    full_content,
                    full_thinking if full_thinking else None,
                )
                db.add(assistant_msg)


async def _get_last_assistant_msg(db: AsyncSession, conv_id: str):
    """Check if an assistant message was already persisted for this request."""
    from sqlalchemy import select
    from app.models.conversation import Message as MessageModel

    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conv_id)
        .where(MessageModel.role == "assistant")
        .order_by(MessageModel.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


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
