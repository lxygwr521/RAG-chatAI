"""Evaluation framework for retrieval and Agent answer quality.

Provides:
  - Retrieval-only evaluation (hit@k, MRR, latency)
  - Agent end-to-end LLM-as-judge evaluation
  - Hand-annotated test cases with expected_terms
  - Multi-mode comparison (vector_only, hybrid_rrf, hybrid_rerank)
  - FastAPI evaluation endpoints
"""
