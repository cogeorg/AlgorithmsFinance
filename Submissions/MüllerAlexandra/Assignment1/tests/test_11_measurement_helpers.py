"""Measurement helpers have deterministic arithmetic and fresh-state rules."""

from collections.abc import Iterator

import pytest

from limit_order_book.measurement import (
    latency_summary_ns,
    measure_throughput_repeats,
    nearest_rank_percentile,
    throughput_events_per_second,
)


class FakeBook:
    """Minimal stateful book that records which sequence numbers it receives."""

    def __init__(self) -> None:
        self.sequences: list[int] = []

    def process_event(self, event: dict[str, object]) -> dict[str, object]:
        sequence = event["seq"]
        assert isinstance(sequence, int)
        self.sequences.append(sequence)
        return {"status": "accepted"}


def test_nearest_rank_percentile_uses_documented_convention() -> None:
    samples = list(range(100, 0, -1))

    assert nearest_rank_percentile(samples, 50) == 50
    assert nearest_rank_percentile(samples, 95) == 95
    assert nearest_rank_percentile(samples, 99) == 99
    assert nearest_rank_percentile(samples, 100) == 100


@pytest.mark.parametrize(("samples", "percentile"), [([], 95), ([1], 0), ([1], 101)])
def test_nearest_rank_percentile_rejects_undefined_requests(
    samples: list[int], percentile: float
) -> None:
    with pytest.raises(ValueError):
        nearest_rank_percentile(samples, percentile)


def test_latency_summary_reports_count_median_p95_and_p99() -> None:
    assert latency_summary_ns([5, 1, 3, 2, 4]) == {
        "sample_count": 5,
        "median_ns": 3,
        "p95_ns": 5,
        "p99_ns": 5,
    }


def test_throughput_uses_events_divided_by_seconds() -> None:
    assert throughput_events_per_second(10_000, 2.5) == 4_000


@pytest.mark.parametrize(
    ("event_count", "elapsed_seconds"),
    [(0, 1.0), (-1, 1.0), (1, 0.0), (1, -1.0)],
)
def test_throughput_rejects_nonpositive_inputs(
    event_count: int, elapsed_seconds: float
) -> None:
    with pytest.raises(ValueError):
        throughput_events_per_second(event_count, elapsed_seconds)


def test_repeats_use_fresh_books_and_keep_each_raw_timing() -> None:
    books: list[FakeBook] = []
    clock_values: Iterator[float] = iter(
        [
            9.0,
            10.0,
            10.0,
            12.0,
            19.0,
            20.0,
            20.0,
            24.0,
        ]
    )

    def factory() -> FakeBook:
        book = FakeBook()
        books.append(book)
        return book

    records = measure_throughput_repeats(
        factory,
        [{"seq": 1}, {"seq": 2}],
        warmups=1,
        repeats=2,
        clock=lambda: next(clock_values),
    )

    assert len(books) == 3
    assert [book.sequences for book in books] == [[1, 2], [1, 2], [1, 2]]
    assert records == [
        {
            "repeat": 1,
            "event_count": 2,
            "construction_seconds": 1.0,
            "replay_seconds": 2.0,
            "total_engine_seconds": 3.0,
            "throughput_events_per_second": 1.0,
        },
        {
            "repeat": 2,
            "event_count": 2,
            "construction_seconds": 1.0,
            "replay_seconds": 4.0,
            "total_engine_seconds": 5.0,
            "throughput_events_per_second": 0.5,
        },
    ]


@pytest.mark.parametrize(
    ("warmups", "repeats"),
    [(-1, 1), (0, 0), (0, -1)],
)
def test_repeat_configuration_must_be_valid(warmups: int, repeats: int) -> None:
    with pytest.raises(ValueError):
        measure_throughput_repeats(
            FakeBook,
            [{"seq": 1}],
            warmups=warmups,
            repeats=repeats,
            clock=lambda: 0.0,
        )
