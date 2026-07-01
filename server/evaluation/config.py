"""Evaluation configuration -- thresholds, model settings, dataset paths."""

from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Central configuration for RAG evaluation."""

    # Model used as judge (should be stronger than the model being evaluated)
    judge_model: str = "deepseek-chat"
    judge_temperature: float = 0.0  # deterministic for evaluation

    # Metric thresholds (scores below these trigger warnings)
    faithfulness_min: float = 0.80
    answer_relevancy_min: float = 0.70
    context_precision_min: float = 0.70
    context_recall_min: float = 0.70
    context_relevancy_min: float = 0.60

    # Regression detection
    regression_threshold: float = 0.05  # 5% drop triggers warning

    # Dataset
    manual_dataset_path: str = "evaluation/dataset/test_cases.py"
    auto_dataset_size: int = 50  # number of auto-generated test cases

    # Report output
    report_dir: str = "evaluation/reports"
    report_format: str = "markdown"  # markdown | json | html

    # CI mode -- fail on low scores
    ci_mode: bool = False
    ci_blocking_metrics: list[str] = field(default_factory=lambda: ["faithfulness"])


# Global config instance
config = EvalConfig()
