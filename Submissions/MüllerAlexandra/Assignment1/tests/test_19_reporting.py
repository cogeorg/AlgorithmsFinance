"""Saved-result aggregation is complete, paired, and non-fabricating."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from limit_order_book.reporting import collect_dashboard_data, write_dashboard_data


def write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def write_gzip_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream)


def add_throughput_task(
    root: Path,
    *,
    version: str,
    scenario: str,
    outcome: str,
    throughput: float | None,
) -> None:
    stem = f"{scenario}_1000_seed42_levels1000"
    result_relative = f"results/raw/{version}/throughput/{stem}.json.gz"
    status = {
        "task": {
            "task_id": f"{version}_throughput_{stem}",
            "version": version,
            "phase": "throughput",
            "scenario": scenario,
            "event_count": 1_000,
            "seed": 42,
            "levels": 1_000,
            "input_path": f"data/generated/{stem}.jsonl.gz",
            "sha256": "a" * 64,
            "result_path": result_relative,
            "status_path": f"results/status/{version}/throughput/{stem}.json",
        },
        "task_id": f"{version}_throughput_{stem}",
        "outcome": outcome,
        "timeout_seconds": 60,
        "result_path": result_relative if outcome == "completed" else None,
        "environment": {
            "python_version": "3.12.10",
            "platform": "Windows",
            "git": {"commit": "abc123", "code_dirty": False},
        },
    }
    write_json(
        root / f"results/status/{version}/throughput/{stem}.json",
        status,
    )
    if outcome == "completed":
        assert throughput is not None
        write_gzip_json(
            root / result_relative,
            {
                "schema_version": 1,
                "version": version,
                "phase": "throughput",
                "input": {
                    "sha256": "a" * 64,
                    "event_count": 1_000,
                    "parse_seconds": 0.5,
                },
                "settings": {"warmups": 1, "repeats": 2},
                "records": [
                    {
                        "repeat": 1,
                        "event_count": 1_000,
                        "construction_seconds": 0.01,
                        "replay_seconds": 10.0,
                        "total_engine_seconds": 10.01,
                        "throughput_events_per_second": throughput - 1,
                    },
                    {
                        "repeat": 2,
                        "event_count": 1_000,
                        "construction_seconds": 0.02,
                        "replay_seconds": 9.0,
                        "total_engine_seconds": 9.02,
                        "throughput_events_per_second": throughput + 1,
                    },
                ],
                "summary": {
                    "repeat_count": 2,
                    "median_construction_seconds": 0.015,
                    "median_replay_seconds": 9.5,
                    "median_total_engine_seconds": 9.515,
                    "median_throughput_events_per_second": throughput,
                },
                "environment": status["environment"],
            },
        )


def test_dashboard_data_preserves_statuses_raw_repeats_and_matched_speedup(
    tmp_path: Path,
) -> None:
    add_throughput_task(
        tmp_path,
        version="baseline",
        scenario="buildup",
        outcome="completed",
        throughput=100.0,
    )
    add_throughput_task(
        tmp_path,
        version="revised",
        scenario="buildup",
        outcome="completed",
        throughput=250.0,
    )
    add_throughput_task(
        tmp_path,
        version="baseline",
        scenario="mixed",
        outcome="stopped_timeout",
        throughput=None,
    )
    add_throughput_task(
        tmp_path,
        version="revised",
        scenario="mixed",
        outcome="completed",
        throughput=300.0,
    )

    data = collect_dashboard_data(tmp_path / "results")

    assert len(data["statuses"]) == 4
    assert len(data["throughput_repeats"]) == 6
    assert len(data["throughput_summaries"]) == 3
    assert data["status_counts"] == {
        "baseline": {"completed": 1, "stopped_timeout": 1},
        "revised": {"completed": 2},
    }
    assert data["throughput_comparisons"] == [
        {
            "experiment_group": "formal",
            "scenario": "buildup",
            "event_count": 1_000,
            "seed": 42,
            "levels": 1_000,
            "baseline_events_per_second": 100.0,
            "revised_events_per_second": 250.0,
            "speedup_revised_over_baseline": 2.5,
        }
    ]


def test_dashboard_writer_is_gzip_json_and_refuses_overwrite(tmp_path: Path) -> None:
    results = tmp_path / "results"
    add_throughput_task(
        tmp_path,
        version="baseline",
        scenario="buildup",
        outcome="completed",
        throughput=100.0,
    )
    output = tmp_path / "summary" / "dashboard.json.gz"

    write_dashboard_data(results, output)

    with gzip.open(output, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    assert document["schema_version"] == 1
    assert document["throughput_summaries"][0]["version"] == "baseline"
    with pytest.raises(FileExistsError):
        write_dashboard_data(results, output)
