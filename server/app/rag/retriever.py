"""ChromaDB vector search with score filtering."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with metadata."""

    chunk_id: str
    document: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


async def retrieve_context(
    query: str,
    collection,
    embedder,
    top_k: int = 5,
    score_threshold: float = 1.5,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks from ChromaDB for a query.

    Args:
        query: User query text.
        collection: ChromaDB collection.
        embedder: Embedding function for the query.
        top_k: Number of chunks to retrieve.
        score_threshold: Minimum similarity score (lower = more similar in ChromaDB distance).

    Returns:
        List of RetrievedChunk sorted by relevance (best first).
    """
    # Generate query embedding
    query_embedding = embedder.embed_query(query)

    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[RetrievedChunk] = []

    if not results["ids"] or not results["ids"][0]:
        return chunks

    for i, doc_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i] if results["distances"] else 0.0
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        document_text = results["documents"][0][i] if results["documents"] else ""

        # Filter by score threshold (ChromaDB distance: lower = more similar)
        if distance > score_threshold:
            continue

        chunks.append(RetrievedChunk(
            chunk_id=doc_id,
            document=metadata.get("source", "unknown"),
            content=document_text,
            score=distance,
            metadata=metadata,
        ))

    # Sort by score (ascending — lower distance = better)
    chunks.sort(key=lambda c: c.score)

    return chunks
