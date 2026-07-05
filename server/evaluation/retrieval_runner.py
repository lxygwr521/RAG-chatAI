"""Retrieval-only evaluation for hybrid RAG search quality."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.rag.retriever import RetrievedChunk, retrieve_context
from app.services.rag_service import _generate_hypothetical_doc, get_collection
from app.rag.embedder import get_embedder
from evaluation.config import config
from evaluation.dataset.retrieval_cases import load_retrieval_cases
RETRIEVAL_MODES = ["vector_only", "hybrid_rrf", "hybrid_rerank"]

@dataclass
class RetrievalCaseScore:
    case_id: str
    question: str
    category: str
    mode: str
    hit_rank: int | None
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    mrr: float
    elapsed_ms: int
    results: list[dict] = field(default_factory=list)


@dataclass
class RetrievalEvalResult:
    id: str
    timestamp: str
    top_k: int
    use_hyde: bool
    case_count: int
    modes: list[str]
    summary: dict[str, dict]
    scores: list[dict]


async def run_retrieval_evaluation(
    *,
    modes: list[str] | None = None,
    top_k: int = 5,
    use_hyde: bool = True,
    persist: bool = True,
) -> RetrievalEvalResult:
    """Evaluate retrieval hit@k and MRR for each retrieval mode."""
    selected_modes = modes or RETRIEVAL_MODES
    _validate_modes(selected_modes)

    cases = load_retrieval_cases()
    collection = get_collection()
    embedder = get_embedder()
    case_scores: list[RetrievalCaseScore] = []

    for case in cases:
        question = case["question"]
        retrieval_query = await _generate_hypothetical_doc(question) if use_hyde else question

        for mode in selected_modes:
            started = time.perf_counter()
            chunks = await retrieve_context(
                query=retrieval_query,
                original_query=question,
                collection=collection,
                embedder=embedder,
                top_k=top_k,
                mode=mode,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            case_scores.append(_score_case(case, mode, chunks, elapsed_ms))

    result = RetrievalEvalResult(
        id=f"retrieval_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        top_k=top_k,
        use_hyde=use_hyde,
        case_count=len(cases),
        modes=selected_modes,
        summary=_summarize(case_scores),
        scores=[score.__dict__ for score in case_scores],
    )

    if persist:
        _save_result(result)

    return result


def _score_case(
    case: dict,
    mode: str,
    chunks: list[RetrievedChunk],
    elapsed_ms: int,
) -> RetrievalCaseScore:
    hit_rank = _first_hit_rank(case, chunks)
    return RetrievalCaseScore(
        case_id=case["id"],
        question=case["question"],
        category=case.get("category", "unknown"),
        mode=mode,
        hit_rank=hit_rank,
        hit_at_1=hit_rank is not None and hit_rank <= 1,
        hit_at_3=hit_rank is not None and hit_rank <= 3,
        hit_at_5=hit_rank is not None and hit_rank <= 5,
        mrr=round(1 / hit_rank, 4) if hit_rank else 0.0,
        elapsed_ms=elapsed_ms,
        results=[_chunk_out(chunk) for chunk in chunks],
    )


def _first_hit_rank(case: dict, chunks: list[RetrievedChunk]) -> int | None:
    for rank, chunk in enumerate(chunks, 1):
        if _matches_expected(case, chunk):
            return rank
    return None


def _matches_expected(case: dict, chunk: RetrievedChunk) -> bool:
    haystack = f"{chunk.document}\n{chunk.content}".lower()
    expected_documents = [str(value).lower() for value in case.get("expected_documents", [])]
    expected_terms = [str(value).lower() for value in case.get("expected_terms", [])]

    if expected_documents and any(value in chunk.document.lower() for value in expected_documents):
        return True
    if expected_terms and any(value in haystack for value in expected_terms):
        return True
    return False


def _chunk_out(chunk: RetrievedChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "document": chunk.document,
        "score": chunk.score,
        "snippet": chunk.content[:200],
        "retrieval": chunk.metadata.get("retrieval", {}),
    }


def _summarize(scores: list[RetrievalCaseScore]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for mode in sorted({score.mode for score in scores}):
        mode_scores = [score for score in scores if score.mode == mode]
        total = len(mode_scores) or 1
        summary[mode] = {
            "hit_at_1": round(sum(score.hit_at_1 for score in mode_scores) / total, 4),
            "hit_at_3": round(sum(score.hit_at_3 for score in mode_scores) / total, 4),
            "hit_at_5": round(sum(score.hit_at_5 for score in mode_scores) / total, 4),
            "mrr": round(sum(score.mrr for score in mode_scores) / total, 4),
            "avg_elapsed_ms": round(sum(score.elapsed_ms for score in mode_scores) / total, 2),
        }
    return summary


def _save_result(result: RetrievalEvalResult) -> None:
    report_dir = Path(config.report_dir)
    os.makedirs(report_dir, exist_ok=True)

    data = result.__dict__
    json_path = report_dir / f"{result.id}.json"
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    md_path = report_dir / f"{result.id}.md"
    with open(md_path, "w", encoding="utf-8") as file:
        file.write(_markdown_report(result))


def _markdown_report(result: RetrievalEvalResult) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"**ID**: `{result.id}`  ",
        f"**Timestamp**: {result.timestamp}  ",
        f"**Cases**: {result.case_count}  ",
        f"**Top K**: {result.top_k}  ",
        f"**HyDE**: {result.use_hyde}",
        "",
        "## Summary",
        "",
        "| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Avg Latency (ms) |",
        "|------|-------|-------|-------|-----|------------------|",
    ]
    for mode, stats in result.summary.items():
        lines.append(
            f"| {mode} | {stats['hit_at_1']:.4f} | {stats['hit_at_3']:.4f} | "
            f"{stats['hit_at_5']:.4f} | {stats['mrr']:.4f} | {stats['avg_elapsed_ms']:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _validate_modes(modes: list[str]) -> None:
    unknown = [mode for mode in modes if mode not in RETRIEVAL_MODES]
    if unknown:
        raise ValueError(f"Unknown retrieval modes: {', '.join(unknown)}")
