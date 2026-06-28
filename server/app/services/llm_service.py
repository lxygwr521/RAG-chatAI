"""LLM service — persistence helpers for chat messages.

The streaming logic has moved to llm_provider.py (LLMProvider abstraction).
This module retains only the persistence helpers used by the chat endpoint.
"""

import time

from app.models.conversation import Message as MessageModel


def persist_user_message(
    conversation_id: str,
    content: str,
    files_json: str | None = None,
) -> MessageModel:
    """Create a MessageModel for a user message (caller must add to session)."""
    return MessageModel(
        conversation_id=conversation_id,
        role="user",
        content=content,
        files_json=files_json,
        timestamp=int(time.time() * 1000),
    )


def persist_assistant_message(
    conversation_id: str,
    content: str,
    thinking_content: str | None = None,
    citations_json: str | None = None,
) -> MessageModel:
    """Create a MessageModel for an assistant message."""
    return MessageModel(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        thinking_content=thinking_content,
        citations_json=citations_json,
        timestamp=int(time.time() * 1000),
    )
