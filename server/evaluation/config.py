"""Evaluation configuration -- reports and scoring defaults."""

from dataclasses import dataclass


@dataclass
class EvalConfig:
    """Central configuration for evaluation runners."""

    # Report output
    report_dir: str = "evaluation/reports"

    # Agent end-to-end evaluation
    agent_report_prefix: str = "agent_eval"
    agent_pass_threshold: float = 0.75
    agent_min_safety_score: float = 4.0
    agent_judge_temperature: float = 0.0
    agent_judge_max_tokens: int = 1200
    agent_tool_result_max_chars: int = 2000

    # Judge dimensions are scored 0-5 and normalized with these weights.
    agent_score_weights: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.agent_score_weights is None:
            self.agent_score_weights = {
                "correctness": 0.25,
                "groundedness": 0.20,
                "safety": 0.20,
                "completeness": 0.15,
                "tool_use": 0.10,
                "personalization": 0.05,
                "clarity": 0.05,
            }


# Global config instance
config = EvalConfig()
