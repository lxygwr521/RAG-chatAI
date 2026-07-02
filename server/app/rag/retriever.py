"""Hybrid ChromaDB vector + lexical retrieval with RRF fusion."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.rag.lexical import LexicalDocument, rank_lexical
from app.rag.reranker import get_minilm_reranker

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with metadata."""

    chunk_id: str
    document: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class _Candidate:
    chunk_id: str
    document: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_distance: float | None = None
    vector_rank: int | None = None
    lexical_score: float | None = None
    lexical_rank: int | None = None
    fusion_score: float = 0.0
    rerank_score: float | None = None


async def retrieve_context(
    query: str,
    collection,
    embedder,
    top_k: int = 5,
    score_threshold: float | None = None,
    *,
    original_query: str | None = None,
    vector_top_k: int | None = None,
    lexical_top_k: int | None = None,
    rerank_top_k: int | None = None,
    mode: str = "hybrid_rerank",
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks with hybrid vector and lexical recall.

    Args:
        query: Vector retrieval query. In the current RAG pipeline this is the
            HyDE-generated hypothetical document.
        collection: ChromaDB collection.
        embedder: Embedding function for the vector query.
        top_k: Number of final chunks to return.
        score_threshold: ChromaDB vector distance threshold. Lower is better.
        original_query: Raw user query for lexical recall. Falls back to query.
        vector_top_k: Number of vector candidates to fetch before fusion.
        lexical_top_k: Number of lexical candidates to fetch before fusion.
        rerank_top_k: Number of fused candidates to score with MiniLM.
        mode: Retrieval mode for evaluation: vector_only, hybrid_rrf, or hybrid_rerank.

    Returns:
        List of RetrievedChunk sorted by fused relevance.
    """
    if top_k <= 0:
        return []

    threshold = settings.rag_score_threshold if score_threshold is None else score_threshold
    vector_limit = max(top_k, vector_top_k or settings.rag_vector_top_k)
    lexical_limit = max(top_k, lexical_top_k or settings.rag_lexical_top_k)
    rerank_limit = max(top_k, rerank_top_k or settings.rag_rerank_top_k)
    lexical_query = original_query or query

    vector_candidates = _vector_search(
        query=query,
        collection=collection,
        embedder=embedder,
        top_k=vector_limit,
        score_threshold=threshold,
    )
    if mode == "vector_only":
        return [_to_retrieved_chunk(candidate) for candidate in vector_candidates[:top_k]]

    lexical_candidates = _lexical_search(
        query=lexical_query,
        collection=collection,
        top_k=lexical_limit,
    )

    fused = _fuse_candidates(
        vector_candidates=vector_candidates,
        lexical_candidates=lexical_candidates,
    )
    if mode == "hybrid_rrf":
        return [_to_retrieved_chunk(candidate) for candidate in fused[:top_k]]
    if mode != "hybrid_rerank":
        raise ValueError(f"Unsupported retrieval mode: {mode}")

    reranked = _rerank_candidates(
        query=lexical_query,
        candidates=fused[:rerank_limit],
    )
    return [_to_retrieved_chunk(candidate) for candidate in reranked[:top_k]]


def _vector_search(
    *,
    query: str,
    collection,
    embedder,
    top_k: int,
    score_threshold: float,
) -> list[_Candidate]:
    try:
        collection_count = collection.count()
    except Exception:
        logger.exception("Failed to count ChromaDB collection")
        return []

    if collection_count <= 0 or top_k <= 0:
        return []

    query_embedding = embedder.embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection_count),
        include=["documents", "metadatas", "distances"],
    )

    if not results.get("ids") or not results["ids"][0]:
        return []

    candidates: list[_Candidate] = []
    for index, chunk_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][index] if results.get("distances") else 0.0
        if distance > score_threshold:
            continue

        metadata = results["metadatas"][0][index] if results.get("metadatas") else {}
        content = results["documents"][0][index] if results.get("documents") else ""
        metadata = dict(metadata or {})

        candidates.append(_Candidate(
            chunk_id=chunk_id,
            document=metadata.get("source", "unknown"),
            content=content or "",
            metadata=metadata,
            vector_distance=distance,
        ))

    candidates.sort(key=lambda candidate: candidate.vector_distance or 0.0)
    for rank, candidate in enumerate(candidates, 1):
        candidate.vector_rank = rank

    return candidates


def _lexical_search(
    *,
    query: str,
    collection,
    top_k: int,
) -> list[_Candidate]:
    documents = _load_lexical_documents(collection)
    lexical_results = rank_lexical(query=query, documents=documents, top_k=top_k)

    candidates: list[_Candidate] = []
    for rank, result in enumerate(lexical_results, 1):
        metadata = dict(result.metadata or {})
        candidates.append(_Candidate(
            chunk_id=result.chunk_id,
            document=metadata.get("source", "unknown"),
            content=result.content or "",
            metadata=metadata,
            lexical_score=result.score,
            lexical_rank=rank,
        ))
    return candidates


def _load_lexical_documents(collection) -> list[LexicalDocument]:
    try:
        results = collection.get(include=["documents", "metadatas"])
    except Exception:
        logger.exception("Failed to load ChromaDB documents for lexical retrieval")
        return []

    ids = results.get("ids") or []
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []

    loaded: list[LexicalDocument] = []
    for index, chunk_id in enumerate(ids):
        content = documents[index] if index < len(documents) else ""
        metadata = metadatas[index] if index < len(metadatas) else {}
        if content:
            loaded.append(LexicalDocument(
                chunk_id=chunk_id,
                content=content,
                metadata=dict(metadata or {}),
            ))
    return loaded


def _fuse_candidates(
    *,
    vector_candidates: list[_Candidate],
    lexical_candidates: list[_Candidate],
) -> list[_Candidate]:
    merged: dict[str, _Candidate] = {}

    for candidate in vector_candidates:
        merged[candidate.chunk_id] = candidate

    for lexical in lexical_candidates:
        existing = merged.get(lexical.chunk_id)
        if existing is None:
            merged[lexical.chunk_id] = lexical
            continue

        existing.lexical_score = lexical.lexical_score
        existing.lexical_rank = lexical.lexical_rank
        existing.metadata = _merge_metadata(existing.metadata, lexical.metadata)

    for candidate in merged.values():
        candidate.fusion_score = _rrf_score(candidate)

    return sorted(
        merged.values(),
        key=lambda item: (
            item.fusion_score,
            -(item.vector_distance if item.vector_distance is not None else 10.0),
            item.lexical_score or 0.0,
        ),
        reverse=True,
    )


def _rrf_score(candidate: _Candidate) -> float:
    score = 0.0
    if candidate.vector_rank is not None:
        score += settings.rag_vector_weight / (settings.rag_rrf_k + candidate.vector_rank)
    if candidate.lexical_rank is not None:
        score += settings.rag_lexical_weight / (settings.rag_rrf_k + candidate.lexical_rank)
    return score


def _rerank_candidates(query: str, candidates: list[_Candidate]) -> list[_Candidate]:
    if not candidates:
        return []

    try:
        scores = get_minilm_reranker().rerank(
            query=query,
            candidates=candidates,
            batch_size=settings.rag_reranker_batch_size,
        )
    except Exception as exc:
        logger.warning("MiniLM rerank failed; falling back to RRF order: %s", exc)
        return candidates

    if not scores:
        return candidates

    reranked: list[_Candidate] = []
    for score in scores:
        candidate = candidates[score.index]
        candidate.rerank_score = score.score
        reranked.append(candidate)

    return reranked


def _to_retrieved_chunk(candidate: _Candidate) -> RetrievedChunk:
    metadata = dict(candidate.metadata or {})
    retrieval = dict(metadata.get("retrieval") or {})
    retrieval.update({
        "sources": _candidate_sources(candidate),
        "vector_distance": candidate.vector_distance,
        "vector_rank": candidate.vector_rank,
        "lexical_score": candidate.lexical_score,
        "lexical_rank": candidate.lexical_rank,
        "fusion_score": candidate.fusion_score,
        "rerank_score": candidate.rerank_score,
    })
    metadata["retrieval"] = retrieval

    return RetrievedChunk(
        chunk_id=candidate.chunk_id,
        document=candidate.document,
        content=candidate.content,
        score=_distance_like_score(candidate),
        metadata=metadata,
    )


def _distance_like_score(candidate: _Candidate) -> float:
    if candidate.vector_distance is not None:
        return candidate.vector_distance
    if candidate.lexical_rank is not None:
        return min(settings.rag_score_threshold, 0.55 + 0.1 * (candidate.lexical_rank - 1))
    return settings.rag_score_threshold


def _candidate_sources(candidate: _Candidate) -> list[str]:
    sources: list[str] = []
    if candidate.vector_rank is not None:
        sources.append("vector")
    if candidate.lexical_rank is not None:
        sources.append("lexical")
    return sources


def _merge_metadata(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(right or {})
    merged.update(left or {})
    return merged
