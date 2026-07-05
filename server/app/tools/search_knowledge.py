"""Search knowledge base tool — wraps RAG retrieval as a LangChain @tool."""

import re

from langchain_core.tools import tool

from app.services.rag_service import augment_chat

# Chunks with score below this threshold are considered "high confidence"
# ChromaDB cosine distance: 0 = identical, 2 = opposite. < 0.8 = good match.
HIGH_CONFIDENCE_THRESHOLD = 0.6


def _clean_snippet(text: str) -> str:
    """
    洗和规范化从知识库中检索到的原始文档片段，去除噪声和格式污染
    ，确保传递给LLM的文本更干净、易读。
    """
    # Remove horizontal rule dividers (===...===)
    text = re.sub(r'={10,}', '', text)
    # Remove orphaned standalone numbers at line start (chunk boundary artifacts)
    text = re.sub(r'^\s*\d{1,2}\s*$', '', text, flags=re.MULTILINE)
    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    # If after cleaning the snippet is too short to be useful, drop it
    if len(text) < 20:
        return ""
    return text


@tool
async def search_knowledge(query: str) -> str:
    """搜索本地知识库，获取与查询相关的文档片段。
    如果知识库有相关内容，基于检索结果作为参考进行回答。
    如果知识库没有相关内容或相关度过低，工具会明确告知，此时应基于通用知识回答。
    """
    result = await augment_chat(
        system_prompt="",
        history=[],
        user_content=query,
    )

    if not result.chunks_used:
        return (
            "知识库中未找到与查询相关的文档。\n"
            "你必须基于自己的通用健康知识直接回答用户问题,请勿再次调用此工具。"
        )

    # Separate high vs low confidence results, clean snippets
    high_conf = [
        c for c in result.citations
        if c["score"] >= HIGH_CONFIDENCE_THRESHOLD
    ]
    low_conf = [
        c for c in result.citations
        if 0.4 <= c["score"] < HIGH_CONFIDENCE_THRESHOLD
    ]

    if not high_conf and low_conf:
        cleaned = [(c, _clean_snippet(c["snippet"])) for c in low_conf]
        cleaned = [(c, s) for c, s in cleaned if s]
        if not cleaned:
            return (
                "知识库中未找到与查询相关的有效文档。\n"
                "你必须基于自己的通用健康知识直接回答用户问题,请勿再次调用此工具。"
            )
        parts = [
            "以下知识库内容与问题关联较弱，仅供参考：",
            *[f"文档「{c['document']}」:\n{s}" for c, s in cleaned],
            "如果以上内容无法充分回答问题，你必须基于自己的通用健康知识直接回答。\n"
            "请勿再次调用此工具。",
        ]
        return "\n\n".join(parts)

    cleaned = [(c, _clean_snippet(c["snippet"])) for c in high_conf]
    cleaned = [(c, s) for c, s in cleaned if s]
    if not cleaned:
        return (
            "知识库中未找到与查询相关的有效文档。\n"
            "你必须基于自己的通用健康知识直接回答用户问题,请勿再次调用此工具。"
        )
    parts = [
        "以下是从知识库检索到的相关内容：",
        *[f"文档「{c['document']}」:\n{s}" for c, s in cleaned],
    ]
    return "\n\n".join(parts)
