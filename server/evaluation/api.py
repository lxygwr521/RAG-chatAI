"""Evaluation API endpoints under /api/eval/*."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from evaluation.agent_runner import run_agent_evaluation
from evaluation.config import config
from evaluation.dataset.agent_cases import load_agent_cases
from evaluation.dataset.retrieval_cases import load_retrieval_cases
from evaluation.retrieval_runner import RETRIEVAL_MODES, run_retrieval_evaluation

eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])


class RetrievalEvalRequest(BaseModel):
    """Request to run retrieval-only evaluation."""

    modes: list[str] | None = Field(None, description="Modes to compare. None = all.")
    top_k: int = Field(5, ge=1, le=20)
    use_hyde: bool = True
    persist: bool = True


class AgentEvalRequest(BaseModel):
    """Request to run end-to-end Agent evaluation."""

    case_ids: list[str] | None = Field(None, description="Case IDs to run. None = all.")
    categories: list[str] | None = Field(None, description="Categories to run. None = all.")
    persist: bool = True
    judge_model: str | None = Field(None, description="OpenRouter model slug override.")
    judge_runs: int = Field(1, ge=1, le=5)


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


@eval_router.get("/agent/test-cases")
async def get_agent_test_cases():
    """List end-to-end Agent evaluation test cases."""
    cases = load_agent_cases()
    categories = sorted({case.get("category", "unknown") for case in cases})
    return {
        "count": len(cases),
        "categories": categories,
        "cases": cases,
    }


@eval_router.post("/agent/run")
async def run_agent_eval(request: AgentEvalRequest | None = None):
    """Run end-to-end Agent quality evaluation with LLM-as-judge."""
    body = request or AgentEvalRequest()
    try:
        result = await run_agent_evaluation(
            case_ids=body.case_ids,
            categories=body.categories,
            persist=body.persist,
            judge_model=body.judge_model,
            judge_runs=body.judge_runs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "completed",
        "id": result.id,
        "summary": result.summary,
        "case_count": result.case_count,
        "judge_model": result.judge_model,
        "judge_runs": result.judge_runs,
    }


@eval_router.get("/retrieval/reports")
async def list_retrieval_reports(limit: int = Query(10, ge=1, le=100)):
    """List recent retrieval evaluation reports."""
    report_dir = Path(config.report_dir)
    if not report_dir.exists():
        return {"reports": []}

    reports = sorted(report_dir.glob("retrieval_eval_*.json"), reverse=True)[:limit]
    result = []
    for report in reports:
        try:
            with open(report, encoding="utf-8") as file:
                data = json.load(file)
            result.append({
                "id": data.get("id", report.stem),
                "timestamp": data.get("timestamp"),
                "case_count": data.get("case_count", 0),
                "modes": data.get("modes", []),
                "top_k": data.get("top_k", 5),
                "use_hyde": data.get("use_hyde", True),
            })
        except Exception:
            result.append({"id": report.stem, "timestamp": None, "error": "Failed to read"})

    return {"reports": result}


@eval_router.get("/retrieval/report/latest")
async def get_latest_retrieval_report():
    """Get the most recent retrieval evaluation report."""
    report_dir = Path(config.report_dir)
    reports = sorted(report_dir.glob("retrieval_eval_*.json"), reverse=True)
    if not reports:
        raise HTTPException(404, "No retrieval evaluation reports found")

    with open(reports[0], encoding="utf-8") as file:
        return json.load(file)


@eval_router.get("/retrieval/report/{eval_id}")
async def get_retrieval_report(eval_id: str):
    """Get a specific retrieval evaluation report by ID."""
    report_path = Path(config.report_dir) / f"{eval_id}.json"
    if not report_path.exists():
        raise HTTPException(404, f"Report {eval_id} not found")

    with open(report_path, encoding="utf-8") as file:
        return json.load(file)


@eval_router.get("/agent/reports")
async def list_agent_reports(limit: int = Query(10, ge=1, le=100)):
    """List recent end-to-end Agent evaluation reports."""
    report_dir = Path(config.report_dir)
    if not report_dir.exists():
        return {"reports": []}

    reports = sorted(report_dir.glob(f"{config.agent_report_prefix}_*.json"), reverse=True)[:limit]
    result = []
    for report in reports:
        try:
            with open(report, encoding="utf-8") as file:
                data = json.load(file)
            result.append({
                "id": data.get("id", report.stem),
                "timestamp": data.get("timestamp"),
                "case_count": data.get("case_count", 0),
                "judge_model": data.get("judge_model"),
                "judge_runs": data.get("judge_runs", 1),
                "summary": data.get("summary", {}),
            })
        except Exception:
            result.append({"id": report.stem, "timestamp": None, "error": "Failed to read"})

    return {"reports": result}


@eval_router.get("/agent/report/latest")
async def get_latest_agent_report():
    """Get the most recent end-to-end Agent evaluation report."""
    report_dir = Path(config.report_dir)
    reports = sorted(report_dir.glob(f"{config.agent_report_prefix}_*.json"), reverse=True)
    if not reports:
        raise HTTPException(404, "No agent evaluation reports found")

    with open(reports[0], encoding="utf-8") as file:
        return json.load(file)


@eval_router.get("/agent/report/{eval_id}")
async def get_agent_report(eval_id: str):
    """Get a specific end-to-end Agent evaluation report by ID."""
    report_path = Path(config.report_dir) / f"{eval_id}.json"
    if not report_path.exists():
        raise HTTPException(404, f"Report {eval_id} not found")

    with open(report_path, encoding="utf-8") as file:
        return json.load(file)
