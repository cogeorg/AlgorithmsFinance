"""Benchmark harness preserves raw evidence and explicit measurement boundaries."""

from __future__ import annotations

from collections.abc import Iterator
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from limit_order_book.benchmarking import (
    load_event_batch,
    summarize_throughput_records,
    write_json_exclusive,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = PROJECT_ROOT / "scripts" / "04_benchmark.py"


def test_event_batch_records_separate_parsing_metadata_and_limit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "events.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "event_id": "e1",
                        "type": "CANCEL",
                        "target_order_id": "x",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "event_id": "e2",
                        "type": "CANCEL",
                        "target_order_id": "y",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    clock_values: Iterator[float] = iter([10.0, 11.5])

    events, metadata = load_event_batch(
        source,
        max_events=1,
        clock=lambda: next(clock_values),
    )

    assert events == (
        {"seq": 1, "event_id": "e1", "type": "CANCEL", "target_order_id": "x"},
    )
    assert metadata == {
        "path": str(source.resolve()),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "compressed_bytes": source.stat().st_size,
        "event_count": 1,
        "max_events": 1,
        "parse_seconds": 1.5,
    }
    assert len(metadata["sha256"]) == 64


@pytest.mark.parametrize("max_events", [0, -1, True])
def test_event_limit_must_be_a_positive_integer(max_events: object) -> None:
    with pytest.raises(ValueError):
        load_event_batch(Path("unused.jsonl"), max_events=max_events)


def test_throughput_summary_keeps_medians_separate() -> None:
    records = [
        {
            "repeat": 1,
            "event_count": 10,
            "construction_seconds": 0.3,
            "replay_seconds": 3.0,
            "total_engine_seconds": 3.3,
            "throughput_events_per_second": 10 / 3,
        },
        {
            "repeat": 2,
            "event_count": 10,
            "construction_seconds": 0.1,
            "replay_seconds": 1.0,
            "total_engine_seconds": 1.1,
            "throughput_events_per_second": 10.0,
        },
        {
            "repeat": 3,
            "event_count": 10,
            "construction_seconds": 0.2,
            "replay_seconds": 2.0,
            "total_engine_seconds": 2.2,
            "throughput_events_per_second": 5.0,
        },
    ]

    assert summarize_throughput_records(records) == {
        "repeat_count": 3,
        "median_construction_seconds": 0.2,
        "median_replay_seconds": 2.0,
        "median_total_engine_seconds": 2.2,
        "median_throughput_events_per_second": 5.0,
    }


def test_summary_rejects_empty_or_inconsistent_records() -> None:
    with pytest.raises(ValueError):
        summarize_throughput_records([])
    with pytest.raises(ValueError):
        summarize_throughput_records(
            [
                {
                    "repeat": 1,
                    "event_count": 1,
                    "construction_seconds": 0.1,
                    "replay_seconds": 0.2,
                    "total_engine_seconds": 0.3,
                    "throughput_events_per_second": 5.0,
                },
                {
                    "repeat": 2,
                    "event_count": 2,
                    "construction_seconds": 0.1,
                    "replay_seconds": 0.2,
                    "total_engine_seconds": 0.3,
                    "throughput_events_per_second": 10.0,
                },
            ]
        )


def test_json_writer_creates_parent_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "result.json"
    payload = {"schema_version": 1, "records": [{"repeat": 1}]}

    write_json_exclusive(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    with pytest.raises(FileExistsError):
        write_json_exclusive(output, {"different": True})


def test_json_writer_compresses_gzip_output_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "nested" / "result.json.gz"
    payload = {"schema_version": 1, "records": [{"event_index": 1}]}

    write_json_exclusive(output, payload)

    with gzip.open(output, "rt", encoding="utf-8") as stream:
        assert json.load(stream) == payload
    with pytest.raises(FileExistsError):
        write_json_exclusive(output, {"different": True})


def benchmark_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def test_benchmark_cli_documents_required_options() -> None:
    completed = subprocess.run(
        [sys.executable, str(BENCHMARK_SCRIPT), "--help"],
        cwd=PROJECT_ROOT,
        env=benchmark_environment(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    for option in (
        "--version",
        "--input",
        "--max-events",
        "--warmups",
        "--repeats",
        "--out",
    ):
        assert option in completed.stdout


def test_benchmark_cli_writes_one_smoke_result_document(tmp_path: Path) -> None:
    source = tmp_path / "events.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "event_id": "e1",
                        "type": "CANCEL",
                        "target_order_id": "x",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "event_id": "e2",
                        "type": "CANCEL",
                        "target_order_id": "y",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "results" / "smoke.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK_SCRIPT),
            "--version",
            "baseline",
            "--input",
            str(source),
            "--max-events",
            "2",
            "--warmups",
            "0",
            "--repeats",
            "1",
            "--out",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=benchmark_environment(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["phase"] == "throughput"
    assert document["version"] == "baseline"
    assert document["input"]["event_count"] == 2
    assert document["input"]["max_events"] == 2
    assert document["input"]["parse_seconds"] >= 0
    assert len(document["input"]["sha256"]) == 64
    assert document["settings"] == {"warmups": 0, "repeats": 1}
    assert len(document["records"]) == 1
    assert document["summary"]["repeat_count"] == 1
    assert document["environment"]["python_version"]
    assert document["environment"]["platform"]
    assert "assignment_dirty" in document["environment"]["git"]
    assert "code_dirty" in document["environment"]["git"]
    assert document["created_utc"].endswith("+00:00")
    assert document["command"]
