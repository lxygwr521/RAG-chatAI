"""RAG prompt templates."""

RAG_SYSTEM_TEMPLATE = """You are a helpful assistant with access to a knowledge base.

Use the following retrieved context to answer the user's question.
If the context does NOT contain relevant information, say so honestly and answer based on your own knowledge.

## Retrieved Context

{context}

## Guidelines

- Cite the source document when using information from the context (e.g., "[来源: filename]").
- Do NOT fabricate information not found in the context.
- Keep your answer concise and relevant."""


def build_rag_context(chunks) -> str:
    """Format retrieved chunks into a context string for the prompt."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[来源 {i}: {chunk.document}]\n{chunk.content}"
        )
    return "\n\n---\n\n".join(parts)


def build_rag_messages(
    system_prompt: str,
    history: list[dict],
    user_content: str,
    retrieved_chunks,
) -> list[dict]:
    """Build the full message list with RAG context injected into system prompt.

    Args:
        system_prompt: Original system prompt.
        history: Conversation history [{role, content}].
        user_content: Current user message.
        retrieved_chunks: List of RetrievedChunk from retriever.

    Returns:
        List of messages ready for the LLM.
    """
    context_text = build_rag_context(retrieved_chunks)
    rag_system = RAG_SYSTEM_TEMPLATE.format(context=context_text)

    # Merge with original system prompt
    if system_prompt and system_prompt != "You are a helpful assistant.":
        rag_system = f"{system_prompt}\n\n{rag_system}"

    messages: list[dict] = [{"role": "system", "content": rag_system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages


def build_citations(retrieved_chunks) -> list[dict]:
    """Build citation objects for the SSE response."""
    return [
        {
            "chunk_id": chunk.chunk_id,
            "document": chunk.document,
            "snippet": chunk.content[:200],
            # Cosine distance ≈ 0-2, convert to 0-1 similarity
            "score": round(max(0.0, 1.0 - chunk.score / 2.0), 4),
        }
        for chunk in retrieved_chunks
    ]
