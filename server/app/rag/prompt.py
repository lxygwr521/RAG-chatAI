"""RAG prompt utilities."""


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
