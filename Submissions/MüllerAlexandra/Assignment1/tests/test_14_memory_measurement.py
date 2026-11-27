"""Memory measurement has explicit inclusion boundaries and growth samples."""

from __future__ import annotations

from collections.abc import Iterator
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from limit_order_book.memory_measurement import (
    measurement_checkpoint_indices,
    measure_memory_replay,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_SCRIPT = PROJECT_ROOT / "scripts" / "05_measure_memory.py"


class FakeBook:
    def __init__(self) -> None:
        self.sequences: list[int] = []

    def process_event(self, event: dict[str, object]) -> dict[str, object]:
        sequence = event["seq"]
        assert isinstance(sequence, int)
        self.sequences.append(sequence)
        return {"sequence": sequence}

    def inspect_book(self) -> list[dict[str, object]]:
        return [
            {
                "order_id": f"o{sequence}",
                "side": "BUY",
                "price_ticks": 100 + sequence % 2,
                "qty_units": 1,
                "seq": sequence,
            }
            for sequence in self.sequences
        ]


class FakeTracer:
    def __init__(self, samples: list[tuple[int, int]]) -> None:
        self.samples: Iterator[tuple[int, int]] = iter(samples)
        self.started = False
        self.stopped = False

    def start(self) -> None:
        assert not self.started
        self.started = True

    def get_traced_memory(self) -> tuple[int, int]:
        assert self.started and not self.stopped
        return next(self.samples)

    def stop(self) -> None:
        assert self.started
        self.stopped = True


def test_checkpoint_indices_include_start_end_and_evenly_spaced_growth() -> None:
    assert measurement_checkpoint_indices(11, checkpoint_count=5) == (1, 3, 6, 9, 11)
    assert measurement_checkpoint_indices(2, checkpoint_count=10) == (1, 2)
    assert measurement_checkpoint_indices(1, checkpoint_count=1) == (1,)


@pytest.mark.parametrize(
    ("mode", "retained_output_count"),
    [("memory_state", 0), ("memory_retained_output", 5)],
)
def test_memory_replay_records_growth_and_explicit_boundaries(
    mode: str, retained_output_count: int
) -> None:
    tracer = FakeTracer([(10, 20), (30, 40), (50, 60)])

    result = measure_memory_replay(
        FakeBook,
        tuple({"seq": sequence} for sequence in range(1, 6)),
        mode=mode,
        checkpoint_count=3,
        trace_start=tracer.start,
        trace_get=tracer.get_traced_memory,
        trace_stop=tracer.stop,
    )

    assert tracer.started and tracer.stopped
    assert result == {
        "mode": mode,
        "event_count": 5,
        "checkpoints": [
            {"event_index": 1, "current_bytes": 10, "peak_bytes": 20},
            {"event_index": 3, "current_bytes": 30, "peak_bytes": 40},
            {"event_index": 5, "current_bytes": 50, "peak_bytes": 60},
        ],
        "final": {
            "current_bytes": 50,
            "peak_bytes": 60,
            "active_orders": 5,
            "occupied_price_levels": 2,
            "retained_output_count": retained_output_count,
        },
        "inclusions": {
            "preloaded_input": False,
            "book_construction": True,
            "live_book_state": True,
            "temporary_matching_allocations": True,
            "current_event_result": True,
            "complete_result_history": mode == "memory_retained_output",
            "checkpoint_bookkeeping": True,
            "final_book_inspection": False,
            "python_tracemalloc_only": True,
        },
    }


@pytest.mark.parametrize(
    ("events", "mode", "checkpoint_count"),
    [([], "memory_state", 1), ([{"seq": 1}], "unknown", 1), ([{"seq": 1}], "memory_state", 0)],
)
def test_memory_replay_rejects_invalid_configuration(
    events: list[dict[str, object]], mode: str, checkpoint_count: int
) -> None:
    with pytest.raises(ValueError):
        measure_memory_replay(
            FakeBook,
            events,
            mode=mode,
            checkpoint_count=checkpoint_count,
        )


def test_memory_replay_stops_tracing_when_processing_fails() -> None:
    tracer = FakeTracer([])

    class FailingBook(FakeBook):
        def process_event(self, event: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("deliberate failure")

    with pytest.raises(RuntimeError, match="deliberate failure"):
        measure_memory_replay(
            FailingBook,
            [{"seq": 1}],
            mode="memory_state",
            trace_start=tracer.start,
            trace_get=tracer.get_traced_memory,
            trace_stop=tracer.stop,
        )

    assert tracer.stopped


def benchmark_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def test_memory_cli_saves_state_mode_without_tracing_input_parsing(
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
    output = tmp_path / "memory.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(MEMORY_SCRIPT),
            "--version",
            "baseline",
            "--mode",
            "memory_state",
            "--input",
            str(source),
            "--max-events",
            "2",
            "--checkpoints",
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
    assert document["schema_version"] == 1
    assert document["phase"] == "memory_state"
    assert document["version"] == "baseline"
    assert document["input"]["event_count"] == 2
    assert document["input"]["parse_seconds"] >= 0
    assert document["settings"] == {"checkpoint_count": 2}
    assert document["measurement"]["event_count"] == 2
    assert document["measurement"]["final"]["active_orders"] == 0
    assert document["measurement"]["final"]["occupied_price_levels"] == 0
    assert document["measurement"]["final"]["retained_output_count"] == 0
    assert document["measurement"]["inclusions"]["preloaded_input"] is False
    assert document["environment"]["python_version"]
