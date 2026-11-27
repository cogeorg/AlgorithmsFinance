"""Pure data-loading helpers for the Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_results(path: Path) -> dict[str, Any]:
    """Load and minimally validate one saved benchmark result file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"environment", "settings", "definitions", "records"}
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"result file is missing keys: {sorted(missing)}")
    if not isinstance(payload["records"], list):
        raise ValueError("result records must be a list")
    return payload


def filter_records(
    records: list[dict[str, Any]],
    *,
    q: int,
    scenario: str,
    duplicate_policy: str,
) -> list[dict[str, Any]]:
    """Select comparable records while retaining every input size and method."""
    return [
        record
        for record in records
        if record["q"] == q
        and record["scenario"] == scenario
        and record["duplicate_policy"] == duplicate_policy
    ]


def timing_rows(
    records: list[dict[str, Any]], metric: str
) -> list[dict[str, Any]]:
    """Flatten one median timing metric and convert seconds to milliseconds."""
    if metric not in {"preparation", "query_batch", "total"}:
        raise ValueError(f"unknown timing metric: {metric}")
    return [
        {
            "n": record["n"],
            "method/version": record["label"],
            "elapsed (ms)": record["median_seconds"][metric] * 1_000,
        }
        for record in records
    ]


def memory_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten traced-memory readings and convert bytes to KiB."""
    return [
        {
            "n": record["n"],
            "q": record["q"],
            "method/version": record["label"],
            "current traced (KiB)": record["tracemalloc"]["current_bytes"] / 1_024,
            "peak traced (KiB)": record["tracemalloc"]["peak_bytes"] / 1_024,
        }
        for record in records
    ]


def raw_repeat_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one row per method, input size, and raw timing repeat."""
    rows: list[dict[str, Any]] = []
    for record in records:
        raw = record["raw_seconds"]
        repeat_count = len(raw["total"])
        for repeat_index in range(repeat_count):
            rows.append(
                {
                    "n": record["n"],
                    "method/version": record["label"],
                    "repeat": repeat_index + 1,
                    "preparation (ms)": raw["preparation"][repeat_index] * 1_000,
                    "query batch (ms)": raw["query_batch"][repeat_index] * 1_000,
                    "total (ms)": raw["total"][repeat_index] * 1_000,
                    "seed": record["seed"],
                    "preparation loops": record["batching_loops"]["preparation"],
                    "query loops": record["batching_loops"]["query_batch"],
                    "total loops": record["batching_loops"]["total"],
                }
            )
    return rows
