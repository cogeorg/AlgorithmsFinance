import json
from pathlib import Path

import pytest

from orderbook.baseline import OrderBook as BaselineOrderBook
from orderbook.revised import OrderBook as RevisedOrderBook
from generate_spec_streams import EVENTS_PER_STREAM, SEEDS, generate_event_stream


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _read_stream(seed):
    path = FIXTURE_DIR / f"generated_seed_{seed}.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_stream_fixture_matches_its_seeded_generator(seed):
    events = _read_stream(seed)

    assert events == generate_event_stream(seed)
    assert len(events) == EVENTS_PER_STREAM
    assert [event["seq"] for event in events] == list(
        range(1, EVENTS_PER_STREAM + 1)
    )
    assert len({event["event_id"] for event in events}) == EVENTS_PER_STREAM

    submission_ids = [
        event["order_id"]
        for event in events
        if event["type"] in ("LIMIT", "MARKET_SELL")
    ]
    assert len(submission_ids) == len(set(submission_ids))
    assert {event["type"] for event in events} == {
        "LIMIT",
        "MARKET_SELL",
        "CANCEL",
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_stream_versions_match_after_each_event(seed):
    baseline = BaselineOrderBook()
    revised = RevisedOrderBook()
    observations = []

    for event in _read_stream(seed):
        baseline_result = baseline.process_event(event)
        revised_result = revised.process_event(event)
        assert revised_result == baseline_result
        assert revised.last_accepted_seq == baseline.last_accepted_seq
        assert revised.inspect_book() == baseline.inspect_book()
        observations.append(
            (revised_result, revised.inspect_book(), revised.last_accepted_seq)
        )

    assert len(observations) == EVENTS_PER_STREAM
