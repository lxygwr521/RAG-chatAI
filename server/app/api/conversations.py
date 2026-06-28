"""Conversation CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.conversation import Conversation as ConversationModel, Message as MessageModel
from app.schemas.chat import ConversationCreate, ConversationOut, MessageOut

router = APIRouter(prefix="/api")


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """List all conversations with message counts."""
    result = await db.execute(
        select(ConversationModel).order_by(ConversationModel.updated_at.desc())
    )
    conversations = result.scalars().all()

    out = []
    for conv in conversations:
        count_result = await db.execute(
            select(func.count(MessageModel.id)).where(
                MessageModel.conversation_id == conv.id
            )
        )
        count = count_result.scalar() or 0
        out.append(
            ConversationOut(
                id=conv.id,
                title=conv.title,
                model=conv.model,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=count,
            )
        )
    return out


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    body: ConversationCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    conv = ConversationModel(
        id=str(uuid.uuid4()),
        title=body.title,
        model=body.model,
    )
    db.add(conv)
    await db.flush()
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a conversation and all its messages."""
    conv = await db.get(ConversationModel, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    return {"detail": "Deleted"}


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conv_id: str,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a conversation, paginated."""
    conv = await db.get(ConversationModel, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conv_id)
        .order_by(MessageModel.timestamp.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            thinking_content=m.thinking_content,
            files_json=m.files_json,
            citations_json=m.citations_json,
            timestamp=m.timestamp,
        )
        for m in messages
    ]
