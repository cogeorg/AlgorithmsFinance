#!/usr/bin/env python3
"""Build the short assignment report from one saved measurement report."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from typing import Iterable, Mapping

from measurement.metrics import latency_summary, load_report, validate_report


PROJECT_ROOT = Path(__file__).resolve().parent


def _number(value: object, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}"


def _markdown_table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    materialized = [list(row) for row in rows]
    if not materialized:
        return "No saved measurements are available for this table."
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in materialized:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def _aggregate(
    records: Iterable[Mapping[str, object]],
    value_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        key = (
            record.get("experiment"),
            record.get("scenario"),
            record.get("event_count"),
            record.get("levels"),
            record.get("version"),
            record.get("phase"),
            record.get("liquidation_percent"),
        )
        grouped[key].append(record)
    output: list[dict[str, object]] = []
    for key, values in sorted(grouped.items(), key=lambda item: tuple(str(v) for v in item[0])):
        row: dict[str, object] = {
            "experiment": key[0],
            "scenario": key[1],
            "event_count": key[2],
            "levels": key[3],
            "version": key[4],
            "phase": key[5],
            "liquidation_percent": key[6],
            "seed_count": len(values),
            "completed_repeat_count": sum(
                int(value.get("completed_repeat_count", 0)) for value in values
            ),
            "stopped_repeat_count": sum(
                int(value.get("stopped_repeat_count", 0)) for value in values
            ),
            "expected_repeat_count": sum(
                int(value.get("expected_repeat_count", 0)) for value in values
            ),
            "missing_repeat_count": sum(
                int(value.get("missing_repeat_count", 0)) for value in values
            ),
        }
        for field in value_fields:
            present = [float(value[field]) for value in values if value.get(field) is not None]
            row[field] = statistics.median(present) if present else None
        output.append(row)
    return output


def _aggregate_timing(
    records: Iterable[Mapping[str, object]],
    phases: set[str],
) -> list[dict[str, object]]:
    """Pool completed raw repeats while taking coverage from saved summaries."""

    raw_groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    summary_groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        if record.get("phase") not in phases:
            continue
        key = (
            record.get("experiment"),
            record.get("scenario"),
            record.get("event_count"),
            record.get("levels"),
            record.get("version"),
            record.get("phase"),
            record.get("liquidation_percent"),
        )
        if record.get("measurement_kind") == "timing":
            raw_groups[key].append(record)
        elif record.get("measurement_kind") == "timing_summary":
            summary_groups[key].append(record)

    output: list[dict[str, object]] = []
    for key, summaries in sorted(
        summary_groups.items(), key=lambda item: tuple(str(value) for value in item[0])
    ):
        completed = [
            record
            for record in raw_groups.get(key, [])
            if not record.get("stopped") and record.get("elapsed_seconds") is not None
        ]
        elapsed = [float(record["elapsed_seconds"]) for record in completed]
        throughputs = [
            float(record["throughput_events_per_second"])
            for record in completed
            if record.get("throughput_events_per_second") is not None
        ]
        output.append(
            {
                "experiment": key[0],
                "scenario": key[1],
                "event_count": key[2],
                "levels": key[3],
                "version": key[4],
                "phase": key[5],
                "liquidation_percent": key[6],
                "seed_count": len(summaries),
                "completed_repeat_count": sum(
                    int(value.get("completed_repeat_count", 0)) for value in summaries
                ),
                "stopped_repeat_count": sum(
                    int(value.get("stopped_repeat_count", 0)) for value in summaries
                ),
                "expected_repeat_count": sum(
                    int(value.get("expected_repeat_count", 0)) for value in summaries
                ),
                "missing_repeat_count": sum(
                    int(value.get("missing_repeat_count", 0)) for value in summaries
                ),
                "elapsed_seconds_median": statistics.median(elapsed) if elapsed else None,
                "throughput_events_per_second_median": (
                    statistics.median(throughputs) if throughputs else None
                ),
            }
        )
    return output


def _aggregate_latency(
    records: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Pool saved event samples before computing nearest-rank percentiles."""

    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        key = (
            record.get("experiment"),
            record.get("scenario"),
            record.get("event_count"),
            record.get("levels"),
            record.get("version"),
            record.get("phase"),
            record.get("liquidation_percent"),
        )
        grouped[key].append(record)

    output: list[dict[str, object]] = []
    for key, values in sorted(
        grouped.items(), key=lambda item: tuple(str(value) for value in item[0])
    ):
        samples = [
            int(sample)
            for value in values
            for sample in value.get("samples_ns", [])
        ]
        row: dict[str, object] = {
            "experiment": key[0],
            "scenario": key[1],
            "event_count": key[2],
            "levels": key[3],
            "version": key[4],
            "phase": key[5],
            "liquidation_percent": key[6],
            "seed_count": len(values),
        }
        row.update(latency_summary(samples))
        output.append(row)
    return output


def _repeat_coverage(row: Mapping[str, object]) -> str:
    """Render completed/expected coverage without hiding stopped or missing work."""

    completed = int(row.get("completed_repeat_count", 0))
    stopped = int(row.get("stopped_repeat_count", 0))
    missing = int(row.get("missing_repeat_count", 0))
    expected = int(row.get("expected_repeat_count", 0))
    if not expected:
        expected = completed + stopped + missing
    if not expected:
        return "-"
    exceptions = []
    if stopped:
        exceptions.append(f"{stopped} stopped")
    if missing:
        exceptions.append(f"{missing} missing")
    suffix = f" ({', '.join(exceptions)})" if exceptions else ""
    return f"{completed}/{expected}{suffix}"


def render_report(report: dict[str, object]) -> str:
    """Render deterministic Markdown from saved evidence only."""

    validate_report(report)
    records: list[dict[str, object]] = report["records"]  # type: ignore[assignment]
    environment: dict[str, object] = report["environment"]  # type: ignore[assignment]
    settings: dict[str, object] = report["settings"]  # type: ignore[assignment]
    run_label = str(report["run_label"])
    integrity_revision = int(settings.get("measurement_integrity_revision", 0))
    clean_canonical = run_label == "canonical" and not environment.get("git_dirty")
    if clean_canonical and integrity_revision >= 4:
        status = "Canonical clean-tree evidence."
    elif clean_canonical:
        status = (
            "SUPERSEDED: legacy measurement evidence. This report predates "
            "measurement-integrity revision 4."
        )
    else:
        status = "PROVISIONAL: this report was produced from a noncanonical or dirty-tree run."

    correctness = [record for record in records if record["measurement_kind"] == "correctness"]
    completed_correctness = [record for record in correctness if not record["stopped"]]
    stopped_correctness = [record for record in correctness if record["stopped"]]
    correctness_passes = sum(
        bool(record.get("ordered_results_equal")) and bool(record.get("final_books_equal"))
        for record in completed_correctness
    )
    correctness_disagreements = len(completed_correctness) - correctness_passes
    stopped = [record for record in records if record.get("stopped")]
    partial_timing = [
        record
        for record in records
        if record.get("measurement_kind") == "timing_summary"
        and (
            record.get("completion_status") == "partial"
            or record.get("completion_status") == "missing"
            or int(record.get("missing_repeat_count", 0)) > 0
            or (
                int(record.get("completed_repeat_count", 0)) > 0
                and int(record.get("stopped_repeat_count", 0)) > 0
            )
        )
    ]
    missing_timing_repeats = sum(
        int(record.get("missing_repeat_count", 0))
        for record in records
        if record.get("measurement_kind") == "timing_summary"
    )

    timing = _aggregate_timing(
        records,
        {"engine_replay", "application_total"},
    )
    latency = _aggregate_latency(
        (
            record
            for record in records
            if record["measurement_kind"] == "latency" and not record["stopped"]
        )
    )
    memory = _aggregate(
        (
            record
            for record in records
            if record["measurement_kind"] == "memory"
            and record["phase"] == "engine_replay"
            and not record["stopped"]
        ),
        ("current_traced_bytes", "peak_traced_bytes"),
    )
    liquidation = _aggregate_timing(
        records,
        {"individual_sale"},
    )
    operations = [
        record for record in records if record["measurement_kind"] == "operation_counts"
    ]

    command = settings.get("command", [])
    command_text = " ".join(str(part) for part in command) if command else "not recorded"
    dataset_count = len(report.get("datasets", []))
    record_count = len(records)

    sections = [
        "# Limit order book report",
        "",
        f"**Evidence status:** {status}",
        "",
        f"Run label: `{run_label}`. Recorded code commit: `{environment.get('git_commit', 'unknown')}`. "
        f"The saved report contains {dataset_count} datasets and {record_count} records.",
        "",
        "## Specification and boundaries",
        "",
        "This project implements a sequential single-venue BTC limit order book with integer "
        "cent prices and integer 10^-8 BTC quantities. Better prices execute first and FIFO "
        "breaks ties. Trades use the resting maker price. A market sell consumes bids and "
        "discards any residual. The model intentionally excludes fees, balances, hidden "
        "orders, self-trade checks, simultaneous execution, networking, and historical "
        "exchange calibration; it is not a production trading system.",
        "",
        "## Correctness evidence",
        "",
        f"Completed correctness rows passing ordered-result and final-book agreement: "
        f"{correctness_passes}/{len(completed_correctness)}; {len(stopped_correctness)} were "
        f"stopped by the declared limit and {correctness_disagreements} completed rows "
        f"disagreed. Independent tests additionally cover "
        "worked fills, price-time priority, partial fills, cancellation, atomic validation, "
        "quantity/proceeds conservation, input immutability, and defensive inspection copies. "
        "Agreement is supporting evidence rather than a proof.",
        "",
        "## Implementation and revision",
        "",
        "Version A stores active makers in one list and scans for duplicates, cancellations, "
        "and the best maker. Version B indexes active identifiers and insertion-ordered FIFO "
        "price levels, with sorted price keys and eager empty-level cleanup. Both preserve the "
        "same API and tests. The revision targets work that grows with active depth while "
        "avoiding tombstones under cancellation churn. Detailed invariants, complexity, and AI "
        "decisions are recorded in `IMPLEMENTATION_NOTES.md`.",
        "",
        "## Runtime and throughput",
        "",
        _markdown_table(
            [
                "Experiment", "Scenario", "M", "Levels", "Version", "Phase",
                "Sale %", "Seeds", "Repeat coverage", "Median seconds", "Median events/s",
            ],
            (
                (
                    row["experiment"], row["scenario"], row["event_count"],
                    row["levels"], row["version"], row["phase"],
                    row["liquidation_percent"] if row["liquidation_percent"] is not None else "-",
                    row["seed_count"],
                    _repeat_coverage(row),
                    _number(row["elapsed_seconds_median"], 6),
                    _number(row["throughput_events_per_second_median"], 0),
                )
                for row in timing
            ),
        ),
        "",
        "Input reading/parsing is measured separately. `engine_replay` includes fresh empty-book "
        "construction and event processing; `application_total` adds the paired parse repeat. "
        "All displayed values are medians of saved raw repeats, not reciprocal-latency estimates.",
        "",
        "## Processing latency",
        "",
        _markdown_table(
            [
                "Experiment", "Scenario", "M", "Levels", "Version", "Seeds",
                "p50 ns", "p95 ns", "p99 ns",
            ],
            (
                (
                    row["experiment"], row["scenario"], row["event_count"],
                    row["levels"], row["version"], row["seed_count"],
                    _number(row["p50_ns"], 0), _number(row["p95_ns"], 0),
                    _number(row["p99_ns"], 0),
                )
                for row in latency
            ),
        ),
        "",
        "Latency is instrumented separately with `perf_counter_ns`, retained per event, and "
        "summarized with nearest-rank percentiles after pooling saved samples across seeds. "
        "Saved records also separate LIMIT, CANCEL, "
        "and MARKET_SELL events and compare the first and last 10% (capped at 1,000 events).",
        "",
        "## Memory",
        "",
        _markdown_table(
            [
                "Experiment", "Scenario", "M", "Levels", "Version", "Seeds",
                "Current MiB", "Peak MiB",
            ],
            (
                (
                    row["experiment"], row["scenario"], row["event_count"],
                    row["levels"], row["version"], row["seed_count"],
                    _number(float(row["current_traced_bytes"] or 0) / 1_048_576, 3),
                    _number(float(row["peak_traced_bytes"] or 0) / 1_048_576, 3),
                )
                for row in memory
            ),
        ),
        "",
        "Inputs are prepared before each fresh `tracemalloc` run and excluded. The live book, "
        "indexes/levels, final output, and negligible checkpoint integer bookkeeping are included; "
        "prior outputs are released. Native/process allocations are excluded, so these values are "
        "neither auxiliary space alone nor RSS.",
        "",
        "## Large liquidation",
        "",
        _markdown_table(
            ["Setup orders", "Version", "Sale %", "Seeds", "Repeat coverage", "Median sale seconds"],
            (
                (
                    row["event_count"], row["version"], row["liquidation_percent"],
                    row["seed_count"],
                    _repeat_coverage(row),
                    _number(row["elapsed_seconds_median"], 6),
                )
                for row in liquidation
            ),
        ),
        "",
        "Each percentage is evaluated against a freshly rebuilt identical bid book. Saved "
        "correctness rows contain requested quantity, makers touched, price levels visited, "
        "fills, and unfilled residual.",
        "",
        "## Bottleneck and operation counts",
        "",
        _markdown_table(
            [
                "Dataset", "Requested / processed", "Active peak", "Level peak",
                "Fills", "Visited levels", "Final active",
            ],
            (
                (
                    row.get("dataset_id"),
                    f"{row.get('events_requested', '-')} / {row.get('events_processed', '-')}",
                    row.get("active_order_peak"), row.get("occupied_price_level_peak"),
                    row.get("fill_count"), row.get("maker_price_levels_visited"),
                    row.get("final_active_order_count"),
                )
                for row in operations
            ),
        ),
        "",
        "The baseline can rescan B active orders for validation and each maker fill; the revision "
        "usually performs indexed lookup and FIFO-level access but pays O(P) when inserting or "
        "deleting a sorted price key. The active-depth, price-level, and fill counts above explain "
        "why performance can vary by workload; no claim assumes the revision wins everywhere.",
        "",
        "## Limitations",
        "",
        f"Stopped saved records: {len(stopped)}. Partial timing summaries: "
        f"{len(partial_timing)}. Missing timing repeats: {missing_timing_repeats}. "
        "Repeat coverage is shown in timing tables; declared stops and missing work are "
        "not extrapolated. Results are "
        "machine- and interpreter-specific synthetic measurements. Sequential processing excludes "
        "networking and queueing, so throughput does not establish live-venue overload capacity. "
        "The supplied data are teaching workloads rather than historical or calibrated market data. "
        "Passing tests and cross-version agreement do not constitute a formal proof.",
        "",
        "## Reproducibility",
        "",
        f"Python: `{environment.get('python_version', 'unknown')}`; platform: "
        f"`{environment.get('platform', 'unknown')}`; dirty tree: "
        f"`{environment.get('git_dirty', 'unknown')}`.",
        "",
        "Recorded measurement command:",
        "",
        "```text",
        command_text,
        "```",
        "",
        f"Time-limit scope: {settings.get('time_limit_scope', 'not recorded')}",
        "",
        "Run `python3 -m unittest discover -s tests -v`, rebuild the dashboard from the saved "
        "result file with `python3 dashboard.py`, and consult `MEASUREMENT_PLAN.md` for exact "
        "data preparation, timing, latency, and memory boundaries.",
        "",
    ]
    return "\n".join(sections)


def write_report_markdown(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=PROJECT_ROOT / "results" / "raw_measurements.json.gz",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "REPORT.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load_report(args.results)
    write_report_markdown(report, args.output)
    print(f"loaded_results={args.results}")
    print(f"run_label={report['run_label']}")
    print(f"report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
