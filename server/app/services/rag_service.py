"""RAG service — orchestrates document ingestion, retrieval, and augmentation."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional
from dataclasses import dataclass

import chromadb
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
    _collection = _chroma_client.get_or_create_collection(
        name=settings.chroma_collection_name,
        embedding_function=None,  # Manually embed before add()
    )
    logger.info(f"ChromaDB initialized: {settings.chroma_persist_dir}")


def get_collection() -> chromadb.Collection:
    """Get the ChromaDB collection (auto-initializes if not already done)."""
    global _collection, _chroma_client
    if _collection is None:
        init_chroma()
    return _collection


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

    # Delete from ChromaDB
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

    # Check if knowledge base has any documents
    if collection.count() == 0:
        # No documents → no RAG
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return RAGResult(messages=messages, citations=[], chunks_used=0)

    # Retrieve
    chunks = await retrieve_context(
        query=user_content,
        collection=collection,
        embedder=embedder,
        top_k=top_k,
    )

    if not chunks:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return RAGResult(messages=messages, citations=[], chunks_used=0)

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
