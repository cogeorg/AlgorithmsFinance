"""White-box tests of Version B's compaction rules (07_docs/REVISIONS.md).

Expected bounds come from the approved design, not from the implementation:
  - heap: after every event, entries <= 2 * occupied levels + 16 per side
  - deque: after every event, len(queue) <= 2 * live_count per level
            (rebuilt when more than half of its entries are cancelled)
These tests read B internals (levels, Level.queue, live_count, _heaps).
"""

import gzip
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHURN = ROOT / "00_instructions" / "data" / "cancel_churn_10000.jsonl.gz"
BTC = 100_000_000
B_VERSIONS = ["lob_b_sorted", "lob_b_heap"]


def limit(seq, order_id, side, price_ticks, qty_units):
    return {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT",
            "order_id": order_id, "side": side,
            "price_ticks": price_ticks, "qty_units": qty_units}


def cancel(seq, target):
    return {"seq": seq, "event_id": f"e{seq}", "type": "CANCEL",
            "target_order_id": target}


@pytest.mark.source("design rule: heap compaction bound (cancel_churn)")
@pytest.mark.parametrize("lob", ["lob_b_heap"], indirect=True)
def test_heap_stays_bounded_under_cancel_churn(lob):
    """Supplied cancel_churn_10000: 5,000 BUY levels created and emptied.
    Without compaction the bid heap would keep ~5,000 stale keys
    (BUYs never ask for the best BID, so nothing pops them)."""
    with gzip.open(CHURN, "rt", encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh]
    book = lob.OrderBook()
    levels_emptied = 0
    max_heap = 0
    for event in events:
        result = book.process_event(event)
        levels_emptied += result["status"] == "cancelled"
        for side in ("BUY", "SELL"):
            h = len(book._heaps[side])
            p = len(book.levels[side])
            assert h <= 2 * p + 16, (event["seq"], side, h, p)
            max_heap = max(max_heap, h)
    # The workload really exercises accumulation ...
    assert levels_emptied == 5000
    # ... yet the heap never holds more than 2 * 1 + 16 keys (B <= 1).
    assert max_heap <= 18
    assert book.inspect_book() == []
    book.assert_invariants()


@pytest.mark.source("design rule: deque compaction bound (cancels behind FIFO head)")
@pytest.mark.parametrize("lob", B_VERSIONS, indirect=True)
def test_deque_stays_bounded_behind_live_head(lob):
    """A live head order at 60,000; 1,000 times: add an order behind it and
    cancel it. Without compaction the queue would keep 1,000 dead entries."""
    price = 6_000_000
    book = lob.OrderBook()
    book.process_event(limit(1, "head", "BUY", price, 1 * BTC))
    seq = 1
    max_queue = 0
    for i in range(1000):
        seq += 1
        book.process_event(limit(seq, f"x{i}", "BUY", price, 1 * BTC))
        seq += 1
        assert book.process_event(cancel(seq, f"x{i}"))["status"] == "cancelled"
        level = book.levels["BUY"][price]
        assert level.live_count == 1
        assert len(level.queue) <= 2 * level.live_count
        max_queue = max(max_queue, len(level.queue))
    assert max_queue <= 2
    book.assert_invariants()

    # Priority is unchanged: one more order behind the head, then a sale of
    # 2 BTC fills the head first (by hand: head 1 BTC, then late 1 BTC).
    seq += 1
    book.process_event(limit(seq, "late", "BUY", price, 1 * BTC))
    seq += 1
    sale = book.process_event({"seq": seq, "event_id": f"e{seq}",
                               "type": "MARKET_SELL", "order_id": "s1",
                               "qty_units": 2 * BTC})
    assert [(f["maker_id"], f["qty_units"]) for f in sale["fills"]] == [
        ("head", 1 * BTC), ("late", 1 * BTC)]
    assert book.inspect_book() == []
    book.assert_invariants()


@pytest.mark.source("design rule: deque compaction bound (batch cancels)")
@pytest.mark.parametrize("lob", B_VERSIONS, indirect=True)
def test_deque_compaction_keeps_fifo_order(lob):
    """Head + 9 orders behind it; cancel 8 of the 9 (more than half dead,
    so the queue must be rebuilt). The survivors keep arrival order."""
    price = 5_990_000
    book = lob.OrderBook()
    book.process_event(limit(1, "head", "BUY", price, 1 * BTC))
    for i in range(9):
        book.process_event(limit(2 + i, f"y{i}", "BUY", price, 1 * BTC))
    seq = 10
    for i in range(8):                       # cancel y0..y7, keep y8
        seq += 1
        book.process_event(cancel(seq, f"y{i}"))
        level = book.levels["BUY"][price]
        assert len(level.queue) <= 2 * level.live_count
    assert [o["order_id"] for o in book.inspect_book()] == ["head", "y8"]
    assert len(book.levels["BUY"][price].queue) <= 4
    book.assert_invariants()
