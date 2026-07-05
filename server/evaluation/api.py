"""Evaluation API endpoints -- /api/eval/*"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from evaluation.config import config
from evaluation.runner import runner
from evaluation.dataset.test_cases import load_test_cases
from evaluation.dataset.retrieval_cases import load_retrieval_cases
from evaluation.retrieval_runner import RETRIEVAL_MODES, run_retrieval_evaluation

eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])


# ── Request / Response models ────────────────────────────────────

class EvalRunRequest(BaseModel):
    """Request to run an evaluation."""
    metric_names: list[str] | None = Field(None, description="Metrics to compute. None = all.")


class GenerateRequest(BaseModel):
    """Request to generate a synthetic testset from the knowledge base."""
    testset_size: int | None = Field(None, ge=5, le=200, description="Number of test cases. None = config default.")
    force: bool = Field(False, description="Regenerate even if cache exists.")


class RetrievalEvalRequest(BaseModel):
    """Request to run retrieval-only evaluation."""
    modes: list[str] | None = Field(None, description="Modes to compare. None = all.")
    top_k: int = Field(5, ge=1, le=20)
    use_hyde: bool = True
    persist: bool = True


class RegressionResponse(BaseModel):
    status: str
    regressions: list[dict] = []
    current_id: str | None = None
    message: str | None = None


class BaselineResponse(BaseModel):
    status: str
    path: str


# ── Endpoints ────────────────────────────────────────────────────

@eval_router.post("/generate")
async def generate_testset(request: GenerateRequest | None = None):
    """Generate a synthetic evaluation testset from the knowledge base.

    Uses RAGAS TestsetGenerator to create (question, ground_truth, reference_contexts)
    triples from ChromaDB documents. Results are cached to disk for subsequent
    /eval/prepare and /eval/run calls.

    This requires knowledge base documents to be uploaded first.
    Generation may take several minutes depending on testset_size.
    """
    body = request or GenerateRequest()
    result = await runner.generate_testset(
        testset_size=body.testset_size,
        force=body.force,
    )
    return result


@eval_router.post("/prepare")
async def prepare_test_cases():
    """Run the RAG + Agent pipeline on all test questions to fill answers + contexts.

    Call /eval/generate first to create the testset from the knowledge base,
    then call this endpoint to run the actual RAG retrieval and Agent answer
    generation on each question. The filled results are held in memory for
    a subsequent /eval/run call.
    """
    from evaluation.runner import runner as eval_runner

    questions = load_test_cases()
    if not questions:
        raise HTTPException(
            status_code=400,
            detail="No test cases available. POST to /api/eval/generate first.",
        )

    filled = await eval_runner.prepare_test_cases(questions)

    # Store in memory for the next /eval/run call
    _prepared_cases.clear()
    _prepared_cases.extend(filled)

    return {
        "status": "completed",
        "prepared_count": len(filled),
        "total_count": len(questions),
    }


# In-memory store for prepared test cases
_prepared_cases: list[dict] = []


@eval_router.post("/run")
async def run_evaluation(request: EvalRunRequest | None = None):
    """Run a RAGAS evaluation against the current test cases.

    Test cases must have been prepared with answers and contexts
    (use the RAG pipeline to fill them before calling this endpoint).
    """
    metric_names = request.metric_names if request else None

    eval_runner = type(runner).__new__(type(runner))
    eval_runner.__init__(metric_names=metric_names)

    if not _prepared_cases:
        raise HTTPException(
            status_code=400,
            detail="No prepared test cases. POST to /api/eval/prepare first.",
        )

    test_cases = list(_prepared_cases)

    # Filter to test cases that have answers and contexts
    ready = [tc for tc in test_cases if tc.get("answer") and tc.get("contexts")]
    if not ready:
        return {
            "status": "no_data",
            "message": (
                "No test cases have answers/contexts. "
                "POST to /api/eval/prepare first to run the RAG pipeline on test questions."
            ),
            "test_case_count": len(test_cases),
            "ready_count": 0,
        }

    result = await eval_runner.run_batch(ready, persist=True)

    return {
        "status": "completed",
        "id": result.id,
        "summary": result.metric_summary,
        "case_count": result.case_count,
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "warnings": result.warnings,
    }


@eval_router.get("/report/latest")
async def get_latest_report():
    """Get the most recent evaluation report."""
    report_dir = Path(config.report_dir)
    reports = sorted(report_dir.glob("eval_*.json"), reverse=True)
    if not reports:
        raise HTTPException(404, "No evaluation reports found")

    with open(reports[0]) as f:
        return json.load(f)


@eval_router.get("/report/{eval_id}")
async def get_report(eval_id: str):
    """Get a specific evaluation report by ID."""
    report_path = Path(config.report_dir) / f"{eval_id}.json"
    if not report_path.exists():
        raise HTTPException(404, f"Report {eval_id} not found")

    with open(report_path) as f:
        return json.load(f)


@eval_router.get("/reports")
async def list_reports(limit: int = Query(10, ge=1, le=100)):
    """List recent evaluation reports."""
    report_dir = Path(config.report_dir)
    if not report_dir.exists():
        return {"reports": []}

    reports = sorted(report_dir.glob("eval_*.json"), reverse=True)[:limit]
    result = []
    for r in reports:
        try:
            with open(r) as f:
                data = json.load(f)
            result.append({
                "id": data.get("id", r.stem),
                "timestamp": data.get("timestamp"),
                "case_count": data.get("case_count", 0),
                "pass_count": data.get("pass_count", 0),
                "fail_count": data.get("fail_count", 0),
            })
        except Exception:
            result.append({"id": r.stem, "timestamp": None, "error": "Failed to read"})

    return {"reports": result}


@eval_router.post("/baseline")
async def set_baseline(eval_id: str | None = None):
    """Set an evaluation as the regression baseline."""
    path = runner.set_baseline(eval_id)
    if not path:
        raise HTTPException(404, "No evaluation found to set as baseline")

    return BaselineResponse(status="ok", path=path)


@eval_router.get("/regression")
async def check_regression():
    """Compare current evaluation against baseline to detect regressions."""
    result = await runner.check_regression()
    return result


@eval_router.get("/metrics")
async def list_metrics():
    """List available RAGAS metrics."""
    from evaluation.metrics import get_metrics

    metrics = get_metrics()
    return {
        "metrics": [
            {
                "name": m.name,
                "description": m.__doc__ or "(no description)",
            }
            for m in metrics
        ]
    }


@eval_router.get("/test-cases")
async def get_test_cases():
    """List available test cases (questions and ground_truth, no answers yet)."""
    cases = load_test_cases()
    return {
        "count": len(cases),
        "source": "auto_generated",
        "cases": [
            {
                "index": i,
                "question": tc["question"],
                "category": tc.get("category", "generated"),
                "difficulty": tc.get("difficulty", "auto"),
                "has_ground_truth": bool(tc.get("ground_truth")),
            }
            for i, tc in enumerate(cases)
        ],
    }


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
    """Run retrieval-only hit@k/MRR evaluation."""
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
