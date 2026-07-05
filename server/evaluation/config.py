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

    # Regression detection
    regression_threshold: float = 0.05  # 5% drop triggers warning

    # Testset auto-generation (RAGAS TestsetGenerator)
    testset_cache_path: str = "evaluation/dataset/auto_test_cases.json"
    testset_size: int = 30  # number of synthetic test cases to generate
    generator_model: str = "deepseek-chat"  # LLM for question/answer generation
    generator_temperature: float = 0.3  # slight creativity for diverse questions

    # Report output
    report_dir: str = "evaluation/reports"
    report_format: str = "markdown"  # markdown | json | html

    # CI mode -- fail on low scores
    ci_mode: bool = False
    ci_blocking_metrics: list[str] = field(default_factory=lambda: ["faithfulness"])


# Global config instance
config = EvalConfig()
