"""Auto-generate evaluation test sets from knowledge base documents.

Uses RAGAS TestsetGenerator to create synthetic (question, ground_truth, reference_contexts)
from the actual ChromaDB knowledge base. Generated test cases are cached to JSON for reuse.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from langchain_core.documents import Document as LCDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Apply vertexai stub before importing RAGAS (same fix as metrics/__init__.py)
# ---------------------------------------------------------------------------
try:
    from langchain_community.chat_models.vertexai import ChatVertexAI  # noqa: F401
except ImportError:
    sys.modules.setdefault("langchain_community.chat_models.vertexai", type(sys)("vstub"))
    sys.modules["langchain_community.chat_models.vertexai"].ChatVertexAI = type(
        "ChatVertexAI", (), {}
    )


class TestsetGenerationError(Exception):
    """Raised when testset generation fails."""


async def _load_chunks_from_chromadb(
    max_chunks: int = 300,
) -> list[LCDocument]:
    """Load document chunks from ChromaDB as LangChain Documents.

    Args:
        max_chunks: Maximum number of chunks to load (to keep generation manageable).

    Returns:
        List of LangChain Document objects ready for RAGAS TestsetGenerator.
    """
    from app.services.rag_service import get_collection

    collection = get_collection()
    count = collection.count()
    if count == 0:
        raise TestsetGenerationError(
            "Knowledge base is empty. Upload documents before generating test sets."
        )

    logger.info("Loading up to %d chunks from ChromaDB (total: %d)...", max_chunks, count)

    # ChromaDB .get() fetches all documents. For large collections,
    # sample by taking the first max_chunks entries.
    # (A more sophisticated sampling could be added later.)
    data = collection.get(
        include=["documents", "metadatas"],
        limit=max_chunks,
    )

    chunks: list[LCDocument] = []
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])
    for j in range(len(ids)):
        chunk_id = ids[j]
        doc_text = docs[j] if j < len(docs) else ""
        meta = metas[j] if j < len(metas) else {}
        if not doc_text or not doc_text.strip():
            continue
        metadata = dict(meta or {})
        metadata["chunk_id"] = chunk_id
        chunks.append(
            LCDocument(
                page_content=doc_text,
                metadata=metadata,
            )
        )

    logger.info("Loaded %d valid chunks from ChromaDB", len(chunks))
    if len(chunks) < 5:
        raise TestsetGenerationError(
            f"Only {len(chunks)} valid chunks found. "
            "Need at least 5 chunks to generate meaningful test cases."
        )

    return chunks


async def generate_testset(
    testset_size: int = 30,
    generator_model: str = "deepseek-chat",
    max_chunks: int = 300,
) -> list[dict]:
    """Generate synthetic test cases from the knowledge base.

    Uses RAGAS TestsetGenerator to build a knowledge graph from ChromaDB chunks
    and synthesize (question, ground_truth, reference_contexts) triples.

    Args:
        testset_size: Number of test cases to generate.
        generator_model: LLM model for question/answer synthesis (DeepSeek).
        max_chunks: Max ChromaDB chunks to feed into the knowledge graph.

    Returns:
        List of test case dicts with keys:
          - question (str)
          - ground_truth (str | None)
          - reference_contexts (list[str])
          - category (str): evolution_type from RAGAS
    """
    from openai import OpenAI

    from app.config import settings

    # 1. Load chunks from ChromaDB
    chunks = await _load_chunks_from_chromadb(max_chunks)

    # 2. Set up generator LLM via DeepSeek (OpenAI-compatible)
    deepseek_client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    from ragas.llms import llm_factory

    generator_llm = llm_factory(
        model=generator_model,
        provider="openai",
        client=deepseek_client,
    )

    # 3. Set up embedding model for knowledge graph construction
    from ragas.embeddings import OpenAIEmbeddings

    if settings.zhipuai_api_key:
        embedding_client = OpenAI(
            api_key=settings.zhipuai_api_key,
            base_url=settings.zhipuai_base_url,
        )
        embedding_model_name = settings.zhipuai_embedding_model
    elif settings.openai_api_key:
        embedding_client = OpenAI(api_key=settings.openai_api_key)
        embedding_model_name = settings.openai_embedding_model
    else:
        # Fallback: wrap the ONNX embedder via LangChain adapter
        from app.rag.embedder import get_embedder
        from langchain_core.embeddings import Embeddings as LCEmbeddings

        class _EmbedderAdapter(LCEmbeddings):
            def __init__(self, impl):
                self._impl = impl

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return self._impl.embed_documents(texts)

            def embed_query(self, text: str) -> list[float]:
                return self._impl.embed_query(text)

        from ragas.embeddings import LangchainEmbeddingsWrapper

        lc_embedder = _EmbedderAdapter(get_embedder())
        generator_embeddings = LangchainEmbeddingsWrapper(lc_embedder)
        embedding_client = None
        embedding_model_name = None

    if embedding_client is not None:
        generator_embeddings = OpenAIEmbeddings(
            client=embedding_client,
            model=embedding_model_name,
        )

    # 4. Initialize TestsetGenerator
    from ragas.testset.synthesizers.generate import TestsetGenerator

    gen = TestsetGenerator(
        llm=generator_llm,
        embedding_model=generator_embeddings,
    )

    # 5. Generate testset
    logger.info(
        "Generating %d test cases from %d chunks (this may take a few minutes)...",
        testset_size,
        len(chunks),
    )
    testset = gen.generate_with_chunks(
        chunks=chunks,
        testset_size=testset_size,
        with_debugging_logs=False,
        raise_exceptions=True,
    )

    # 6. Convert to our test case format
    # to_list() returns flat dicts with top-level keys: user_input, reference,
    # reference_contexts, query_style, persona_name, synthesizer_name, etc.
    test_cases: list[dict] = []
    for sample in testset.to_list():
        question = sample.get("user_input", "")
        if not question:
            continue

        ground_truth = sample.get("reference")
        ref_contexts = sample.get("reference_contexts") or []
        evolution_type = sample.get("query_style", "generated")

        test_cases.append({
            "question": question,
            "ground_truth": ground_truth,
            "reference_contexts": ref_contexts,
            "category": evolution_type or "generated",
            "difficulty": "auto",
        })

    logger.info("Generated %d test cases", len(test_cases))
    return test_cases


def save_testset(test_cases: list[dict], path: str | None = None) -> str:
    """Save generated test cases to a JSON cache file.

    Args:
        test_cases: List of test case dicts.
        path: Output file path. Uses config.testset_cache_path if None.

    Returns:
        The file path where test cases were saved.
    """
    from evaluation.config import config

    output = Path(path or config.testset_cache_path)
    os.makedirs(output.parent, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d test cases to %s", len(test_cases), output)
    return str(output)


def load_testset(path: str | None = None) -> list[dict]:
    """Load cached test cases from JSON.

    Args:
        path: JSON file path. Uses config.testset_cache_path if None.

    Returns:
        List of test case dicts, or empty list if cache doesn't exist.
    """
    from evaluation.config import config

    source = Path(path or config.testset_cache_path)
    if not source.exists():
        logger.warning("No cached testset found at %s", source)
        return []

    with open(source, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Loaded %d test cases from %s", len(data), source)
    return data
