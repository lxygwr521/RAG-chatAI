"""Retrieval evaluation framework for the RAG knowledge base.

Provides:
  - Retrieval-only evaluation (hit@k, MRR, latency)
  - Hand-annotated test cases with expected_terms
  - Multi-mode comparison (vector_only, hybrid_rrf, hybrid_rerank)
  - FastAPI evaluation endpoints
"""
