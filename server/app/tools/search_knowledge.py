"""Search knowledge base tool — wraps RAG retrieval as a LangChain @tool."""

from langchain_core.tools import tool

from app.services.rag_service import augment_chat


@tool
async def search_knowledge(query: str) -> str:
    """搜索本地知识库，获取与查询相关的文档片段。

    当用户询问的问题可能在已上传的文档中有答案时，使用此工具检索相关内容。
    返回相关文档片段及其来源。
    """
    result = await augment_chat(
        system_prompt="",
        history=[],
        user_content=query,
    )

    if not result.chunks_used:
        return "知识库中未找到与查询相关的内容。"

    parts = []
    for i, c in enumerate(result.citations, 1):
        parts.append(f"[{i}] 来源: {c['document']} (相关度: {c['score']})\n{c['snippet']}")
    return "\n\n".join(parts)
