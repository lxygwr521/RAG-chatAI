"""Evaluation configuration -- paths for retrieval evaluation reports."""

from dataclasses import dataclass


@dataclass
class EvalConfig:
    """Central configuration for retrieval evaluation."""

    # Report output
    report_dir: str = "evaluation/reports"


# Global config instance
config = EvalConfig()
