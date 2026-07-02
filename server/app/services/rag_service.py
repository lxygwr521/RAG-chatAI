"""RAG service — orchestrates document ingestion, retrieval, and augmentation.

Query rewriting uses HyDE (Hypothetical Document Embeddings):
  user question → LLM generates hypothetical answer → embed & search → real chunks
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional
from dataclasses import dataclass

import chromadb
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.rag.loader import load_document
from app.rag.splitter import split_documents
from app.rag.embedder import get_embedder, ChromaEmbeddingFunction
from app.rag.retriever import retrieve_context, RetrievedChunk
from app.rag.prompt import build_rag_messages, build_citations

logger = logging.getLogger(__name__)

# Module-level ChromaDB client (initialized in main.py lifespan)
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None

# ---------------------------------------------------------------------------
# HyDE: Hypothetical Document Embeddings for query rewriting
# ---------------------------------------------------------------------------

HYDE_PROMPT = """你是一个个人健康档案撰写助手。根据用户的健康相关问题，写一段 100-200 字的假想健康文档片段，
模拟个人健康知识库中可能存在的答案内容。写出关键营养素数据、运动建议、体检指标参考值、
饮食方案、用药说明或医学指南摘要，风格接近正式的健康管理报告或医学文献。

只输出假想文档内容，不要加任何前缀、说明或标记。

用户问题：{question}
假想文档片段："""

# Lazy-initialized HyDE LLM (lightweight model for fast generation)
_hyde_llm: Optional[ChatOpenAI] = None


def _get_hyde_llm() -> ChatOpenAI:
    """Get or create the HyDE generation LLM (lazy init, singleton)."""
    global _hyde_llm
    if _hyde_llm is None:
        _hyde_llm = ChatOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model="deepseek-v4-flash",
            max_tokens=300,
            temperature=0.3,
        )
    return _hyde_llm


async def _generate_hypothetical_doc(question: str) -> str:
    """Generate a hypothetical document to improve retrieval accuracy.

    Uses the HyDE technique: an LLM writes a fake "answer document",
    whose embedding will be closer to actual knowledge-base documents
    than the original short query.

    Returns the original question on failure (graceful degradation).
    """
    try:
        llm = _get_hyde_llm()
        prompt = HYDE_PROMPT.format(question=question)
        response = await llm.ainvoke(prompt)
        hypothetical = response.content.strip() if hasattr(response, "content") else str(response).strip()

        if not hypothetical or len(hypothetical) < 10:
            logger.warning("HyDE returned empty/short response, falling back to original query")
            return question

        logger.info("HyDE generated hypothetical doc (%d chars): %s...", len(hypothetical), hypothetical[:80])
        return hypothetical

    except Exception as e:
        logger.warning("HyDE generation failed, falling back to original query: %s", e)
        return question


def init_chroma():
    """Initialize ChromaDB persistent client and collection.

    Uses no embedding_function — we pre-compute embeddings before add()
    to avoid ChromaDB's internal timeout when calling external APIs.
    """
    global _chroma_client, _collection
    _chroma_client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=chromadb.Settings(anonymized_telemetry=False),
    )
    try:
        _collection = _chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            embedding_function=None,  # Manually embed before add()
        )
    except KeyError:
        # ChromaDB version upgrade may break config format (_type field missing)
        logger.warning(
            "ChromaDB collection config is incompatible, recreating collection "
            "(existing vectors will be re-indexed on next upload)"
        )
        try:
            _chroma_client.delete_collection(name=settings.chroma_collection_name)
        except Exception:
            pass
        _collection = _chroma_client.create_collection(
            name=settings.chroma_collection_name,
            embedding_function=None,
        )
    logger.info(f"ChromaDB initialized: {settings.chroma_persist_dir}")


def get_collection() -> chromadb.Collection:
    """Get the ChromaDB collection (auto-initializes if not already done)."""
    global _collection, _chroma_client
    if _collection is None:
        init_chroma()
    return _collection


def get_chroma_client() -> chromadb.PersistentClient:
    """Get the shared ChromaDB persistent client (auto-initializes if needed)."""
    global _chroma_client
    if _chroma_client is None:
        init_chroma()
    return _chroma_client


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

async def ingest_document(
    file_path: str,
    filename: str,
    file_type: str,
    file_size: int,
    db: AsyncSession,
) -> KnowledgeDocument:
    """Full ingestion pipeline: load → split → embed → store.

    Returns the created KnowledgeDocument with status='ready'.
    """
    doc_id = str(uuid.uuid4())
    collection = get_collection()

    # Create DB record (status=processing)
    doc = KnowledgeDocument(
        id=doc_id,
        filename=filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        status="processing",
    )
    db.add(doc)
    await db.flush()

    try:
        # 1. Load
        documents = await load_document(file_path)
        if not documents:
            raise ValueError(f"No content extracted from {filename}")

        # 2. Split
        chunks = split_documents(documents)
        if not chunks:
            raise ValueError(f"No chunks produced from {filename}")

        # 3. Pre-compute embeddings 
        embedder = get_embedder()
        chunk_texts = [chunk.page_content for chunk in chunks]
        logger.info("Embedding %d chunks for %s...", len(chunks), filename)
        embeddings = embedder.embed_documents(chunk_texts)

        chunk_ids = []
        chroma_ids = []
        chroma_metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chroma_id = f"{doc_id}_{i}"
            chunk_ids.append(chunk_id)
            chroma_ids.append(chroma_id)
            chroma_metadatas.append({
                **chunk.metadata,
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "source": filename,
                "chunk_index": i,
            })

        # Batch add with pre-computed embeddings (skips collection embedding function)
        collection.add(
            ids=chroma_ids,
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=chroma_metadatas,
        )

        # 4. Store chunk records in SQLite
        for i, chunk in enumerate(chunks):
            db.add(KnowledgeChunk(
                id=chunk_ids[i],
                document_id=doc_id,
                chunk_index=i,
                content=chunk.page_content,
                metadata_json=json.dumps(chunk.metadata, ensure_ascii=False),
                chroma_id=chroma_ids[i],
            ))

        # Mark as ready
        doc.chunk_count = len(chunks)
        doc.status = "ready"

    except Exception as e:
        logger.error(f"Failed to ingest {filename}: {e}")
        doc.status = "error"
        # Clean up ChromaDB if we added anything
        if chroma_ids:
            try:
                collection.delete(ids=chroma_ids)
            except Exception:
                pass

    return doc


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

async def delete_document(doc_id: str, doc: KnowledgeDocument) -> None:
    """Delete a document: remove file, SQLite records, and ChromaDB vectors."""
    collection = get_collection()

    # Delete from ChromaDB (skip if no chunks — e.g., document stuck in processing/error)
    if doc.chunk_count > 0:
        chroma_ids = [f"{doc_id}_{i}" for i in range(doc.chunk_count)]
        try:
            collection.delete(ids=chroma_ids)
        except Exception as e:
            logger.warning(f"ChromaDB delete warning: {e}")

    # Delete source file
    try:
        os.remove(doc.file_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Retrieval + Augmentation for chat
# ---------------------------------------------------------------------------

@dataclass
class RAGResult:
    """Result of RAG retrieval + augmentation."""

    messages: list[dict]
    citations: list[dict]
    chunks_used: int


async def augment_chat(
    system_prompt: str,
    history: list[dict],
    user_content: str,
    top_k: int = 5,
) -> RAGResult:
    """Retrieve relevant chunks and augment the chat messages.

    Args:
        system_prompt: Original system prompt.
        history: Conversation history.
        user_content: Current user message.
        top_k: Number of chunks to retrieve.

    Returns:
        RAGResult with augmented messages and citation data.
    """
    collection = get_collection()
    embedder = get_embedder()
	# 1. 空知识库处理
    if collection.count() == 0:
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return RAGResult(messages=messages, citations=[], chunks_used=0)

    # 1.5 HyDE query rewriting — generate hypothetical doc for better retrieval
    retrieval_query = await _generate_hypothetical_doc(user_content)

    # 2. 检索 (using HyDE-generated query for embedding)
    chunks = await retrieve_context(
        query=retrieval_query,
        original_query=user_content,
        collection=collection,
        embedder=embedder,
        top_k=top_k,
        score_threshold=settings.rag_score_threshold,
        rerank_top_k=settings.rag_rerank_top_k,
    )
# 2.检索与空结果处理
    if not chunks:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return RAGResult(messages=messages, citations=[], chunks_used=0)
# 3.构建增强后的消息
    # Build augmented messages
    messages = build_rag_messages(
        system_prompt=system_prompt,
        history=history,
        user_content=user_content,
        retrieved_chunks=chunks,
    )
    citations = build_citations(chunks)

    return RAGResult(
        messages=messages,
        citations=citations,
        chunks_used=len(chunks),
    )
