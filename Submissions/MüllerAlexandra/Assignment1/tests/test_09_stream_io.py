"""Supplied plain and gzip JSON Lines files must replay in stored sequence order."""

from pathlib import Path

from limit_order_book.interface import OrderBook
from limit_order_book.stream_io import iter_events, replay_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data" / "supplied"


def test_plain_worked_stream_is_loaded_in_order() -> None:
    events = list(iter_events(DATA / "worked_example.jsonl"))

    assert len(events) == 6
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5, 6]
    assert events[0]["order_id"] == "b1"
    assert events[-1]["order_id"] == "s1"


def test_gzip_stream_is_loaded_in_order() -> None:
    events = list(iter_events(DATA / "cancel_churn_10000.jsonl.gz"))

    assert len(events) == 10_000
    assert events[0]["seq"] == 1
    assert events[-1]["seq"] == 10_000


def test_replay_returns_one_result_per_event(book: OrderBook) -> None:
    events = list(iter_events(DATA / "worked_example.jsonl"))

    results = replay_events(book, events)

    assert len(results) == len(events)
    assert results[-1]["event_id"] == "event6"

