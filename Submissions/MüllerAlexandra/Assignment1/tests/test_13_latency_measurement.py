"""Latency instrumentation preserves raw samples and documented breakdowns."""

from __future__ import annotations

from collections.abc import Iterator
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from limit_order_book.measurement import (
    latency_breakdown_ns,
    measure_event_latencies,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = PROJECT_ROOT / "scripts" / "04_benchmark.py"


class FakeBook:
    def __init__(self) -> None:
        self.sequences: list[int] = []

    def process_event(self, event: dict[str, object]) -> dict[str, object]:
        sequence = event["seq"]
        assert isinstance(sequence, int)
        self.sequences.append(sequence)
        return {"status": "accepted"}


def test_event_latencies_use_fresh_warmup_and_measured_books_per_repeat() -> None:
    books: list[FakeBook] = []
    clock_values: Iterator[int] = iter(
        [100, 110, 200, 225, 300, 315, 400, 440]
    )

    def factory() -> FakeBook:
        book = FakeBook()
        books.append(book)
        return book

    records = measure_event_latencies(
        factory,
        [
            {"seq": 1, "type": "LIMIT"},
            {"seq": 2, "type": "CANCEL"},
        ],
        warmups=2,
        repeats=2,
        clock_ns=lambda: next(clock_values),
    )

    assert len(books) == 4
    assert [book.sequences for book in books] == [[1, 2]] * 4
    assert records == [
        {
            "repeat": 1,
            "event_index": 1,
            "event_type": "LIMIT",
            "latency_ns": 10,
        },
        {
            "repeat": 1,
            "event_index": 2,
            "event_type": "CANCEL",
            "latency_ns": 25,
        },
        {
            "repeat": 2,
            "event_index": 1,
            "event_type": "LIMIT",
            "latency_ns": 15,
        },
        {
            "repeat": 2,
            "event_index": 2,
            "event_type": "CANCEL",
            "latency_ns": 40,
        },
    ]


def test_latency_measurement_rejects_empty_input_or_negative_clock() -> None:
    with pytest.raises(ValueError):
        measure_event_latencies(FakeBook, [])

    clock_values: Iterator[int] = iter([10, 9])
    with pytest.raises(ValueError):
        measure_event_latencies(
            FakeBook,
            [{"seq": 1, "type": "LIMIT"}],
            warmups=0,
            repeats=1,
            clock_ns=lambda: next(clock_values),
        )


@pytest.mark.parametrize(
    ("warmups", "repeats"),
    [(-1, 1), (True, 1), (1.0, 1), (0, 0), (0, -1), (0, True), (0, 1.0)],
)
def test_latency_run_configuration_must_be_valid(
    warmups: object, repeats: object
) -> None:
    with pytest.raises(ValueError):
        measure_event_latencies(
            FakeBook,
            [{"seq": 1, "type": "LIMIT"}],
            warmups=warmups,
            repeats=repeats,
        )


def test_latency_breakdown_reports_overall_type_and_ten_percent_windows() -> None:
    records = [
        {
            "repeat": 1,
            "event_index": index,
            "event_type": "LIMIT" if index % 2 else "CANCEL",
            "latency_ns": index,
        }
        for index in range(1, 12)
    ]

    assert latency_breakdown_ns(records) == {
        "overall": {
            "sample_count": 11,
            "median_ns": 6,
            "p95_ns": 11,
            "p99_ns": 11,
        },
        "by_event_type": {
            "CANCEL": {
                "sample_count": 5,
                "median_ns": 6,
                "p95_ns": 10,
                "p99_ns": 10,
            },
            "LIMIT": {
                "sample_count": 6,
                "median_ns": 6.0,
                "p95_ns": 11,
                "p99_ns": 11,
            },
        },
        "early_10_percent": {
            "sample_count": 2,
            "median_ns": 1.5,
            "p95_ns": 2,
            "p99_ns": 2,
        },
        "late_10_percent": {
            "sample_count": 2,
            "median_ns": 10.5,
            "p95_ns": 11,
            "p99_ns": 11,
        },
        "repeat_count": 1,
        "window_size_per_repeat": 2,
    }


def test_latency_breakdown_rejects_empty_records() -> None:
    with pytest.raises(ValueError):
        latency_breakdown_ns([])


@pytest.mark.parametrize(
    "record",
    [
        {"repeat": 1, "event_index": 1, "event_type": "", "latency_ns": 1},
        {"repeat": 1, "event_index": 1, "event_type": "LIMIT", "latency_ns": -1},
        {"repeat": 1, "event_index": 1, "event_type": "LIMIT", "latency_ns": True},
    ],
)
def test_latency_breakdown_rejects_malformed_records(
    record: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        latency_breakdown_ns([record])


def test_latency_windows_are_selected_within_each_repeat() -> None:
    records = [
        {
            "repeat": repeat,
            "event_index": index,
            "event_type": "LIMIT",
            "latency_ns": offset + index,
        }
        for repeat, offset in ((1, 0), (2, 100))
        for index in range(1, 12)
    ]

    summary = latency_breakdown_ns(records)

    assert summary["repeat_count"] == 2
    assert summary["window_size_per_repeat"] == 2
    assert summary["early_10_percent"]["sample_count"] == 4
    assert summary["late_10_percent"]["sample_count"] == 4
    assert summary["early_10_percent"]["median_ns"] == 51.5
    assert summary["late_10_percent"]["median_ns"] == 60.5


def benchmark_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def test_latency_cli_writes_distinct_raw_and_summary_output(tmp_path: Path) -> None:
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
    output = tmp_path / "latency.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK_SCRIPT),
            "--phase",
            "latency",
            "--version",
            "baseline",
            "--input",
            str(source),
            "--max-events",
            "2",
            "--warmups",
            "0",
            "--repeats",
            "2",
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
    assert document["phase"] == "latency"
    assert document["settings"] == {
        "clock": "time.perf_counter_ns",
        "warmups": 0,
        "repeats": 2,
        "window_fraction": 0.1,
    }
    assert len(document["records"]) == 4
    assert [record["repeat"] for record in document["records"]] == [1, 1, 2, 2]
    assert [record["event_index"] for record in document["records"]] == [1, 2, 1, 2]
    assert all(record["latency_ns"] >= 0 for record in document["records"])
    assert document["summary"]["repeat_count"] == 2
    assert document["summary"]["overall"]["sample_count"] == 4
    assert document["summary"]["by_event_type"]["CANCEL"]["sample_count"] == 4
