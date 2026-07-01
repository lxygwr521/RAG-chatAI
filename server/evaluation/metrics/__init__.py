"""RAGAS metric wrappers -- compatible with RAGAS 0.4.x (class-based metrics).

Metrics are loaded lazily so the module imports cleanly without RAGAS installed.
"""

import logging

logger = logging.getLogger(__name__)

# Lazy state
_ragas_available = False
_ragas_metrics = {}


def _ensure_ragas():
    """Lazy-load RAGAS on first use. Raises ImportError if not installed."""
    global _ragas_available, _ragas_metrics
    if _ragas_available:
        return
    try:
        # RAGAS 0.4.x tries to import ChatVertexAI from langchain_community,
        # which may not exist in newer langchain-community versions.
        # Stub it out if missing.
        import sys as _sys
        try:
            from langchain_community.chat_models.vertexai import ChatVertexAI  # noqa: F401
        except ImportError:
            _sys.modules.setdefault("langchain_community.chat_models.vertexai", type(_sys)("vstub"))
            _sys.modules["langchain_community.chat_models.vertexai"].ChatVertexAI = type("ChatVertexAI", (), {})

        from ragas import evaluate as _evaluate
        from ragas.metrics._faithfulness import Faithfulness
        from ragas.metrics._answer_relevance import AnswerRelevancy
        from ragas.metrics._context_precision import ContextPrecision
        from ragas.metrics._context_recall import ContextRecall

        global ragas_evaluate
        ragas_evaluate = _evaluate

        # RAGAS 0.4.x uses class instances, not module-level singletons
        _ragas_metrics = {
            "faithfulness": Faithfulness(),
            "answer_relevancy": AnswerRelevancy(),
            "context_precision": ContextPrecision(),
            "context_recall": ContextRecall(),
        }
        _ragas_available = True
        logger.info("RAGAS 0.4.x metrics loaded (4 metrics)")
    except ImportError as e:
        raise ImportError(
            "RAGAS is required for evaluation. Install with: pip install ragas datasets pandas"
        ) from e


# Public metric registry (populated on first use)
METRICS: dict = {}


def _get_metrics():
    _ensure_ragas()
    return _ragas_metrics


def get_metrics(names: list[str] | None = None) -> list:
    """Get RAGAS metric instances by name. None -> all."""
    metrics = _get_metrics()
    if names is None:
        return list(metrics.values())
    selected = []
    for name in names:
        if name in metrics:
            selected.append(metrics[name])
        else:
            logger.warning("Unknown metric: %s, skipping", name)
    return selected


async def evaluate_single(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None = None,
    llm=None,
    embeddings=None,
    metric_names: list[str] | None = None,
) -> dict[str, float]:
    """Evaluate a single RAG query-answer-context triplet."""
    if not contexts:
        return {"error": "no_contexts", "message": "No contexts provided"}

    selected = get_metrics(metric_names)
    if ground_truth is None:
        selected = [m for m in selected if m.name != "context_recall"]

    if not selected:
        return {"error": "no_metrics", "message": "No applicable metrics"}

    from datasets import Dataset

    # RAGAS 0.4.x expects specific column names different from 0.3.x
    data = {
        "user_input": [question],
        "response": [answer],
        "retrieved_contexts": [contexts],
    }
    if ground_truth:
        data["reference"] = [ground_truth]

    # Filter metrics to only those whose required columns we have
    available_cols = set(data.keys())
    valid_metrics = []
    for m in selected:
        required = m.required_columns.get("SINGLE_TURN", set())
        missing = required - available_cols
        if missing:
            logger.warning("Skipping %s: missing columns %s", m.name, missing)
        else:
            valid_metrics.append(m)

    if not valid_metrics:
        return {"error": "no_metrics", "message": "No metrics have all required columns"}

    dataset = Dataset.from_dict(data)

    try:
        result = ragas_evaluate(
            dataset,
            metrics=valid_metrics,
            llm=llm,
            embeddings=embeddings,
        )
        # RAGAS 0.4.x returns EvaluationResult — use to_pandas() for safe extraction
        df = result.to_pandas()
        scores = {}
        for m in valid_metrics:
            col = m.name
            if col in df.columns:
                val = df[col].iloc[0]
                scores[col] = round(float(val), 4) if not (isinstance(val, float) and (val != val)) else None
        return scores
    except Exception as e:
        import traceback
        logger.error("Evaluation failed: %s\n%s", e, traceback.format_exc())
        return {"error": "eval_failed", "message": str(e)}


async def evaluate_batch(
    test_cases: list[dict],
    llm=None,
    embeddings=None,
    metric_names: list[str] | None = None,
) -> dict:
    """Evaluate a batch of test cases using RAGAS."""
    selected = get_metrics(metric_names)
    has_ground_truth = any("ground_truth" in tc for tc in test_cases)
    if not has_ground_truth:
        selected = [m for m in selected if m.name != "context_recall"]

    if not selected:
        return {"error": "no_metrics", "scores": [], "summary": {}}

    from datasets import Dataset

    # RAGAS 0.4.x column names
    data = {
        "user_input": [],
        "response": [],
        "retrieved_contexts": [],
    }
    if has_ground_truth:
        data["reference"] = []

    for tc in test_cases:
        data["user_input"].append(tc["question"])
        data["response"].append(tc["answer"])
        data["retrieved_contexts"].append(tc.get("contexts", []))
        if has_ground_truth:
            data["reference"].append(tc.get("ground_truth", ""))

    # Filter metrics to only those with all required columns
    available_cols = set(data.keys())
    valid_metrics = []
    for m in selected:
        required = m.required_columns.get("SINGLE_TURN", set())
        missing = required - available_cols
        if missing:
            logger.warning("Skipping %s: missing columns %s", m.name, missing)
        else:
            valid_metrics.append(m)

    if not valid_metrics:
        return {"error": "no_metrics", "scores": [], "summary": {}}

    dataset = Dataset.from_dict(data)

    try:
        result = ragas_evaluate(
            dataset,
            metrics=valid_metrics,
            llm=llm,
            embeddings=embeddings,
        )

        scores = []
        metric_cols = [m.name for m in valid_metrics]
        df = result.to_pandas()
        for _, row in df.iterrows():
            case_score = {}
            for col in metric_cols:
                if col in row:
                    case_score[col] = round(float(row[col]), 4)
            scores.append(case_score)

        summary = {}
        for col in metric_cols:
            if col in df.columns:
                values = df[col].dropna()
                if len(values) > 0:
                    summary[col] = {
                        "mean": round(float(values.mean()), 4),
                        "min": round(float(values.min()), 4),
                        "max": round(float(values.max()), 4),
                    }

        return {
            "scores": scores,
            "summary": summary,
            "count": len(test_cases),
        }
    except Exception as e:
        logger.error("Batch evaluation failed: %s", e)
        return {"error": str(e), "scores": [], "summary": {}, "count": len(test_cases)}
