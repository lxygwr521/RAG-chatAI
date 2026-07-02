"""BM25-style lexical retrieval over ChromaDB documents."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.rag.tokenizer import tokenize


@dataclass
class LexicalDocument:
    """A document chunk loaded from the vector store for lexical matching."""

    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LexicalResult:
    """A BM25-ranked chunk candidate."""

    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def rank_lexical(
    query: str,
    documents: list[LexicalDocument],
    top_k: int,
) -> list[LexicalResult]:
    """Rank documents with a compact BM25 implementation."""
    if top_k <= 0 or not query or not documents:
        return []

    query_terms = tokenize(query)
    if not query_terms:
        return []

    tokenized_docs: list[list[str]] = []
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        source = str(doc.metadata.get("source") or "")
        tokens = tokenize(f"{source}\n{doc.content}")
        tokenized_docs.append(tokens)
        doc_freq.update(set(tokens))

    avg_doc_len = sum(len(tokens) for tokens in tokenized_docs) / max(len(tokenized_docs), 1)
    if avg_doc_len <= 0:
        return []

    query_counts = Counter(query_terms)
    total_docs = len(documents)
    scored: list[LexicalResult] = []

    for doc, doc_tokens in zip(documents, tokenized_docs):
        if not doc_tokens:
            continue

        frequencies = Counter(doc_tokens)
        score = 0.0
        for term, query_weight in query_counts.items():
            term_frequency = frequencies.get(term, 0)
            if term_frequency == 0:
                continue

            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += query_weight * idf * _bm25_term_score(term_frequency, len(doc_tokens), avg_doc_len)

        if score > 0:
            scored.append(LexicalResult(
                chunk_id=doc.chunk_id,
                content=doc.content,
                score=score,
                metadata=dict(doc.metadata or {}),
            ))

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


def _bm25_term_score(
    term_frequency: int,
    doc_len: int,
    avg_doc_len: float,
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    denominator = term_frequency + k1 * (1 - b + b * doc_len / avg_doc_len)
    return (term_frequency * (k1 + 1)) / denominator
