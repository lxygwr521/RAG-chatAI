"""Search knowledge base tool — wraps RAG retrieval as a LangChain @tool."""

from langchain_core.tools import tool

from app.services.rag_service import augment_chat

# Chunks with score below this threshold are considered "high confidence"
# ChromaDB cosine distance: 0 = identical, 2 = opposite. < 0.8 = good match.
HIGH_CONFIDENCE_THRESHOLD = 0.6


@tool
async def search_knowledge(query: str) -> str:
    """搜索本地知识库，获取与查询相关的文档片段。

    如果知识库有相关内容，基于检索结果回答并标注来源。
    如果知识库没有相关内容或相关度过低，工具会明确告知，此时应基于通用知识回答。
    """
    result = await augment_chat(
        system_prompt="",
        history=[],
        user_content=query,
    )

    if not result.chunks_used:
        return "【知识库无结果】知识库中未找到与查询相关的文档。请基于你的通用知识直接回答用户问题。"

    # Separate high vs low confidence results
    high_conf = [c for c in result.citations if c["score"] >= HIGH_CONFIDENCE_THRESHOLD]
    low_conf = [c for c in result.citations if c["score"] < HIGH_CONFIDENCE_THRESHOLD]

    if not high_conf and low_conf:
        parts = ["【知识库低相关】以下内容与问题关联较弱，仅供参考："]
        for i, c in enumerate(low_conf, 1):
            parts.append(f"[{i}] 来源: {c['document']} (相关度: {c['score']:.2f})\n{c['snippet']}")
        parts.append("\n如果以上内容无法回答问题，请基于通用知识回答。")
        return "\n\n".join(parts)

    parts = ["【知识库命中】找到以下相关内容："]
    for i, c in enumerate(high_conf, 1):
        parts.append(f"[{i}] 来源: {c['document']} (相关度: {c['score']:.2f})\n{c['snippet']}")
    return "\n\n".join(parts)
