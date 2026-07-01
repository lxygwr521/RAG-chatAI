"""RAGAS evaluation runner -- orchestrates end-to-end evaluation."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings
from evaluation.config import config
from evaluation.dataset.test_cases import load_test_cases
from evaluation.metrics import evaluate_single, evaluate_batch, METRICS
from evaluation.report import generate_report

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result of a single evaluation run."""

    id: str
    timestamp: str
    metric_summary: dict[str, dict]
    per_case_scores: list[dict]
    case_count: int
    pass_count: int
    fail_count: int
    warnings: list[str] = field(default_factory=list)


class EvaluationRunner:
    """Runs RAGAS evaluations against the current RAG pipeline.

    Usage::

        runner = EvaluationRunner()
        # Single evaluation
        result = await runner.evaluate_one(question, answer, contexts)
        # Batch against test cases
        report = await runner.run_batch()
        # Regression check
        regression = await runner.check_regression()
    """

    def __init__(self, metric_names: list[str] | None = None):
        self.metric_names = metric_names
        self._judge_llm = None
        self._embeddings = None
        self._baseline_path = Path(config.report_dir) / "baseline.json"

    @property
    def judge_llm(self):
        if self._judge_llm is None:
            class _DeepSeekJudgeLLM(ChatOpenAI):
                """Wrapper: DeepSeek only supports n=1, but RAGAS may request n>1.

                Forces n=1 and duplicates the response to satisfy callers that expect
                multiple generations (e.g. AnswerRelevancy which requests n=3).
                """

                def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                    requested_n = kwargs.pop("n", 1)
                    kwargs["n"] = 1
                    result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    if requested_n > 1 and result.generations:
                        # Duplicate the first response to match requested n
                        for gens in result.generations:
                            while len(gens) < requested_n:
                                gens.append(gens[0])
                    return result

                async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                    requested_n = kwargs.pop("n", 1)
                    kwargs["n"] = 1
                    result = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    if requested_n > 1 and result.generations:
                        for gens in result.generations:
                            while len(gens) < requested_n:
                                gens.append(gens[0])
                    return result

            self._judge_llm = _DeepSeekJudgeLLM(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=config.judge_model,
                temperature=config.judge_temperature,
            )
        return self._judge_llm

    @property
    def embeddings(self):
        if self._embeddings is None:
            # Use OpenAI-compatible embeddings (ZhipuAI)
            self._embeddings = OpenAIEmbeddings(
                api_key=settings.zhipuai_api_key,
                base_url=settings.zhipuai_base_url,
                model=settings.zhipuai_embedding_model,
            )
        return self._embeddings

    async def evaluate_one(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> dict:
        """Evaluate a single question-answer pair."""
        return await evaluate_single(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
            llm=self.judge_llm,
            embeddings=self.embeddings,
            metric_names=self.metric_names,
        )

    async def prepare_test_cases(
        self,
        questions: list[dict] | None = None,
    ) -> list[dict]:
        """Run the RAG pipeline on each test question to fill answers + contexts.

        For each test case:
          1. Call augment_chat to retrieve relevant chunks (contexts)
          2. Call agent_service to generate the answer
          3. Return filled test case ready for evaluation

        Args:
            questions: List of test case dicts with at least "question" key.
                       None -> load defaults.

        Returns:
            List of test cases with question, answer, contexts populated.
        """
        from app.services.rag_service import augment_chat
        from app.services.agent_service import agent_service

        if questions is None:
            questions = load_test_cases()

        filled = []
        skipped = []

        for i, tc in enumerate(questions):
            question = tc["question"]
            logger.info("Preparing [%d/%d]: %s", i + 1, len(questions), question[:60])

            try:
                # Step 1: Retrieve contexts via RAG
                rag_result = await augment_chat(
                    system_prompt="",
                    history=[],
                    user_content=question,
                )
                contexts = [c["snippet"] for c in rag_result.citations] if rag_result.citations else []

                # Step 2: Generate answer via agent
                answer_text = ""
                async for event in agent_service.run(
                    messages=[{"role": "user", "content": question}],
                    model="deepseek",
                ):
                    if event.event == "delta":
                        data = event.data if isinstance(event.data, dict) else {}
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        answer_text += delta.get("content", "")
                    elif event.event == "done":
                        break

                filled.append({
                    **tc,
                    "answer": answer_text.strip(),
                    "contexts": contexts,
                })
                logger.info("  -> %d contexts, %d chars answer", len(contexts), len(answer_text))

            except Exception as e:
                logger.error("  X failed: %s", e)
                skipped.append({"question": question, "error": str(e)})

        logger.info("Prepared %d/%d test cases (%d skipped)", len(filled), len(questions), len(skipped))
        return filled

    async def run_batch(
        self,
        test_cases: list[dict] | None = None,
        persist: bool = True,
    ) -> EvalResult:
        """Run evaluation against all test cases.

        Args:
            test_cases: Test cases with question, answer, contexts.
                        If None, loads defaults and needs actual RAG pipeline to fill answers.
            persist: Save report to disk.

        Returns:
            EvalResult with summary and per-case scores.
        """
        if test_cases is None:
            test_cases = load_test_cases()
            logger.warning(
                "Default test cases loaded (no answers/contexts). "
                "Use run_against_pipeline() to fill them automatically."
            )

        # Filter to test cases that have answers and contexts
        ready = [tc for tc in test_cases if tc.get("answer") and tc.get("contexts")]
        if not ready:
            logger.error("No test cases with answers + contexts. "
                         "Run the RAG pipeline on questions first.")
            return EvalResult(
                id="",
                timestamp=datetime.now(timezone.utc).isoformat(),
                metric_summary={},
                per_case_scores=[],
                case_count=0,
                pass_count=0,
                fail_count=0,
                warnings=["No ready test cases"],
            )

        t0 = time.time()
        batch_result = await evaluate_batch(
            ready,
            llm=self.judge_llm,
            embeddings=self.embeddings,
            metric_names=self.metric_names,
        )
        elapsed = round(time.time() - t0, 2)

        summary = batch_result.get("summary", {})
        scores = batch_result.get("scores", [])

        # Check thresholds
        warnings = self._check_thresholds(summary)
        pass_count, fail_count = self._count_pass_fail(scores)

        result = EvalResult(
            id=f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_summary=summary,
            per_case_scores=scores,
            case_count=len(ready),
            pass_count=pass_count,
            fail_count=fail_count,
            warnings=warnings,
        )

        if persist:
            self._save_result(result, elapsed)

        return result

    async def check_regression(self) -> dict:
        """Compare latest evaluation against baseline.

        Returns:
            Dict with regression status per metric.
        """
        if not self._baseline_path.exists():
            return {"status": "no_baseline", "message": "No baseline set. Run /eval/baseline first."}

        with open(self._baseline_path) as f:
            baseline = json.load(f)

        # Run current evaluation
        current = await self.run_batch(persist=False)

        if "error" in current.metric_summary:
            return {"status": "error", "message": current.metric_summary.get("error")}

        regressions = []
        for metric, stats in current.metric_summary.items():
            baseline_mean = baseline.get("summary", {}).get(metric, {}).get("mean")
            if baseline_mean is not None and stats.get("mean") is not None:
                delta = baseline_mean - stats["mean"]
                if delta > config.regression_threshold:
                    regressions.append({
                        "metric": metric,
                        "baseline": round(baseline_mean, 4),
                        "current": round(stats["mean"], 4),
                        "delta": round(delta, 4),
                        "degraded": True,
                    })
                elif delta > 0:
                    regressions.append({
                        "metric": metric,
                        "baseline": round(baseline_mean, 4),
                        "current": round(stats["mean"], 4),
                        "delta": round(delta, 4),
                        "degraded": False,
                    })

        has_regression = any(r["degraded"] for r in regressions)
        return {
            "status": "regression" if has_regression else "stable",
            "regressions": regressions,
            "current_id": current.id,
        }

    def set_baseline(self, eval_id: str | None = None) -> str:
        """Set current (or specific) evaluation as baseline.

        Args:
            eval_id: Specific evaluation ID, or None -> latest.

        Returns:
            Path to the baseline file.
        """
        report_dir = Path(config.report_dir)
        if eval_id:
            report_path = report_dir / f"{eval_id}.json"
        else:
            # Find latest
            reports = sorted(report_dir.glob("eval_*.json"))
            if not reports:
                return ""
            report_path = reports[-1]

        if not report_path.exists():
            return ""

        with open(report_path) as f:
            data = json.load(f)

        os.makedirs(report_dir, exist_ok=True)
        with open(self._baseline_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Baseline set from %s", report_path.name)
        return str(self._baseline_path)

    # ── helpers ──────────────────────────────────────────────────

    def _check_thresholds(self, summary: dict) -> list[str]:
        warnings = []
        thresholds = {
            "faithfulness": config.faithfulness_min,
            "answer_relevancy": config.answer_relevancy_min,
            "context_precision": config.context_precision_min,
            "context_recall": config.context_recall_min,
            "context_relevancy": config.context_relevancy_min,
        }
        for metric, threshold in thresholds.items():
            if metric in summary:
                mean = summary[metric]["mean"]
                if mean < threshold:
                    warnings.append(
                        f"{metric}: {mean:.3f} < {threshold:.3f} (threshold)"
                    )
        return warnings

    def _count_pass_fail(self, scores: list[dict]) -> tuple[int, int]:
        if not scores or not self.metric_names:
            return 0, 0

        # Use primary metric (first in list) for pass/fail
        primary = self.metric_names[0] if self.metric_names else "faithfulness"
        threshold = getattr(config, f"{primary}_min", 0.7)

        passes = sum(1 for s in scores if s.get(primary, 0) >= threshold)
        fails = len(scores) - passes
        return passes, fails

    def _save_result(self, result: EvalResult, elapsed_seconds: float) -> None:
        report_dir = Path(config.report_dir)
        os.makedirs(report_dir, exist_ok=True)

        data = {
            "id": result.id,
            "timestamp": result.timestamp,
            "elapsed_seconds": elapsed_seconds,
            "case_count": result.case_count,
            "pass_count": result.pass_count,
            "fail_count": result.fail_count,
            "summary": result.metric_summary,
            "scores": result.per_case_scores,
            "warnings": result.warnings,
        }

        path = report_dir / f"{result.id}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Also generate Markdown report
        md_path = report_dir / f"{result.id}.md"
        md_content = generate_report(result, config)
        with open(md_path, "w") as f:
            f.write(md_content)

        logger.info("Report saved: %s (%d cases, %.1fs)", path.name, result.case_count, elapsed_seconds)


# Global singleton
runner = EvaluationRunner()
