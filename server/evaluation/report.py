"""Report generation -- Markdown, JSON, and terminal (rich) formats."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evaluation.runner import EvalResult
    from evaluation.config import EvalConfig


def generate_report(result: "EvalResult", config: "EvalConfig") -> str:
    """Generate a Markdown evaluation report."""
    lines = [
        f"# RAGAS Evaluation Report",
        f"",
        f"**ID**: `{result.id}`  ",
        f"**Timestamp**: {result.timestamp}  ",
        f"**Cases**: {result.case_count} total, {result.pass_count} pass, {result.fail_count} fail",
        f"",
        "## Metric Summary",
        f"",
    ]

    # Summary table
    if result.metric_summary:
        lines.append("| Metric | Mean | Min | Max | Target | Status |")
        lines.append("|--------|------|-----|-----|--------|--------|")
        thresholds = {
            "faithfulness": config.faithfulness_min,
            "answer_relevancy": config.answer_relevancy_min,
            "context_precision": config.context_precision_min,
            "context_recall": config.context_recall_min,
        }
        for metric, stats in result.metric_summary.items():
            target = thresholds.get(metric, 0.7)
            passed = stats["mean"] >= target
            status = "PASS" if passed else "WARN"
            lines.append(
                f"| {metric} | {stats['mean']:.4f} | {stats['min']:.4f} | {stats['max']:.4f} | >={target:.2f} | {status} |"
            )
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Per-case scores (truncated for readability)
    if len(result.per_case_scores) <= 20:
        lines.append("## Per-Case Scores")
        lines.append("")
        if result.per_case_scores:
            # Build table header
            metric_names = list(result.per_case_scores[0].keys())
            header = "| # | " + " | ".join(metric_names) + " |"
            sep = "|---|" + "|".join(["------" for _ in metric_names]) + "|"
            lines.append(header)
            lines.append(sep)
            for i, scores in enumerate(result.per_case_scores):
                vals = " | ".join(f"{scores.get(m, 'N/A')}" for m in metric_names)
                lines.append(f"| {i + 1} | {vals} |")
        lines.append("")

    return "\n".join(lines)


def generate_json_report(result: "EvalResult") -> str:
    """Generate a JSON evaluation report string."""
    import json

    data = {
        "id": result.id,
        "timestamp": result.timestamp,
        "case_count": result.case_count,
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "summary": result.metric_summary,
        "scores": result.per_case_scores,
        "warnings": result.warnings,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def print_rich_report(result: "EvalResult", config: "EvalConfig") -> None:
    """Print evaluation results to terminal using rich."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
    except ImportError:
        # Fallback to plain print
        print(generate_report(result, config))
        return

    console = Console()

    # Summary panel
    summary_text = (
        f"Cases: {result.case_count}  |  "
        f"Pass: [green]{result.pass_count}[/green]  |  "
        f"Fail: [red]{result.fail_count}[/red]"
    )
    console.print(Panel(summary_text, title=f"Evaluation: {result.id}", expand=False))

    # Metrics table
    table = Table(title="RAGAS Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Mean", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status")

    thresholds = {
        "faithfulness": config.faithfulness_min,
        "answer_relevancy": config.answer_relevancy_min,
        "context_precision": config.context_precision_min,
        "context_recall": config.context_recall_min,
    }

    for metric, stats in result.metric_summary.items():
        target = thresholds.get(metric, 0.7)
        passed = stats["mean"] >= target
        status = "[green]OK[/green]" if passed else "[yellow]!![/yellow]"
        table.add_row(
            metric,
            f"{stats['mean']:.4f}",
            f"{stats['min']:.4f}",
            f"{stats['max']:.4f}",
            f">={target:.2f}",
            status,
        )

    console.print(table)

    # Warnings
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  • {w}")

    console.print()
