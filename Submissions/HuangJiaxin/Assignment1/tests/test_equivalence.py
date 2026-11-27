"""Version A and version B must agree after EVERY event: same result (including the
ordered fills) and the same canonical book. Agreement is extra evidence; it does not
replace the hand-calculated tests above."""
from pathlib import Path

import pytest

from conftest import OrderBookA, OrderBookB
from lob.events_io import read_events
from random_streams import random_stream

DATA = Path(__file__).resolve().parents[1] / "data" / "supplied"
SAMPLES = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]


@pytest.mark.parametrize("seed", range(30))
def test_versions_agree_on_random_streams(seed):
    a, b = OrderBookA(), OrderBookB()
    for i, event in enumerate(random_stream(seed, n_events=400)):
        assert a.process(event) == b.process(event), f"event {i}"
        assert a.snapshot() == b.snapshot(), f"book after event {i}"


@pytest.mark.parametrize("sample", SAMPLES)
def test_versions_agree_on_supplied_samples(sample):
    """10,000 events each: every result compared; full books compared every 250 events."""
    a, b = OrderBookA(), OrderBookB()
    events = read_events(DATA / f"{sample}_10000.jsonl.gz")
    for i, event in enumerate(events):
        assert a.process(event) == b.process(event), f"{sample}: event {i}"
        if i % 250 == 0 or i == len(events) - 1:
            assert a.snapshot() == b.snapshot(), f"{sample}: book after event {i}"
