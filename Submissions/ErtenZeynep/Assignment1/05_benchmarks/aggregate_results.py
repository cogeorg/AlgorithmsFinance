"""Deterministically aggregate retained benchmark evidence for the dashboard.

This script validates every input against ``07_results/results_manifest.json``.
It never imports a matching engine and never executes a benchmark.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "07_results" / "results_manifest.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "07_results" / "processed" / "aggregated_results.json"
HISTOGRAM_EDGES_NS = (
    0,
    10_000,
    20_000,
    50_000,
    100_000,
    200_000,
    500_000,
    1_000_000,
    2_000_000,
    5_000_000,
    10_000_000,
    20_000_000,
    50_000_000,
    100_000_000,
    200_000_000,
    500_000_000,
    1_000_000_000,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"Manifest path escapes the project: {relative_path}") from error
    return path


def read_jsonl(relative_path: str) -> tuple[bytes, list[dict[str, Any]]]:
    data = project_path(relative_path).read_bytes()
    if data and not data.endswith(b"\n"):
        raise ValueError(f"Truncated JSONL (missing final newline): {relative_path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Blank JSONL record: {relative_path}:{line_number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Malformed JSONL: {relative_path}:{line_number}: {error}"
            ) from error
        if not isinstance(record, dict):
            raise ValueError(f"Non-object JSONL record: {relative_path}:{line_number}")
        records.append(record)
    return data, records


def nonzero_status_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(record["status"] for record in records).items()))


def validate_jsonl_artifact(
    artifact: dict[str, Any], *, protocol_field: str | None = None
) -> list[dict[str, Any]]:
    data, records = read_jsonl(artifact["path"])
    if len(data) != artifact["bytes"]:
        raise ValueError(f"Size mismatch: {artifact['path']}")
    if sha256_bytes(data) != artifact["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {artifact['path']}")
    if len(records) != artifact["record_count"]:
        raise ValueError(f"Record-count mismatch: {artifact['path']}")
    expected_statuses = {
        name: count for name, count in artifact["status_counts"].items() if count
    }
    if nonzero_status_counts(records) != expected_statuses:
        raise ValueError(f"Status-count mismatch: {artifact['path']}")
    if protocol_field and artifact.get("recorded_protocol_version") is not None:
        protocols = {record.get(protocol_field) for record in records}
        if protocols != {artifact["recorded_protocol_version"]}:
            raise ValueError(f"Protocol mismatch: {artifact['path']}")
    return records


def validate_sources(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 2:
        raise ValueError("Expected results manifest schema 2")
    artifacts = manifest["artifacts"]
    pilot = validate_jsonl_artifact(artifacts["pilot"])
    cold = validate_jsonl_artifact(
        artifacts["cold_primary"], protocol_field="controller_protocol_version"
    )
    warmed = validate_jsonl_artifact(
        artifacts["warmed_primary"], protocol_field="controller_protocol_version"
    )
    parsing = validate_jsonl_artifact(artifacts["parsing"])
    if {record.get("protocol_version") for record in parsing} != {
        artifacts["parsing"]["recorded_protocol_version"]
    }:
        raise ValueError("Parsing protocol mismatch")
    if any(record.get("measurement_boundary", {}).get("engine_import_or_replay") for record in parsing):
        raise ValueError("Parsing evidence unexpectedly includes engine work")

    stage4e_records: dict[str, list[dict[str, Any]]] = {}
    combined: list[dict[str, Any]] = []
    for artifact in artifacts["stage4e"]["mode_artifacts"]:
        records = validate_jsonl_artifact(artifact)
        if {record.get("protocol_version") for record in records} != {
            artifacts["stage4e"]["recorded_protocol_version"]
        }:
            raise ValueError(f"Stage 4E protocol mismatch: {artifact['path']}")
        stage4e_records[artifact["measurement_mode"]] = records
        combined.extend(records)
    stage4e = artifacts["stage4e"]
    if len(combined) != stage4e["record_count"]:
        raise ValueError("Stage 4E combined record-count mismatch")
    expected_stage4e_statuses = {
        name: count for name, count in stage4e["status_counts"].items() if count
    }
    if nonzero_status_counts(combined) != expected_stage4e_statuses:
        raise ValueError("Stage 4E combined status-count mismatch")
    charged = sum(float(record.get("controller_wall_seconds") or 0) for record in combined)
    if not math.isclose(
        charged, stage4e["charged_controller_wall_seconds"], rel_tol=0, abs_tol=1e-12
    ):
        raise ValueError("Stage 4E charged-time mismatch")

    latency_manifest = stage4e["latency_raw"]
    latency_files: dict[str, dict[str, Any]] = {}
    fields = latency_manifest["file_fields"]
    for relative_path, compact_values in latency_manifest["files"].items():
        expected = dict(zip(fields, compact_values, strict=True))
        data = project_path(relative_path).read_bytes()
        if len(data) != expected["bytes"]:
            raise ValueError(f"Latency size mismatch: {relative_path}")
        if sha256_bytes(data) != expected["sha256"]:
            raise ValueError(f"Latency SHA-256 mismatch: {relative_path}")
        with gzip.open(project_path(relative_path), "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        if reader.fieldnames != ["event_index", "event_type", "latency_ns", "window"]:
            raise ValueError(f"Unexpected latency schema: {relative_path}")
        if len(rows) != expected["observations"]:
            raise ValueError(f"Latency observation mismatch: {relative_path}")
        latency_files[relative_path] = {"expected": expected, "rows": rows}
    if len(latency_files) != latency_manifest["artifact_count"]:
        raise ValueError("Latency artifact-count mismatch")
    if sum(item["expected"]["bytes"] for item in latency_files.values()) != latency_manifest[
        "total_bytes"
    ]:
        raise ValueError("Latency total-size mismatch")
    if sum(item["expected"]["observations"] for item in latency_files.values()) != latency_manifest[
        "total_observations"
    ]:
        raise ValueError("Latency total-observation mismatch")

    return {
        "pilot": pilot,
        "cold": cold,
        "warmed": warmed,
        "parsing": parsing,
        "stage4e": stage4e_records,
        "latency_files": latency_files,
    }


def median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def nearest_rank(values: list[int], percentile: float) -> int:
    if not values:
        raise ValueError("Percentile requires at least one observation")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def latency_stats(values: list[int]) -> dict[str, int | float]:
    return {
        "observations": len(values),
        "median_ns": statistics.median(values),
        "p95_nearest_rank_ns": nearest_rank(values, 0.95),
        "p99_nearest_rank_ns": nearest_rank(values, 0.99),
    }


def histogram(values: list[int]) -> list[dict[str, int | float | None]]:
    counts = [0] * len(HISTOGRAM_EDGES_NS)
    for value in values:
        index = len(HISTOGRAM_EDGES_NS) - 1
        for candidate, upper in enumerate(HISTOGRAM_EDGES_NS[1:]):
            if value < upper:
                index = candidate
                break
        counts[index] += 1
    bins: list[dict[str, int | float | None]] = []
    for index, count in enumerate(counts):
        lower = HISTOGRAM_EDGES_NS[index] / 1_000
        upper = (
            HISTOGRAM_EDGES_NS[index + 1] / 1_000
            if index + 1 < len(HISTOGRAM_EDGES_NS)
            else None
        )
        bins.append({"lower_us": lower, "upper_us": upper, "count": count})
    return bins


def aggregate_primary(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["engine"], record["scenario"], record["event_count"], record["seed"])].append(
            record
        )
    configurations: list[dict[str, Any]] = []
    for (engine, scenario, event_count, seed), group in sorted(grouped.items()):
        group.sort(key=lambda record: record["repetition"])
        if [record["repetition"] for record in group] != [1, 2, 3, 4, 5]:
            raise ValueError(f"Primary repetition coverage mismatch: {engine}/{scenario}/{event_count}/{seed}")
        completed = [record for record in group if record["status"] == "completed"]
        eligible = len(completed) == 5
        durations = [float(record["engine_seconds"]) for record in completed]
        controller_durations = [float(record["controller_wall_seconds"]) for record in completed]
        if any(duration <= 0 for duration in durations):
            raise ValueError("Completed primary duration must be positive")
        median_seconds = median_or_none(durations) if eligible else None
        median_controller_seconds = median_or_none(controller_durations) if eligible else None
        configurations.append(
            {
                "engine": engine,
                "scenario": scenario,
                "event_count": event_count,
                "seed": seed,
                "workload_id": group[0]["workload_id"],
                "workload_sha256": group[0]["workload_sha256"],
                "raw_repeats": [
                    {
                        "repetition": record["repetition"],
                        "status": record["status"],
                        "engine_seconds": record.get("engine_seconds"),
                        "preparation_seconds": record.get("preparation_seconds"),
                        "controller_wall_seconds": record.get("controller_wall_seconds"),
                    }
                    for record in group
                ],
                "status_counts": nonzero_status_counts(group),
                "five_repeat_complete": eligible,
                "median_engine_seconds": median_seconds,
                "median_controller_invocation_wall_seconds": median_controller_seconds,
                "throughput_events_per_second": (
                    event_count / median_seconds if median_seconds is not None else None
                ),
                "censoring_label": None if eligible else "incomplete_after_processing_timeout",
            }
        )
    if len(configurations) != 90:
        raise ValueError(f"Expected 90 warmed-primary configurations, found {len(configurations)}")

    by_workload = {
        (item["scenario"], item["event_count"], item["seed"], item["engine"]): item
        for item in configurations
    }
    speedups: list[dict[str, Any]] = []
    for scenario, event_count, seed in sorted(
        {(item["scenario"], item["event_count"], item["seed"]) for item in configurations}
    ):
        baseline = by_workload[(scenario, event_count, seed, "baseline")]
        optimized = by_workload[(scenario, event_count, seed, "optimized")]
        if baseline["five_repeat_complete"] and optimized["five_repeat_complete"]:
            speedups.append(
                {
                    "scenario": scenario,
                    "event_count": event_count,
                    "seed": seed,
                    "baseline_median_seconds": baseline["median_engine_seconds"],
                    "optimized_median_seconds": optimized["median_engine_seconds"],
                    "baseline_over_optimized_speedup": baseline["median_engine_seconds"]
                    / optimized["median_engine_seconds"],
                }
            )
    return configurations, speedups


def aggregate_parsing(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["scenario"], record["event_count"], record["seed"])].append(record)
    output = []
    for (scenario, event_count, seed), group in sorted(grouped.items()):
        group.sort(key=lambda record: record["repetition"])
        if [record["repetition"] for record in group] != [1, 2, 3, 4, 5]:
            raise ValueError(f"Parsing repetition coverage mismatch: {scenario}/{event_count}/{seed}")
        if any(record["status"] != "completed" for record in group):
            raise ValueError(f"Incomplete parsing configuration: {scenario}/{event_count}/{seed}")
        output.append(
            {
                "scenario": scenario,
                "event_count": event_count,
                "seed": seed,
                "workload_id": group[0]["workload_id"],
                "workload_sha256": group[0]["workload_sha256"],
                "compressed_bytes": group[0]["compressed_bytes"],
                "decompressed_bytes": group[0]["decompressed_bytes"],
                "raw_repeats": [
                    {
                        "repetition": record["repetition"],
                        "read_decompress_seconds": record["read_decompress_seconds"],
                        "json_decode_seconds": record["json_decode_seconds"],
                        "combined_seconds": record["combined_seconds"],
                    }
                    for record in group
                ],
                "median_read_decompress_seconds": statistics.median(
                    record["read_decompress_seconds"] for record in group
                ),
                "median_json_decode_seconds": statistics.median(
                    record["json_decode_seconds"] for record in group
                ),
                "median_combined_seconds": statistics.median(
                    record["combined_seconds"] for record in group
                ),
                "measurement_boundary": group[0]["measurement_boundary"],
            }
        )
    if len(output) != 45:
        raise ValueError(f"Expected 45 parsing configurations, found {len(output)}")
    return output


def aggregate_latency(
    records: list[dict[str, Any]], latency_files: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if record["status"] != "completed":
            raise ValueError("Latency aggregation only supports completed retained records")
        raw_path = record["result"]["raw_path"]
        rows = latency_files[raw_path]["rows"]
        key = (record["scenario"], record["version"])
        group = groups.setdefault(
            key,
            {"all": [], "types": defaultdict(list), "windows": defaultdict(list), "repetitions": 0, "timer": []},
        )
        group["repetitions"] += 1
        group["timer"].append(record["result"]["timer_calibration_median_ns"])
        for row in rows:
            value = int(row["latency_ns"])
            group["all"].append(value)
            group["types"][row["event_type"]].append(value)
            if row["window"]:
                group["windows"][row["window"]].append(value)
    output: list[dict[str, Any]] = []
    for (scenario, engine), group in sorted(groups.items()):
        output.append(
            {
                "scenario": scenario,
                "engine": engine,
                "event_count_per_repetition": 10_000,
                "repetitions": group["repetitions"],
                "percentile_convention": "ordinary median; nearest-rank P95/P99",
                "early_late_convention": "first 10% and last 10% by stream position",
                "timer_calibration_median_ns": statistics.median(group["timer"]),
                "all_events": latency_stats(group["all"]),
                "event_types": {
                    name: latency_stats(values) for name, values in sorted(group["types"].items())
                },
                "windows": {
                    name: latency_stats(values) for name, values in sorted(group["windows"].items())
                },
                "histogram": histogram(group["all"]),
            }
        )
    if len(output) != 10:
        raise ValueError(f"Expected 10 latency scenario/engine groups, found {len(output)}")
    return output


def aggregate_memory(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for record in sorted(records, key=lambda item: (item["scenario"], item["version"])):
        result = record["result"]
        output.append(
            {
                "engine": record["version"],
                "scenario": record["scenario"],
                "event_count": record["event_count"],
                "traced_current_bytes": result["traced_current_bytes"],
                "traced_peak_bytes": result["traced_peak_bytes"],
                "active_order_peak": result["active_order_peak"],
                "occupied_price_level_peak": result["occupied_price_level_peak"],
                "post_stream": result["post_stream"],
                "samples": [
                    {"checkpoint": name, **sample}
                    for name, sample in sorted(result["samples"].items())
                ],
                "boundary": result["boundary"],
            }
        )
    return output


def unique(values: Iterable[Any], label: str) -> Any:
    materialized = list(values)
    first = materialized[0]
    if any(value != first for value in materialized[1:]):
        raise ValueError(f"Expected identical liquidation {label}")
    return first


def aggregate_liquidation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["version"], record["ratio_percent"])].append(record)
    output = []
    for (engine, ratio), group in sorted(grouped.items()):
        group.sort(key=lambda item: item["repetition"])
        if len(group) != 5 or any(item["status"] != "completed" for item in group):
            raise ValueError(f"Incomplete liquidation group: {engine}/{ratio}")
        results = [item["result"] for item in group]
        if not all(result["oracle_verified"] for result in results):
            raise ValueError(f"Liquidation oracle failure: {engine}/{ratio}")
        output.append(
            {
                "engine": engine,
                "ratio_percent": ratio,
                "repetitions": 5,
                "raw_construction_seconds": [result["construction_seconds"] for result in results],
                "raw_sale_seconds": [result["liquidation_seconds"] for result in results],
                "median_construction_seconds": statistics.median(
                    result["construction_seconds"] for result in results
                ),
                "median_sale_seconds": statistics.median(
                    result["liquidation_seconds"] for result in results
                ),
                "active_bid_depth_units": unique(
                    (result["active_bid_depth_units"] for result in results), "active depth"
                ),
                "liquidation_quantity_units": unique(
                    (result["liquidation_quantity_units"] for result in results), "quantity"
                ),
                "makers_touched": unique(
                    (result["makers_touched"] for result in results), "makers touched"
                ),
                "price_levels_visited": unique(
                    (result["price_levels_visited"] for result in results), "levels visited"
                ),
                "fill_count": unique((result["fill_count"] for result in results), "fill count"),
                "proceeds_tick_quantity_units": str(
                    unique((result["proceeds_tick_quantity_units"] for result in results), "proceeds")
                ),
                "unfilled_qty_units": unique(
                    (result["unfilled_qty_units"] for result in results), "unfilled quantity"
                ),
                "pre_sale_snapshot_digest": unique(
                    (result["pre_sale_snapshot_digest"] for result in results), "fresh-book digest"
                ),
                "fresh_book_and_oracle_verified": True,
            }
        )
    return output


def aggregate_concentration(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["version"], record["variant"], record["event_count"], record["seed"])].append(
            record
        )
    configurations = []
    for (engine, variant, event_count, seed), group in sorted(grouped.items()):
        group.sort(key=lambda item: item["repetition"])
        if [item["repetition"] for item in group] != [1, 2, 3, 4, 5]:
            raise ValueError("Concentration repetition coverage mismatch")
        completed = [item for item in group if item["status"] == "completed"]
        eligible = len(completed) == 5
        durations = [item["result"]["engine_seconds"] for item in completed]
        median_seconds = median_or_none(durations) if eligible else None
        representative = completed[0]["result"] if completed else None
        configurations.append(
            {
                "engine": engine,
                "variant": variant,
                "event_count": event_count,
                "seed": seed,
                "workload_id": group[0]["workload_id"],
                "raw_repeats": [
                    {
                        "repetition": item["repetition"],
                        "status": item["status"],
                        "engine_seconds": (item.get("result") or {}).get("engine_seconds"),
                    }
                    for item in group
                ],
                "status_counts": nonzero_status_counts(group),
                "five_repeat_complete": eligible,
                "median_engine_seconds": median_seconds,
                "throughput_events_per_second": event_count / median_seconds if median_seconds else None,
                "occupied_price_level_peak": (
                    representative["occupied_price_level_peak"] if representative else None
                ),
                "maximum_fifo_length": representative["maximum_fifo_length"] if representative else None,
                "censoring_label": None if eligible else "incomplete_after_processing_timeout",
            }
        )
    comparisons = []
    lookup = {
        (item["engine"], item["event_count"], item["seed"], item["variant"]): item
        for item in configurations
    }
    for engine, event_count, seed in sorted(
        {(item["engine"], item["event_count"], item["seed"]) for item in configurations}
    ):
        original = lookup[(engine, event_count, seed, "original")]
        paired = lookup[(engine, event_count, seed, "levels4_paired")]
        if original["five_repeat_complete"] and paired["five_repeat_complete"]:
            comparisons.append(
                {
                    "engine": engine,
                    "event_count": event_count,
                    "seed": seed,
                    "original_median_seconds": original["median_engine_seconds"],
                    "four_level_median_seconds": paired["median_engine_seconds"],
                    "four_level_over_original_runtime_ratio": paired["median_engine_seconds"]
                    / original["median_engine_seconds"],
                    "original_over_four_level_speedup": original["median_engine_seconds"]
                    / paired["median_engine_seconds"],
                }
            )
    return configurations, comparisons


def aggregate_diagnostics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for record in sorted(records, key=lambda item: (item["scenario"], item["version"])):
        result = record["result"]
        output.append(
            {
                "engine": record["version"],
                "scenario": record["scenario"],
                "event_count": record["event_count"],
                "diagnostic_seconds": result["diagnostic_seconds"],
                "active_order_peak": result["active_order_peak"],
                "occupied_price_level_peak": result["occupied_price_level_peak"],
                "maximum_fifo_length": result["maximum_fifo_length"],
                "operation_counts": result["operation_counts"],
                "operation_count_semantics": result["operation_count_semantics"],
                "uninstrumented_equivalence_verified": result[
                    "uninstrumented_equivalence_verified"
                ],
                "timing_role": "instrumented diagnostic only; not primary timing",
            }
        )
    return output


def build_output(manifest: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    primary, speedups = aggregate_primary(sources["warmed"])
    latency = aggregate_latency(sources["stage4e"]["latency"], sources["latency_files"])
    concentration, concentration_comparisons = aggregate_concentration(
        sources["stage4e"]["concentration"]
    )
    return {
        "schema_version": 1,
        "deterministic": True,
        "source_manifest": {
            "path": "07_results/results_manifest.json",
            "sha256": sha256_bytes(MANIFEST_PATH.read_bytes()),
            "schema_version": manifest["schema_version"],
        },
        "calculation_definitions": {
            "primary_timing_source": "07_results/stage4e/warmed_primary.jsonl",
            "supplementary_cold_source": "07_results/raw/timing.jsonl",
            "pilot_excluded_from_statistics": True,
            "median": "Python statistics.median over exactly five completed raw repeats",
            "throughput": "event_count / median_engine_seconds",
            "speedup": "baseline_median_seconds / optimized_median_seconds; only when both have five completed repeats",
            "censoring": "no median, throughput, or speedup when any planned repeat timed out or was skipped",
            "controller_invocation_wall_cost": "median controller_wall_seconds over five completed warmed-primary repeats; includes process startup, preparation, warm-up, communication, engine replay, and cleanup; not pure parsing-plus-engine time",
            "parsing": "separate warmed-cache filesystem/gzip read-decompression and preloaded JSONL decoding; five repeats per core workload; no engine import or replay",
            "latency_percentiles": "ordinary median; nearest-rank P95/P99 over retained per-event observations",
            "latency_windows": "first 10% and last 10% by event-stream position",
            "memory": "tracemalloc Python allocations; not process RSS",
        },
        "evidence_counts": {
            "pilot": {"records": len(sources["pilot"]), "excluded": True},
            "cold_primary": {
                "records": len(sources["cold"]),
                "role": "supplementary cold-process evidence",
                "status_counts": nonzero_status_counts(sources["cold"]),
            },
            "warmed_primary": {
                "records": len(sources["warmed"]),
                "role": "main instructor-compliant primary timing evidence",
                "status_counts": nonzero_status_counts(sources["warmed"]),
                "complete_configurations": sum(item["five_repeat_complete"] for item in primary),
                "censored_configurations": sum(not item["five_repeat_complete"] for item in primary),
                "valid_speedups": len(speedups),
            },
            "stage4e": {
                "records": sum(len(records) for records in sources["stage4e"].values()),
                "status_counts": nonzero_status_counts(
                    record for records in sources["stage4e"].values() for record in records
                ),
                "latency_artifacts": len(sources["latency_files"]),
            },
            "parsing": {
                "records": len(sources["parsing"]),
                "configurations": len(
                    {
                        (record["scenario"], record["event_count"], record["seed"])
                        for record in sources["parsing"]
                    }
                ),
                "status_counts": nonzero_status_counts(sources["parsing"]),
                "engine_import_or_replay": False,
            },
        },
        "correctness_outcomes": [
            {
                "check": "Complete deterministic suite",
                "result": "PASS",
                "evidence": "51 tests; zero failures, errors, or skips",
                "source": "AI_DECISIONS.md DEC-028",
            },
            {
                "check": "Version A regression projection",
                "result": "PASS",
                "evidence": "45 applicable original tests passed",
                "source": "AI_DECISIONS.md DEC-028",
            },
            {
                "check": "Worked example",
                "result": "PASS",
                "evidence": "Both engines matched exact fills, final book, and proceeds",
                "source": "AI_DECISIONS.md DEC-028",
            },
            {
                "check": "Generated differential replay",
                "result": "PASS",
                "evidence": "15 streams / 15,000 events compared after every event",
                "source": "ACTION_LOG.md entry 75",
            },
            {
                "check": "Optimized internal invariants",
                "result": "PASS",
                "evidence": "Four index/FIFO/heap/cleanup tests passed",
                "source": "AI_DECISIONS.md DEC-028",
            },
        ],
        "primary_configurations": primary,
        "primary_speedups": speedups,
        "parsing_configurations": aggregate_parsing(sources["parsing"]),
        "latency_groups": latency,
        "memory_observations": aggregate_memory(sources["stage4e"]["memory"]),
        "liquidation_groups": aggregate_liquidation(sources["stage4e"]["liquidation"]),
        "concentration_configurations": concentration,
        "concentration_comparisons": concentration_comparisons,
        "diagnostic_observations": aggregate_diagnostics(sources["stage4e"]["diagnostics"]),
        "limitations": [
            "Timeout-censored configurations do not have ordinary five-repeat medians, throughput, or speedups.",
            "Per-event clocks perturb latency; instrumented latency is separate from primary timing.",
            "tracemalloc measures traced Python allocations, not total process RSS or native memory.",
            "Four-level price mapping also changes FIFO queue lengths and matching relationships.",
            "Version A diagnostic scan counts are analytical estimates; Version B wrapper/heap counters are directly observed where labelled.",
            "OneDrive, operating-system scheduling, and thermal state were not fully controlled.",
        ],
    }


def resolve_output(argument: str | None) -> Path:
    if argument is None:
        return DEFAULT_OUTPUT
    candidate = Path(argument)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"Output must remain inside the project: {resolved}") from error
    return resolved


def validate_output(output: dict[str, Any]) -> None:
    counts = output["evidence_counts"]
    if counts["warmed_primary"] != {
        "records": 450,
        "role": "main instructor-compliant primary timing evidence",
        "status_counts": {"completed": 392, "skipped_after_timeout": 46, "timed_out": 12},
        "complete_configurations": 78,
        "censored_configurations": 12,
        "valid_speedups": 33,
    }:
        raise ValueError("Unexpected warmed-primary aggregate counts")
    if counts["stage4e"]["records"] != 212:
        raise ValueError("Unexpected Stage 4E aggregate count")
    if len(output["latency_groups"]) != 10:
        raise ValueError("Unexpected latency group count")
    if len(output["parsing_configurations"]) != 45:
        raise ValueError("Unexpected parsing configuration count")
    if len(output["memory_observations"]) != 4:
        raise ValueError("Unexpected memory observation count")
    if len(output["liquidation_groups"]) != 6:
        raise ValueError("Unexpected liquidation group count")
    if len(output["concentration_configurations"]) != 24:
        raise ValueError("Unexpected concentration configuration count")
    if len(output["concentration_comparisons"]) != 9:
        raise ValueError("Unexpected concentration comparison count")
    if len(output["diagnostic_observations"]) != 8:
        raise ValueError("Unexpected diagnostic observation count")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and aggregate retained results without running an engine."
    )
    parser.add_argument(
        "--output",
        help="Output JSON path; relative paths resolve against the caller's current directory.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Recompute and compare with the existing output without writing.",
    )
    args = parser.parse_args()
    output_path = resolve_output(args.output)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = validate_sources(manifest)
    output = build_output(manifest, sources)
    validate_output(output)
    serialized = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.verify_only:
        if not output_path.is_file():
            raise FileNotFoundError(f"Processed output does not exist: {output_path}")
        existing = output_path.read_bytes()
        if existing != serialized:
            raise ValueError(f"Processed output is not reproducible: {output_path}")
        action = "verified"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_bytes(serialized)
        os.replace(temporary, output_path)
        action = "wrote"
    print(
        json.dumps(
            {
                "action": action,
                "output": output_path.as_posix(),
                "bytes": len(serialized),
                "sha256": sha256_bytes(serialized),
                "primary_configurations": len(output["primary_configurations"]),
                "complete_primary_configurations": output["evidence_counts"]["warmed_primary"][
                    "complete_configurations"
                ],
                "censored_primary_configurations": output["evidence_counts"]["warmed_primary"][
                    "censored_configurations"
                ],
                "valid_speedups": len(output["primary_speedups"]),
                "pilot_records_used_in_statistics": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
