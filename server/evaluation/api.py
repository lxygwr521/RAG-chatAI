"""Retrieval evaluation API endpoints -- /api/eval/*"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from evaluation.config import config
from evaluation.dataset.retrieval_cases import load_retrieval_cases
from evaluation.retrieval_runner import RETRIEVAL_MODES, run_retrieval_evaluation

eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])


# ── Request / Response models ────────────────────────────────────

class RetrievalEvalRequest(BaseModel):
    """Request to run retrieval-only evaluation."""
    modes: list[str] | None = Field(None, description="Modes to compare. None = all.")
    top_k: int = Field(5, ge=1, le=20)
    use_hyde: bool = True
    persist: bool = True


# ── Retrieval evaluation endpoints ──────────────────────────────

@eval_router.get("/retrieval/test-cases")
async def get_retrieval_test_cases():
    """List retrieval-only test cases."""
    cases = load_retrieval_cases()
    return {
        "count": len(cases),
        "modes": RETRIEVAL_MODES,
        "cases": cases,
    }


@eval_router.post("/retrieval/run")
async def run_retrieval_eval(request: RetrievalEvalRequest | None = None):
    """Run retrieval-only hit@k/MRR evaluation.

    Compares vector_only, hybrid_rrf, and hybrid_rerank modes
    against hand-annotated test cases with expected_terms.
    """
    body = request or RetrievalEvalRequest()
    try:
        result = await run_retrieval_evaluation(
            modes=body.modes,
            top_k=body.top_k,
            use_hyde=body.use_hyde,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "completed",
        "id": result.id,
        "summary": result.summary,
        "case_count": result.case_count,
        "modes": result.modes,
        "top_k": result.top_k,
        "use_hyde": result.use_hyde,
    }


# ── Report endpoints ────────────────────────────────────────────

@eval_router.get("/retrieval/reports")
async def list_retrieval_reports(limit: int = Query(10, ge=1, le=100)):
    """List recent retrieval evaluation reports."""
    report_dir = Path(config.report_dir)
    if not report_dir.exists():
        return {"reports": []}

    reports = sorted(report_dir.glob("retrieval_eval_*.json"), reverse=True)[:limit]
    result = []
    for r in reports:
        try:
            import json
            with open(r, encoding="utf-8") as f:
                data = json.load(f)
            result.append({
                "id": data.get("id", r.stem),
                "timestamp": data.get("timestamp"),
                "case_count": data.get("case_count", 0),
                "modes": data.get("modes", []),
                "top_k": data.get("top_k", 5),
                "use_hyde": data.get("use_hyde", True),
            })
        except Exception:
            result.append({"id": r.stem, "timestamp": None, "error": "Failed to read"})

    return {"reports": result}


@eval_router.get("/retrieval/report/latest")
async def get_latest_retrieval_report():
    """Get the most recent retrieval evaluation report."""
    report_dir = Path(config.report_dir)
    reports = sorted(report_dir.glob("retrieval_eval_*.json"), reverse=True)
    if not reports:
        raise HTTPException(404, "No retrieval evaluation reports found")

    import json
    with open(reports[0], encoding="utf-8") as f:
        return json.load(f)


@eval_router.get("/retrieval/report/{eval_id}")
async def get_retrieval_report(eval_id: str):
    """Get a specific retrieval evaluation report by ID."""
    report_path = Path(config.report_dir) / f"{eval_id}.json"
    if not report_path.exists():
        raise HTTPException(404, f"Report {eval_id} not found")

    import json
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)
