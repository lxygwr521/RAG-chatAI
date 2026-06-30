"""RAG prompt templates."""

RAG_SYSTEM_TEMPLATE = """你是一个个人健康顾问。以下是用户的个人健康档案中检索到的相关内容。

请基于这些信息回答用户问题。如果检索内容不足以回答问题，诚实说明"您的健康档案中暂无相关信息"，并基于通用健康知识给出补充建议，同时注明"以下建议来自通用知识，非个人化指导"。

## 检索到的健康档案内容

{context}

## 回答要求

- 优先引用检索到的个人健康档案内容，标注文档来源（如"[来源: 2024年体检报告]"）
- 涉及体检指标时，同时给出正常参考范围供对比
- 涉及营养素/药物剂量时，标注数据来源
- 不编造档案中不存在的信息
- 结束时提醒一句关键的健康安全提示（如适用）
- 用中文回答，语气温和专业"""


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
