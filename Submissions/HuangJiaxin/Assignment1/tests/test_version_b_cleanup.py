"""Version B specific: lazy cancellation must stay correct, and compaction must keep
stale entries bounded when many orders are cancelled (added with version B; no earlier
test was changed)."""
from pathlib import Path

import pytest

from conftest import OrderBookA, OrderBookB
from lob.events_io import read_events
from random_streams import random_stream

DATA = Path(__file__).resolve().parents[1] / "data" / "supplied"


@pytest.mark.parametrize("seed", range(10))
def test_version_b_without_compaction_is_still_correct(seed):
    a, b = OrderBookA(), OrderBookB(compact=False)
    for event in random_stream(seed, n_events=400):
        assert a.process(event) == b.process(event)
        assert a.snapshot() == b.snapshot()


def test_compaction_bounds_stale_entries_under_cancel_churn():
    events = read_events(DATA / "cancel_churn_10000.jsonl.gz")
    compact, lazy = OrderBookB(), OrderBookB(compact=False)
    for e in events:
        assert compact.process(e) == lazy.process(e)
    assert compact.active_order_count() == lazy.active_order_count() == 0
    in_deques, in_heaps = compact.stale_entries()
    assert in_deques == 0 and in_heaps <= 16            # bounded by the compaction rule
    assert lazy.stale_entries()[1] >= 4000              # without it, the heap keeps growing


def test_deque_compaction_after_many_cancels_at_one_price():
    b = OrderBookB()
    seq = 0
    for i in range(1000):
        seq += 1
        b.process({"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": f"o{i}",
                   "side": "BUY", "price_ticks": 100, "qty_units": 1})
    for i in range(999):                                 # cancel all but the last order
        seq += 1
        b.process({"seq": seq, "event_id": f"e{seq}", "type": "CANCEL", "target_order_id": f"o{i}"})
    assert b.active_order_count() == 1
    assert len(b.levels["BUY"][100]) <= 2 * 1 + 8        # deque was rebuilt
    assert b.snapshot()["bids"][0]["order_id"] == "o999"
