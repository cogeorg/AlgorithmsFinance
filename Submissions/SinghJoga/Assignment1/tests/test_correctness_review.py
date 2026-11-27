import gzip
import json
import random
from pathlib import Path

import pytest

from benchmarks.metrics import ceil_percent
from orderbook.baseline import OrderBook as BaselineBook
from orderbook.replay import replay
from orderbook.revised import OrderBook as RevisedBook


ROOT = Path(__file__).resolve().parents[1]
BOOK_TYPES = [BaselineBook, RevisedBook]


def _event(seq, kind, event_id, **fields):
    return {"seq": seq, "type": kind, "event_id": event_id, **fields}


class BruteForceSpecificationBook:
    """Small test-only model; select one eligible maker by scanning each time."""

    def __init__(self):
        self.orders = []
        self.last_seq = None

    @staticmethod
    def _positive_integer(value):
        return type(value) is int and value > 0

    def _reject(self, event, reason):
        result = {"status": "rejected", "reason": reason}
        if isinstance(event, dict) and "event_id" in event:
            result["event_id"] = event["event_id"]
        return result

    def _validate(self, event, kind):
        if not isinstance(event, dict):
            return None, "event must be a mapping"
        for field in ("seq", "event_id", "type"):
            if field not in event:
                return None, f"missing required field: {field}"
        seq = event["seq"]
        if not self._positive_integer(seq):
            return None, "seq must be a positive integer"
        if self.last_seq is not None and seq <= self.last_seq:
            return None, "seq must be strictly increasing"
        if event["type"] != kind:
            return None, f"event type must be {kind}"
        required = {
            "LIMIT": ("order_id", "side", "price_ticks", "qty_units"),
            "MARKET_SELL": ("order_id", "qty_units"),
            "CANCEL": ("target_order_id",),
        }[kind]
        for field in required:
            if field not in event:
                return None, f"missing required field: {field}"
        if kind == "LIMIT":
            if event["side"] not in ("BUY", "SELL"):
                return None, "side must be BUY or SELL"
            if not self._positive_integer(event["price_ticks"]):
                return None, "price_ticks must be a positive integer"
        if kind in ("LIMIT", "MARKET_SELL"):
            if not self._positive_integer(event["qty_units"]):
                return None, "qty_units must be a positive integer"
            for order in self.orders:
                if order["order_id"] == event["order_id"]:
                    return None, "duplicate live submission order_id"
        return event, None

    def process(self, event):
        if not isinstance(event, dict):
            return self._reject(event, "event must be a mapping")
        kind = event.get("type")
        if kind not in ("LIMIT", "MARKET_SELL", "CANCEL"):
            return self._reject(event, "unknown event type")
        data, reason = self._validate(event, kind)
        if reason:
            return self._reject(event, reason)

        if kind == "CANCEL":
            found = None
            for order in self.orders:
                if order["order_id"] == data["target_order_id"]:
                    found = order
                    break
            if found is None:
                result = {
                    "event_id": data["event_id"],
                    "target_order_id": data["target_order_id"],
                    "status": "not_found",
                    "cancelled_qty_units": 0,
                }
            else:
                self.orders.remove(found)
                result = {
                    "event_id": data["event_id"],
                    "target_order_id": data["target_order_id"],
                    "status": "cancelled",
                    "cancelled_qty_units": found["qty_units"],
                }
            self.last_seq = data["seq"]
            return result

        incoming_side = "SELL" if kind == "MARKET_SELL" else data["side"]
        limit_price = None if kind == "MARKET_SELL" else data["price_ticks"]
        remaining = data["qty_units"]
        fills = []
        while remaining:
            maker = None
            for candidate in self.orders:
                if candidate["side"] == incoming_side:
                    continue
                price = candidate["price_ticks"]
                if limit_price is not None:
                    if incoming_side == "BUY" and price > limit_price:
                        continue
                    if incoming_side == "SELL" and price < limit_price:
                        continue
                if maker is None:
                    maker = candidate
                    continue
                better = (
                    price < maker["price_ticks"]
                    if incoming_side == "BUY"
                    else price > maker["price_ticks"]
                )
                if better or (
                    price == maker["price_ticks"]
                    and candidate["seq"] < maker["seq"]
                ):
                    maker = candidate
            if maker is None:
                break
            quantity = min(remaining, maker["qty_units"])
            fills.append(
                {
                    "maker_id": maker["order_id"],
                    "taker_id": data["order_id"],
                    "price_ticks": maker["price_ticks"],
                    "qty_units": quantity,
                }
            )
            maker["qty_units"] -= quantity
            remaining -= quantity
            if maker["qty_units"] == 0:
                self.orders.remove(maker)

        if remaining and kind == "LIMIT":
            self.orders.append(
                {
                    "order_id": data["order_id"],
                    "side": data["side"],
                    "price_ticks": data["price_ticks"],
                    "qty_units": remaining,
                    "seq": data["seq"],
                }
            )
        self.last_seq = data["seq"]
        if kind == "LIMIT":
            status = "filled" if remaining == 0 else "resting"
        elif remaining == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"
        return {
            "event_id": data["event_id"],
            "order_id": data["order_id"],
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def snapshot(self):
        bids = []
        asks = []
        for source in self.orders:
            target = bids if source["side"] == "BUY" else asks
            order = dict(source)
            index = len(target)
            key = (
                (-order["price_ticks"], order["seq"])
                if order["side"] == "BUY"
                else (order["price_ticks"], order["seq"])
            )
            while index and key < (
                (-target[index - 1]["price_ticks"], target[index - 1]["seq"])
                if order["side"] == "BUY"
                else (target[index - 1]["price_ticks"], target[index - 1]["seq"])
            ):
                index -= 1
            target.insert(index, order)
        public = lambda order: {
            "order_id": order["order_id"],
            "side": order["side"],
            "price_ticks": order["price_ticks"],
            "qty_units": order["qty_units"],
            "seq": order["seq"],
        }
        return {
            "bids": [public(order) for order in bids],
            "asks": [public(order) for order in asks],
        }


def _seeded_mixed_events(seed, count=1500):
    rng = random.Random(seed)
    events = []
    known_ids = []
    last_accepted = None
    cycle_added = []
    for index in range(count):
        seq = index + 1
        slot = index % 10
        cycle = index // 10
        if slot == 0:
            order_id = f"z-bid-{seed}-{cycle}"
            cycle_added = [order_id]
            event = _event(
                seq, "LIMIT", f"evt-{index}", order_id=order_id, side="BUY",
                price_ticks=rng.randint(98, 102), qty_units=rng.randint(1, 8),
            )
            known_ids.append(order_id)
        elif slot == 1:
            order_id = f"a-ask-{seed}-{cycle}"
            cycle_added.append(order_id)
            event = _event(
                seq, "LIMIT", f"evt-{index}", order_id=order_id, side="SELL",
                price_ticks=rng.randint(110, 114), qty_units=rng.randint(1, 8),
            )
            known_ids.append(order_id)
        elif slot == 2:
            event = _event(
                seq, "LIMIT", f"evt-{index}", order_id=f"buy-cross-{seed}-{cycle}",
                side="BUY", price_ticks=200, qty_units=rng.randint(1, 12),
            )
        elif slot == 3:
            event = _event(
                seq, "LIMIT", f"evt-{index}", order_id=f"sell-cross-{seed}-{cycle}",
                side="SELL", price_ticks=1, qty_units=rng.randint(1, 12),
            )
        elif slot == 4:
            event = _event(
                seq, "MARKET_SELL", f"evt-{index}",
                order_id=f"market-{seed}-{cycle}", qty_units=rng.randint(1, 10),
            )
        elif slot in (5, 6):
            target = cycle_added[slot - 5]
            event = _event(
                seq, "CANCEL", f"evt-{index}", target_order_id=target,
            )
        elif slot == 7:
            event = _event(
                seq, "LIMIT", f"evt-{index}", order_id=f"invalid-{seed}-{cycle}",
                side="BUY", price_ticks=100, qty_units=0,
            )
        elif slot == 8:
            target = known_ids[rng.randrange(len(known_ids))] if known_ids else "missing"
            event = _event(seq, "CANCEL", f"evt-{index}", target_order_id=target)
        else:
            event = _event(seq, "CANCEL", f"evt-{index}", target_order_id="absent")
            if last_accepted is not None:
                event["seq"] = last_accepted
        events.append(event)
        if event["seq"] > 0 and slot not in (7, 9):
            last_accepted = event["seq"]
    return events


def _assert_model_invariants(book):
    snapshot = book.snapshot()
    all_orders = snapshot["bids"] + snapshot["asks"]
    ids = [order["order_id"] for order in all_orders]
    assert len(ids) == len(set(ids))
    assert all(order["qty_units"] > 0 for order in all_orders)
    if snapshot["bids"] and snapshot["asks"]:
        assert snapshot["bids"][0]["price_ticks"] < snapshot["asks"][0]["price_ticks"]
    return snapshot


@pytest.mark.parametrize("seed", [42, 43, 44])
@pytest.mark.parametrize("book_type", BOOK_TYPES, ids=["baseline", "revised"])
def test_seeded_events_match_independent_brute_force_oracle(seed, book_type):
    oracle = BruteForceSpecificationBook()
    book = book_type()
    events = _seeded_mixed_events(seed, 1500)
    max_active = 0
    for event in events:
        expected = oracle.process(event)
        actual = book.process_event(event)
        assert actual == expected
        assert book.last_accepted_seq == oracle.last_seq
        snapshot = _assert_model_invariants(oracle)
        assert book.inspect_book() == snapshot
        max_active = max(max_active, len(oracle.orders))
    assert len(events) == 1500
    assert max_active < 100


@pytest.mark.parametrize("book_type", BOOK_TYPES, ids=["baseline", "revised"])
def test_2000_order_same_price_queue_uses_literal_arrival_order(book_type):
    book = book_type()
    expected_ids = []
    for seq in range(1, 2001):
        order_id = f"maker-{2001 - seq:04d}"
        expected_ids.append(order_id)
        result = book.process_event(
            _event(
                seq, "LIMIT", f"add-{seq}", order_id=order_id,
                side="BUY", price_ticks=6000, qty_units=1,
            )
        )
        assert result["status"] == "resting"

    result = book.process_event(
        _event(2001, "MARKET_SELL", "sell-all", order_id="taker", qty_units=2000)
    )
    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {
            "maker_id": order_id,
            "taker_id": "taker",
            "price_ticks": 6000,
            "qty_units": 1,
        }
        for order_id in expected_ids
    ]
    assert book.inspect_book() == {"bids": [], "asks": []}


@pytest.mark.parametrize("book_type", BOOK_TYPES, ids=["baseline", "revised"])
def test_id_can_be_reused_after_order_is_no_longer_live(book_type):
    book = book_type()
    assert book.process_event(
        _event(1, "LIMIT", "first", order_id="reused", side="BUY",
               price_ticks=6000, qty_units=2)
    )["status"] == "resting"
    assert book.process_event(
        _event(2, "CANCEL", "cancel", target_order_id="reused")
    )["status"] == "cancelled"
    result = book.process_event(
        _event(3, "LIMIT", "second", order_id="reused", side="BUY",
               price_ticks=5999, qty_units=1)
    )
    assert result["status"] == "resting"
    assert book.last_accepted_seq == 3


@pytest.mark.parametrize("book_type", BOOK_TYPES, ids=["baseline", "revised"])
def test_hand_calculated_mixed_event_sequence(book_type):
    book = book_type()
    events = [
        _event(1, "LIMIT", "e1", order_id="bid1", side="BUY", price_ticks=100, qty_units=10),
        _event(2, "LIMIT", "e2", order_id="bid2", side="BUY", price_ticks=99, qty_units=7),
        _event(3, "LIMIT", "e3", order_id="ask1", side="SELL", price_ticks=105, qty_units=6),
        _event(4, "LIMIT", "e4", order_id="buy-cross", side="BUY", price_ticks=105, qty_units=12),
        _event(5, "MARKET_SELL", "e5", order_id="sell1", qty_units=13),
        _event(6, "CANCEL", "e6", target_order_id="bid2"),
        _event(7, "MARKET_SELL", "e7", order_id="sell2", qty_units=1),
        _event(8, "CANCEL", "e8", target_order_id="bid1"),
    ]
    results = [book.process_event(event) for event in events]
    assert results[3] == {
        "event_id": "e4", "order_id": "buy-cross", "status": "resting",
        "unfilled_qty_units": 6,
        "fills": [{"maker_id": "ask1", "taker_id": "buy-cross",
                   "price_ticks": 105, "qty_units": 6}],
    }
    assert results[4]["fills"] == [
        {"maker_id": "buy-cross", "taker_id": "sell1", "price_ticks": 105, "qty_units": 6},
        {"maker_id": "bid1", "taker_id": "sell1", "price_ticks": 100, "qty_units": 7},
    ]
    assert results[5]["cancelled_qty_units"] == 7
    assert results[6]["fills"] == [
        {"maker_id": "bid1", "taker_id": "sell2", "price_ticks": 100, "qty_units": 1}
    ]
    assert results[7]["cancelled_qty_units"] == 2
    proceeds = sum(
        fill["price_ticks"] * fill["qty_units"]
        for result in results for fill in result.get("fills", [])
    )
    assert proceeds == 2060
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book.last_accepted_seq == 8


@pytest.mark.parametrize("book_type", BOOK_TYPES, ids=["baseline", "revised"])
@pytest.mark.parametrize(
    ("percent", "requested_qty", "status", "unfilled"),
    [(10, 11, "filled", 0), (100, 101, "filled", 0), (200, 202, "partial", 101)],
)
def test_fixed_book_sell_sizes_preserve_quantity_and_do_not_rest(
    book_type, percent, requested_qty, status, unfilled
):
    book = book_type()
    for seq, order_id, quantity in ((1, "first", 60), (2, "second", 41)):
        book.process_event(
            _event(seq, "LIMIT", f"add-{seq}", order_id=order_id,
                   side="BUY", price_ticks=6000, qty_units=quantity)
        )
    computed_request = ceil_percent(101, percent)
    assert computed_request == requested_qty
    result = book.process_event(
        _event(
            3, "MARKET_SELL", "sell", order_id="taker",
            qty_units=requested_qty,
        )
    )
    assert result["status"] == status
    assert result["unfilled_qty_units"] == unfilled
    assert (
        sum(fill["qty_units"] for fill in result["fills"]) + unfilled
        == requested_qty
    )
    assert sum(fill["qty_units"] for fill in result["fills"]) == min(
        requested_qty, 101
    )
    assert book.inspect_book()["asks"] == []
    assert book.last_accepted_seq == 3
    if percent == 10:
        assert book.inspect_book()["bids"] == [
            {"order_id": "first", "side": "BUY", "price_ticks": 6000,
             "qty_units": 49, "seq": 1},
            {"order_id": "second", "side": "BUY", "price_ticks": 6000,
             "qty_units": 41, "seq": 2},
        ]
    else:
        assert book.inspect_book()["bids"] == []


@pytest.mark.parametrize("quantity", range(1, 10))
def test_ten_percent_uses_ceiling_below_ten_units(quantity):
    assert ceil_percent(quantity, 10) == 1


def test_five_thousand_add_cancel_pairs_leave_no_revised_storage():
    book = RevisedBook()
    seq = 1
    for index in range(5000):
        order_id = f"cycle-{index}"
        added = book.process_event(
            _event(seq, "LIMIT", f"add-{index}", order_id=order_id,
                   side="BUY", price_ticks=10000 + index, qty_units=1)
        )
        assert added["status"] == "resting"
        seq += 1
        cancelled = book.process_event(
            _event(seq, "CANCEL", f"cancel-{index}", target_order_id=order_id)
        )
        assert cancelled["status"] == "cancelled"
        assert cancelled["cancelled_qty_units"] == 1
        seq += 1
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book._orders_by_id == {}
    assert book._bids_by_price == {}
    assert book._bid_heap == []
    assert book._bid_heap_members == set()
    assert book._asks_by_price == {}
    assert book._ask_heap == []
    assert book._ask_heap_members == set()
    assert book.last_accepted_seq == 10000


@pytest.mark.parametrize("compressed", [False, True], ids=["jsonl", "gzip"])
def test_replay_jsonl_and_gzip_dispatch_worked_example(compressed, tmp_path):
    source = ROOT / "data" / "worked_example.jsonl"
    expected = json.loads((ROOT / "data" / "worked_expected.json").read_text())
    raw = source.read_bytes()
    target = tmp_path / ("worked.jsonl.gz" if compressed else "worked.jsonl")
    if compressed:
        with gzip.open(target, "wb") as stream:
            stream.write(raw)
    else:
        target.write_bytes(raw)
    for version in ("baseline", "revised"):
        output = replay(target, version)
        assert output["last_accepted_seq"] == 6
        assert output["results"][-1] == expected["market_sell_result"]
        assert output["book"]["bids"][0]["order_id"] == "b4"
        assert output["book"]["bids"][0]["qty_units"] == 400000000
        assert output["book"]["asks"][0]["order_id"] == "a1"
        tick_units = sum(
            fill["price_ticks"] * fill["qty_units"]
            for fill in output["results"][-1]["fills"]
        )
        assert tick_units == expected["gross_proceeds_tick_units"]
        assert tick_units // 10_000_000_000 == int(
            expected["gross_proceeds_usd"].split(".")[0]
        )
        for side, key in (("BUY", "bids"), ("SELL", "asks")):
            expected_side = [
                {
                    "order_id": order["order_id"],
                    "side": order["side"],
                    "price_ticks": order["price_ticks"],
                    "qty_units": order["qty_units"],
                    "seq": order["arrival_seq"],
                }
                for order in expected["remaining_orders"]
                if order["side"] == side
            ]
            assert output["book"][key] == expected_side
