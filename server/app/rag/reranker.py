"""MiniLM cross-encoder reranking for retrieved RAG chunks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class RerankableChunk(Protocol):
    """Minimal candidate shape required by the MiniLM reranker."""

    content: str


@dataclass
class RerankScore:
    """A candidate index paired with its MiniLM relevance score."""

    index: int
    score: float


class MiniLMReranker:
    """Lazy wrapper around sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def rerank(
        self,
        query: str,
        candidates: list[RerankableChunk],
        *,
        batch_size: int,
    ) -> list[RerankScore]:
        """Score query/chunk pairs and return scores sorted descending."""
        if not query or not candidates:
            return []

        model = self._get_model()
        pairs = [(query, candidate.content) for candidate in candidates]
        raw_scores = model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        scores = [
            RerankScore(index=index, score=float(score))
            for index, score in enumerate(raw_scores)
        ]
        scores.sort(key=lambda item: item.score, reverse=True)
        return scores

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for MiniLM reranking"
                ) from exc

            logger.info("Loading MiniLM reranker model: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model


_reranker: MiniLMReranker | None = None


def get_minilm_reranker() -> MiniLMReranker:
    """Get the process-wide MiniLM reranker instance."""
    global _reranker
    if _reranker is None or _reranker.model_name != settings.rag_reranker_model:
        _reranker = MiniLMReranker(settings.rag_reranker_model)
    return _reranker
