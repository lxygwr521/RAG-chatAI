"""Embedding provider — 智谱 ZhipuAI by default, OpenAI fallback, ONNX last resort.

Priority:
  1. ZhipuAI (embedding-2) — 配置了 ZHIPUAI_API_KEY 时启用
  2. OpenAI (text-embedding-3-small) — 配置了 OPENAI_API_KEY 时启用
  3. ONNX (all-MiniLM-L6-v2) — 本地兜底，首次需下载 ~80MB
"""

import logging
from typing import Protocol

from chromadb import Documents, EmbeddingFunction, Embeddings

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedder protocol
# ---------------------------------------------------------------------------

class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


# ---------------------------------------------------------------------------
# ZhipuAI embedder (OpenAI-compatible API)
# ---------------------------------------------------------------------------

class ZhipuEmbedder:
    """ZhipuAI embedding-2 via OpenAI-compatible API."""

    def __init__(self):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.zhipuai_api_key,
            base_url=settings.zhipuai_base_url,
        )
        self._model = settings.zhipuai_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ---------------------------------------------------------------------------
# OpenAI embedder (fallback)
# ---------------------------------------------------------------------------

class OpenAIEmbedder:
    """OpenAI text-embedding-3-small."""

    def __init__(self):
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ---------------------------------------------------------------------------
# ONNX local embedder (last resort)
# ---------------------------------------------------------------------------

class ONNXEmbedder:
    """ChromaDB built-in ONNXMiniLM_L6_V2, runs locally."""

    def __init__(self):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        self._ef = ONNXMiniLM_L6_V2()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._ef(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._ef([text])[0]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_embedder_instance: Embedder | None = None


def _is_valid_key(key: str) -> bool:
    return bool(key) and key not in ("sk-placeholder", "", "sk-your-key-here")


def get_embedder() -> Embedder:
    """Get the best available embedding provider.

    智谱 > OpenAI > ONNX (local)
    """
    global _embedder_instance

    if _embedder_instance is not None:
        return _embedder_instance

    # 1. ZhipuAI
    if _is_valid_key(settings.zhipuai_api_key):
        try:
            _embedder_instance = ZhipuEmbedder()
            logger.info("Using ZhipuAI embeddings (%s)", settings.zhipuai_embedding_model)
            return _embedder_instance
        except Exception as e:
            logger.warning("ZhipuAI embedder failed (%s), trying next", e)

    # 2. OpenAI
    if _is_valid_key(settings.openai_api_key):
        try:
            _embedder_instance = OpenAIEmbedder()
            logger.info("Using OpenAI embeddings (%s)", settings.openai_embedding_model)
            return _embedder_instance
        except Exception as e:
            logger.warning("OpenAI embedder failed (%s), falling back to ONNX", e)

    # 3. ONNX local
    _embedder_instance = ONNXEmbedder()
    logger.info("Using ONNX embeddings (all-MiniLM-L6-v2, local)")
    return _embedder_instance


# ---------------------------------------------------------------------------
# ChromaDB embedding function adapter (not used — we pre-compute embeddings)
# ---------------------------------------------------------------------------

class ChromaEmbeddingFunction(EmbeddingFunction):
    """Adapter: our Embedder → ChromaDB EmbeddingFunction."""

    def __init__(self, embedder: Embedder | None = None):
        self._embedder = embedder or get_embedder()

    def __call__(self, input: Documents) -> Embeddings:
        return self._embedder.embed_documents(list(input))
