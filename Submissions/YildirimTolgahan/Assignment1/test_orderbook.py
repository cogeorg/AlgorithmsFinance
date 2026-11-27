"""Specification tests shared by both order-book versions.

Written before the implementations. Expected values in the hand-calculated
cases were worked out on paper from the assignment rules, not copied from
either engine. The generated-stream tests use an independent sort-based
specification model defined in this file (it shares no code with the engines).
"""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import random
import unittest

from book_a import OrderBookA
from book_b import OrderBookB
from book_b1 import OrderBookB1
from events import read_events
import generate_orders

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
VERSIONS = (OrderBookA, OrderBookB, OrderBookB1)
BTC = 100_000_000          # qty_units per BTC
USD = 100                  # price_ticks per dollar
TICK_UNITS_PER_USD = 10_000_000_000


# ---------------------------------------------------------------- builders
def limit(seq, order_id, side, price, qty):
    return {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": order_id,
            "side": side, "price_ticks": price, "qty_units": qty}


def market(seq, order_id, qty):
    return {"seq": seq, "event_id": f"e{seq}", "type": "MARKET_SELL",
            "order_id": order_id, "qty_units": qty}


def cancel(seq, target):
    return {"seq": seq, "event_id": f"e{seq}", "type": "CANCEL", "target_order_id": target}


def fill(maker, taker, price, qty):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": price, "qty_units": qty}


def submitted(seq, order_id, status, unfilled, fills=()):
    return {"event_id": f"e{seq}", "order_id": order_id, "status": status,
            "unfilled_qty_units": unfilled, "fills": list(fills)}


def cancelled(seq, target, status, qty):
    return {"event_id": f"e{seq}", "target_order_id": target, "status": status,
            "cancelled_qty_units": qty}


def row(order_id, side, price, qty, seq):
    return {"order_id": order_id, "side": side, "price_ticks": price,
            "qty_units": qty, "arrival_seq": seq}


def proceeds(fills):
    return sum(f["price_ticks"] * f["qty_units"] for f in fills)


# ------------------------------------------- independent specification model
def canonical(rows):
    bids = sorted((r for r in rows if r["side"] == "BUY"),
                  key=lambda r: (-r["price_ticks"], r["arrival_seq"]))
    asks = sorted((r for r in rows if r["side"] == "SELL"),
                  key=lambda r: (r["price_ticks"], r["arrival_seq"]))
    return bids + asks


def _positive_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _identifier(value):
    return isinstance(value, str) and value != ""


def spec_step(rows, last_seq, event):
    """Apply one event to a list of resting rows by filtering and sorting, as on paper.

    Mutates rows only for an accepted event. Returns (result without rejection
    reason, last accepted seq).
    """
    event_id = event.get("event_id") if isinstance(event, dict) else None
    rejection = ({"event_id": event_id if _identifier(event_id) else None,
                  "status": "rejected"}, last_seq)
    if not isinstance(event, dict) or not _identifier(event_id):
        return rejection
    seq, kind = event.get("seq"), event.get("type")
    if not _positive_integer(seq) or seq <= last_seq:
        return rejection

    if kind == "CANCEL":
        target = event.get("target_order_id")
        if not _identifier(target):
            return rejection
        for r in rows:
            if r["order_id"] == target:
                rows.remove(r)
                return ({"event_id": event_id, "target_order_id": target, "status": "cancelled",
                         "cancelled_qty_units": r["qty_units"]}, seq)
        return ({"event_id": event_id, "target_order_id": target, "status": "not_found",
                 "cancelled_qty_units": 0}, seq)

    if kind not in ("LIMIT", "MARKET_SELL"):
        return rejection
    order_id, qty = event.get("order_id"), event.get("qty_units")
    if not _identifier(order_id) or not _positive_integer(qty):
        return rejection
    if any(r["order_id"] == order_id for r in rows):
        return rejection
    if kind == "LIMIT":
        side, price = event.get("side"), event.get("price_ticks")
        if side not in ("BUY", "SELL") or not _positive_integer(price):
            return rejection
        if side == "BUY":
            eligible = canonical([r for r in rows if r["side"] == "SELL" and r["price_ticks"] <= price])
        else:
            eligible = canonical([r for r in rows if r["side"] == "BUY" and r["price_ticks"] >= price])
    else:
        eligible = canonical([r for r in rows if r["side"] == "BUY"])

    fills = []
    for maker in eligible:
        if qty == 0:
            break
        traded = min(qty, maker["qty_units"])
        fills.append(fill(maker["order_id"], order_id, maker["price_ticks"], traded))
        maker["qty_units"] -= traded
        qty -= traded
    if fills:
        rows[:] = [r for r in rows if r["qty_units"] > 0]
    if kind == "LIMIT":
        if qty:
            rows.append(row(order_id, side, price, qty, seq))
        status = "resting" if qty else "filled"
    else:
        status = "filled" if qty == 0 else ("partial" if fills else "unfilled")
    return ({"event_id": event_id, "order_id": order_id, "status": status,
             "unfilled_qty_units": qty, "fills": fills}, seq)


def without_reason(result):
    return {k: v for k, v in result.items() if k != "reason"}


# --------------------------------------------------------- shared assertions
class BookTestCase(unittest.TestCase):
    maxDiff = None

    def check(self, events, expected_results, expected_book):
        """Replay events on a fresh book of every version; compare each result."""
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for index, (event, expected) in enumerate(zip(events, expected_results, strict=True)):
                    result = book.ProcessEvent(event)
                    if expected is not None:
                        self.assertEqual(result, expected, f"event index {index}")
                    book.check_invariants()
                self.assertEqual(book.InspectBook(), expected_book)

    def assert_snapshot_invariants(self, rows):
        bids = [r for r in rows if r["side"] == "BUY"]
        asks = [r for r in rows if r["side"] == "SELL"]
        self.assertEqual(rows, canonical(rows), "inspection is not in canonical order")
        self.assertTrue(all(r["qty_units"] > 0 for r in rows), "nonpositive resting quantity")
        self.assertEqual(len({r["order_id"] for r in rows}), len(rows), "order stored twice")
        if bids and asks:
            self.assertLess(bids[0]["price_ticks"], asks[0]["price_ticks"], "crossed book")

    def assert_conservation(self, before, event, result, after):
        """Quantity and value bookkeeping derived only from the returned result."""
        old = {r["order_id"]: r for r in before}
        new = {r["order_id"]: r for r in after}
        status = result["status"]
        if status == "rejected":
            self.assertEqual(before, after)
            return
        if event["type"] == "CANCEL":
            target = event["target_order_id"]
            expected_qty = old[target]["qty_units"] if target in old else 0
            self.assertEqual(result["cancelled_qty_units"], expected_qty)
            self.assertEqual(status, "cancelled" if target in old else "not_found")
            self.assertEqual(after, [r for r in before if r["order_id"] != target])
            return
        fills, taker = result["fills"], event["order_id"]
        executed = sum(f["qty_units"] for f in fills)
        self.assertEqual(event["qty_units"], executed + result["unfilled_qty_units"])
        lost = {}
        for f in fills:
            self.assertGreater(f["qty_units"], 0)
            self.assertEqual(f["taker_id"], taker)
            self.assertEqual(f["price_ticks"], old[f["maker_id"]]["price_ticks"])
            lost[f["maker_id"]] = lost.get(f["maker_id"], 0) + f["qty_units"]
        for order_id, r in old.items():
            remaining = r["qty_units"] - lost.get(order_id, 0)
            self.assertGreaterEqual(remaining, 0)
            self.assertEqual(new.get(order_id, {}).get("qty_units", 0), remaining)
            if order_id in new:
                self.assertEqual(new[order_id]["arrival_seq"], r["arrival_seq"])
        rests = event["type"] == "LIMIT" and result["unfilled_qty_units"] > 0
        self.assertEqual(taker in new, rests)
        if rests:
            self.assertEqual(new[taker], row(taker, event["side"], event["price_ticks"],
                                             result["unfilled_qty_units"], event["seq"]))
        self.assertEqual(set(new) - set(old), {taker} if rests else set())
        self.assertEqual(proceeds(fills), sum(old[m]["price_ticks"] * q for m, q in lost.items()))

    def assert_matches_spec(self, events, snapshot_every=1):
        """Every version against the specification model after every event."""
        books = [cls() for cls in VERSIONS]
        rows, last_seq = [], 0
        for index, event in enumerate(events):
            before = canonical([dict(r) for r in rows]) if snapshot_every == 1 else None
            expected, last_seq = spec_step(rows, last_seq, event)
            results = [book.ProcessEvent(event) for book in books]
            for cls, result in zip(VERSIONS, results):
                self.assertEqual(without_reason(result), expected, f"{cls.__name__} event index {index}")
            for other in results[1:]:
                self.assertEqual(results[0], other, f"versions disagree at event index {index}")
            if expected["status"] == "rejected":
                self.assertIsInstance(results[0]["reason"], str)
                self.assertTrue(results[0]["reason"])
            if index % snapshot_every == 0 or index == len(events) - 1:
                wanted = canonical([dict(r) for r in rows])
                for cls, book in zip(VERSIONS, books):
                    self.assertEqual(book.InspectBook(), wanted, f"{cls.__name__} book after event index {index}")
                    book.check_invariants()
                self.assert_snapshot_invariants(wanted)
                if snapshot_every == 1:
                    self.assert_conservation(before, event, results[0], wanted)
            for book in books:
                self.assertEqual(book.last_seq, last_seq)
        return books


# ------------------------------------------------- hand-calculated behaviour
P600, P599, P597, P601 = 60_000 * USD, 59_900 * USD, 59_700 * USD, 60_100 * USD


class WorkedExampleTests(BookTestCase):
    def test_supplied_worked_example(self):
        events = read_events(DATA / "worked_example.jsonl")
        expected = json.loads((DATA / "worked_expected.json").read_text(encoding="utf-8"))
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[-1], expected["market_sell_result"])
                self.assertEqual(book.InspectBook(), expected["remaining_orders"])
                value = proceeds(results[-1]["fills"])
                self.assertEqual(value, expected["gross_proceeds_tick_units"])
                self.assertEqual(f"{value // TICK_UNITS_PER_USD}.{value % TICK_UNITS_PER_USD // 10**8:02d}",
                                 expected["gross_proceeds_usd"])

    def test_worked_example_calculated_by_hand(self):
        # 1 BTC * 60,000 + 1 * 60,000 + 3 * 59,900 + 1 * 59,700 = 359,400 dollars.
        events = [limit(1, "b1", "BUY", P600, BTC), limit(2, "b2", "BUY", P600, BTC),
                  limit(3, "b3", "BUY", P599, 3 * BTC), limit(4, "b4", "BUY", P597, 5 * BTC),
                  limit(5, "a1", "SELL", P601, 2 * BTC), market(6, "s1", 6 * BTC)]
        sell_fills = [fill("b1", "s1", P600, BTC), fill("b2", "s1", P600, BTC),
                      fill("b3", "s1", P599, 3 * BTC), fill("b4", "s1", P597, BTC)]
        self.assertEqual(proceeds(sell_fills), 359_400 * TICK_UNITS_PER_USD)
        self.check(events,
                   [submitted(1, "b1", "resting", BTC), submitted(2, "b2", "resting", BTC),
                    submitted(3, "b3", "resting", 3 * BTC), submitted(4, "b4", "resting", 5 * BTC),
                    submitted(5, "a1", "resting", 2 * BTC), submitted(6, "s1", "filled", 0, sell_fills)],
                   [row("b4", "BUY", P597, 4 * BTC, 4), row("a1", "SELL", P601, 2 * BTC, 5)])


class EmptyAndSingleOrderTests(BookTestCase):
    def test_new_book_is_empty(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                self.assertEqual(book.InspectBook(), [])
                self.assertIsNone(book.best_bid())
                self.assertIsNone(book.best_ask())
                self.assertEqual((book.active_orders(), book.price_levels(), book.last_seq), (0, 0, 0))

    def test_market_sell_into_empty_book_is_unfilled_and_never_rests(self):
        self.check([market(1, "s1", 7)], [submitted(1, "s1", "unfilled", 7)], [])

    def test_market_sell_ignores_asks(self):
        self.check([limit(1, "a1", "SELL", 100, 5), market(2, "s1", 3)],
                   [submitted(1, "a1", "resting", 5), submitted(2, "s1", "unfilled", 3)],
                   [row("a1", "SELL", 100, 5, 1)])

    def test_cancel_on_empty_book(self):
        self.check([cancel(1, "ghost")], [cancelled(1, "ghost", "not_found", 0)], [])

    def test_single_bid_rests(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                self.assertEqual(book.ProcessEvent(limit(1, "b1", "BUY", 100, 5)),
                                 submitted(1, "b1", "resting", 5))
                self.assertEqual(book.InspectBook(), [row("b1", "BUY", 100, 5, 1)])
                self.assertEqual((book.best_bid(), book.best_ask()), (100, None))
                self.assertEqual((book.active_orders(), book.price_levels(), book.last_seq), (1, 1, 1))

    def test_single_ask_rests(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                book.ProcessEvent(limit(4, "a1", "SELL", 105, 2))
                self.assertEqual(book.InspectBook(), [row("a1", "SELL", 105, 2, 4)])
                self.assertEqual((book.best_bid(), book.best_ask()), (None, 105))

    def test_sale_smaller_than_single_order(self):
        self.check([limit(1, "b1", "BUY", 100, 5), market(2, "s1", 2)],
                   [None, submitted(2, "s1", "filled", 0, [fill("b1", "s1", 100, 2)])],
                   [row("b1", "BUY", 100, 3, 1)])

    def test_sale_equal_to_single_order(self):
        self.check([limit(1, "b1", "BUY", 100, 5), market(2, "s1", 5)],
                   [None, submitted(2, "s1", "filled", 0, [fill("b1", "s1", 100, 5)])], [])

    def test_sale_larger_than_single_order_discards_residual(self):
        self.check([limit(1, "b1", "BUY", 100, 5), market(2, "s1", 8), market(3, "s2", 1)],
                   [None, submitted(2, "s1", "partial", 3, [fill("b1", "s1", 100, 5)]),
                    submitted(3, "s2", "unfilled", 1)], [])


class MarketSellTests(BookTestCase):
    BOOK = [limit(1, "b1", "BUY", 100, 4), limit(2, "b2", "BUY", 100, 6),
            limit(3, "b3", "BUY", 99, 5), limit(4, "b4", "BUY", 97, 10)]   # depth 25

    def test_smaller_than_depth(self):
        # 4 from b1, then 3 of b2's 6 at the same price.
        self.check(self.BOOK + [market(5, "s", 7)],
                   [None] * 4 + [submitted(5, "s", "filled", 0, [fill("b1", "s", 100, 4), fill("b2", "s", 100, 3)])],
                   [row("b2", "BUY", 100, 3, 2), row("b3", "BUY", 99, 5, 3), row("b4", "BUY", 97, 10, 4)])

    def test_equal_to_depth(self):
        fills = [fill("b1", "s", 100, 4), fill("b2", "s", 100, 6), fill("b3", "s", 99, 5), fill("b4", "s", 97, 10)]
        self.assertEqual(proceeds(fills), 400 + 600 + 495 + 970)
        self.check(self.BOOK + [market(5, "s", 25)], [None] * 4 + [submitted(5, "s", "filled", 0, fills)], [])

    def test_larger_than_depth(self):
        fills = [fill("b1", "s", 100, 4), fill("b2", "s", 100, 6), fill("b3", "s", 99, 5), fill("b4", "s", 97, 10)]
        self.check(self.BOOK + [market(5, "s", 26)], [None] * 4 + [submitted(5, "s", "partial", 1, fills)], [])

    def test_multiple_price_levels_best_price_first_regardless_of_arrival(self):
        # The best bid arrives last; price outranks arrival.
        self.check([limit(1, "low", "BUY", 95, 2), limit(2, "mid", "BUY", 98, 2), limit(3, "top", "BUY", 99, 2),
                    market(4, "s", 5)],
                   [None] * 3 + [submitted(4, "s", "filled", 0, [fill("top", "s", 99, 2), fill("mid", "s", 98, 2),
                                                                fill("low", "s", 95, 1)])],
                   [row("low", "BUY", 95, 1, 1)])

    def test_partial_fill_then_second_sale_keeps_maker_priority(self):
        # b1 is cut to 1 unit but still precedes b2 for the next sale.
        self.check([limit(1, "b1", "BUY", 100, 4), limit(2, "b2", "BUY", 100, 4),
                    market(3, "s1", 3), market(4, "s2", 2), market(5, "s3", 10)],
                   [None, None,
                    submitted(3, "s1", "filled", 0, [fill("b1", "s1", 100, 3)]),
                    submitted(4, "s2", "filled", 0, [fill("b1", "s2", 100, 1), fill("b2", "s2", 100, 1)]),
                    submitted(5, "s3", "partial", 7, [fill("b2", "s3", 100, 3)])], [])

    def test_each_result_contains_only_its_own_fills(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                book.ProcessEvent(limit(1, "b1", "BUY", 100, 9))
                first = book.ProcessEvent(market(2, "s1", 1))
                second = book.ProcessEvent(market(3, "s2", 2))
                self.assertEqual(first["fills"], [fill("b1", "s1", 100, 1)])
                self.assertEqual(second["fills"], [fill("b1", "s2", 100, 2)])
                self.assertIsNot(first["fills"], second["fills"])

    def test_identifier_spelling_gives_no_priority(self):
        # Alphabetical order (a..., m..., z...) is the reverse of arrival order.
        self.check([limit(1, "zz-9", "BUY", 100, 1), limit(2, "mm-5", "BUY", 100, 1), limit(3, "aa-1", "BUY", 100, 1),
                    limit(4, "10", "SELL", 110, 1), limit(5, "9", "SELL", 110, 1), market(6, "0", 2)],
                   [None] * 5 + [submitted(6, "0", "filled", 0, [fill("zz-9", "0", 100, 1), fill("mm-5", "0", 100, 1)])],
                   [row("aa-1", "BUY", 100, 1, 3), row("10", "SELL", 110, 1, 4), row("9", "SELL", 110, 1, 5)])

    def test_long_queue_at_one_price(self):
        # 500 makers of 3 units: a sale of 752 = 250 complete makers + 2 units of the 251st.
        events = [limit(i, f"q{(i * 7919) % 1000:03d}-{i}", "BUY", 100, 3) for i in range(1, 501)]
        ids = [e["order_id"] for e in events]
        fills = [fill(ids[i], "s", 100, 3) for i in range(250)] + [fill(ids[250], "s", 100, 2)]
        book = [row(ids[250], "BUY", 100, 1, 251)] + [row(ids[i], "BUY", 100, 3, i + 1) for i in range(251, 500)]
        self.check(events + [market(501, "s", 752)], [None] * 500 + [submitted(501, "s", "filled", 0, fills)], book)


class LimitOrderTests(BookTestCase):
    def test_noncrossing_limits_rest_on_both_sides(self):
        self.check([limit(1, "b1", "BUY", 99, 5), limit(2, "a1", "SELL", 101, 4),
                    limit(3, "b2", "BUY", 100, 1), limit(4, "a2", "SELL", 101, 2), limit(5, "b3", "BUY", 99, 7)],
                   [submitted(1, "b1", "resting", 5), submitted(2, "a1", "resting", 4), submitted(3, "b2", "resting", 1),
                    submitted(4, "a2", "resting", 2), submitted(5, "b3", "resting", 7)],
                   [row("b2", "BUY", 100, 1, 3), row("b1", "BUY", 99, 5, 1), row("b3", "BUY", 99, 7, 5),
                    row("a1", "SELL", 101, 4, 2), row("a2", "SELL", 101, 2, 4)])

    def test_buy_at_exactly_best_ask_crosses_at_resting_price(self):
        self.check([limit(1, "a1", "SELL", 101, 4), limit(2, "b1", "BUY", 101, 3)],
                   [None, submitted(2, "b1", "filled", 0, [fill("a1", "b1", 101, 3)])],
                   [row("a1", "SELL", 101, 1, 1)])

    def test_buy_one_tick_below_best_ask_does_not_cross(self):
        self.check([limit(1, "a1", "SELL", 101, 4), limit(2, "b1", "BUY", 100, 3)],
                   [None, submitted(2, "b1", "resting", 3)],
                   [row("b1", "BUY", 100, 3, 2), row("a1", "SELL", 101, 4, 1)])

    def test_crossing_buy_pays_resting_prices_and_rests_residual(self):
        # Limit 103: takes 101 (2+1), 102 (2); 104 is too expensive; 5 units rest at 103.
        fills = [fill("a1", "b", 101, 2), fill("a2", "b", 101, 1), fill("a3", "b", 102, 2)]
        self.assertEqual(proceeds(fills), 202 + 101 + 204)
        self.check([limit(1, "a1", "SELL", 101, 2), limit(2, "a3", "SELL", 102, 2), limit(3, "a4", "SELL", 104, 9),
                    limit(4, "a2", "SELL", 101, 1), limit(5, "b", "BUY", 103, 10)],
                   [None] * 4 + [submitted(5, "b", "resting", 5, fills)],
                   [row("b", "BUY", 103, 5, 5), row("a4", "SELL", 104, 9, 3)])

    def test_crossing_sell_receives_resting_prices_and_rests_residual(self):
        # Limit 99: takes 100 (3), 99 (2); the 98 bid is below the limit; 1 unit rests at 99.
        fills = [fill("b1", "a", 100, 3), fill("b2", "a", 99, 2)]
        self.check([limit(1, "b3", "BUY", 98, 4), limit(2, "b1", "BUY", 100, 3), limit(3, "b2", "BUY", 99, 2),
                    limit(4, "a", "SELL", 99, 6)],
                   [None] * 3 + [submitted(4, "a", "resting", 1, fills)],
                   [row("b3", "BUY", 98, 4, 1), row("a", "SELL", 99, 1, 4)])

    def test_crossing_limit_filled_completely_does_not_rest(self):
        self.check([limit(1, "b1", "BUY", 100, 5), limit(2, "a", "SELL", 90, 5)],
                   [None, submitted(2, "a", "filled", 0, [fill("b1", "a", 100, 5)])], [])

    def test_crossing_limit_partially_fills_maker_which_keeps_priority(self):
        self.check([limit(1, "a1", "SELL", 101, 5), limit(2, "a2", "SELL", 101, 5), limit(3, "b1", "BUY", 105, 2),
                    limit(4, "b2", "BUY", 101, 4)],
                   [None, None, submitted(3, "b1", "filled", 0, [fill("a1", "b1", 101, 2)]),
                    submitted(4, "b2", "filled", 0, [fill("a1", "b2", 101, 3), fill("a2", "b2", 101, 1)])],
                   [row("a2", "SELL", 101, 4, 2)])

    def test_residual_joins_its_queue_behind_earlier_orders(self):
        # "late" trades 1 unit, then rests at 100 behind "early"; a market sell reaches "early" first.
        self.check([limit(1, "early", "BUY", 100, 2), limit(2, "a1", "SELL", 100, 3)],
                   [None, submitted(2, "a1", "resting", 1, [fill("early", "a1", 100, 2)])],
                   [row("a1", "SELL", 100, 1, 2)])
        self.check([limit(1, "a1", "SELL", 100, 1), limit(2, "early", "BUY", 100, 2), limit(3, "late", "BUY", 100, 4),
                    market(4, "s", 3)],
                   [None, submitted(2, "early", "resting", 1, [fill("a1", "early", 100, 1)]),
                    submitted(3, "late", "resting", 4),
                    submitted(4, "s", "filled", 0, [fill("early", "s", 100, 1), fill("late", "s", 100, 2)])],
                   [row("late", "BUY", 100, 2, 3)])

    def test_aggressive_buy_sweeps_all_asks_then_rests_without_crossing(self):
        self.check([limit(1, "a1", "SELL", 101, 1), limit(2, "a2", "SELL", 105, 1), limit(3, "b", "BUY", 200, 5)],
                   [None, None, submitted(3, "b", "resting", 3, [fill("a1", "b", 101, 1), fill("a2", "b", 105, 1)])],
                   [row("b", "BUY", 200, 3, 3)])


class CancellationTests(BookTestCase):
    def test_cancel_before_any_fill(self):
        self.check([limit(1, "b1", "BUY", 100, 5), limit(2, "b2", "BUY", 100, 6), cancel(3, "b1"), market(4, "s", 2)],
                   [None, None, cancelled(3, "b1", "cancelled", 5),
                    submitted(4, "s", "filled", 0, [fill("b2", "s", 100, 2)])],
                   [row("b2", "BUY", 100, 4, 2)])

    def test_cancel_after_partial_fill_removes_only_the_residual(self):
        self.check([limit(1, "b1", "BUY", 100, 5), market(2, "s", 2), cancel(3, "b1")],
                   [None, submitted(2, "s", "filled", 0, [fill("b1", "s", 100, 2)]), cancelled(3, "b1", "cancelled", 3)],
                   [])

    def test_cancel_after_full_fill_is_not_found(self):
        self.check([limit(1, "b1", "BUY", 100, 5), market(2, "s", 5), cancel(3, "b1")],
                   [None, None, cancelled(3, "b1", "not_found", 0)], [])

    def test_repeated_and_unknown_cancellation(self):
        self.check([limit(1, "b1", "BUY", 100, 5), cancel(2, "b1"), cancel(3, "b1"), cancel(4, "never-seen")],
                   [None, cancelled(2, "b1", "cancelled", 5), cancelled(3, "b1", "not_found", 0),
                    cancelled(4, "never-seen", "not_found", 0)], [])

    def test_cancel_middle_of_queue_preserves_remaining_order(self):
        self.check([limit(1, "b1", "BUY", 100, 1), limit(2, "b2", "BUY", 100, 1), limit(3, "b3", "BUY", 100, 1),
                    cancel(4, "b2"), market(5, "s", 2)],
                   [None] * 3 + [cancelled(4, "b2", "cancelled", 1),
                                 submitted(5, "s", "filled", 0, [fill("b1", "s", 100, 1), fill("b3", "s", 100, 1)])], [])

    def test_cancel_resting_ask_and_last_order_of_best_level(self):
        # Cancelling the only best bid exposes the next level to the following sale.
        self.check([limit(1, "b1", "BUY", 100, 1), limit(2, "b2", "BUY", 98, 1), limit(3, "a1", "SELL", 105, 2),
                    cancel(4, "b1"), cancel(5, "a1"), market(6, "s", 1)],
                   [None] * 3 + [cancelled(4, "b1", "cancelled", 1), cancelled(5, "a1", "cancelled", 2),
                                 submitted(6, "s", "filled", 0, [fill("b2", "s", 98, 1)])], [])

    def test_cancelling_a_market_sell_identifier_is_not_found(self):
        self.check([limit(1, "b1", "BUY", 100, 1), market(2, "s1", 5), cancel(3, "s1")],
                   [None, submitted(2, "s1", "partial", 4, [fill("b1", "s1", 100, 1)]),
                    cancelled(3, "s1", "not_found", 0)], [])

    def test_price_level_can_be_reused_after_emptying(self):
        self.check([limit(1, "b1", "BUY", 100, 1), cancel(2, "b1"), limit(3, "b2", "BUY", 100, 2),
                    market(4, "s1", 2), limit(5, "b3", "BUY", 100, 3), market(6, "s2", 1)],
                   [None, None, None, submitted(4, "s1", "filled", 0, [fill("b2", "s1", 100, 2)]), None,
                    submitted(6, "s2", "filled", 0, [fill("b3", "s2", 100, 1)])],
                   [row("b3", "BUY", 100, 2, 5)])


class ValidationTests(BookTestCase):
    SETUP = [limit(1, "b1", "BUY", 100, 5), limit(2, "a1", "SELL", 110, 5)]
    BOOK = [row("b1", "BUY", 100, 5, 1), row("a1", "SELL", 110, 5, 2)]

    def invalid_events(self):
        good = limit(3, "x", "BUY", 105, 1)
        bad_values = (0, -1, 1.0, 2.5, "3", None, True, [1])
        cases = [dict(good, qty_units=v) for v in bad_values]
        cases += [dict(good, price_ticks=v) for v in bad_values]
        cases += [dict(market(3, "x", 1), qty_units=v) for v in bad_values]
        cases += [dict(good, side=v) for v in ("buy", "HOLD", "", None, 1)]
        cases += [dict(good, type=v) for v in ("limit", "MARKET_BUY", "", None, 7)]
        cases += [dict(good, order_id=v) for v in ("", None, 17, "b1", "a1")]       # last two: live duplicates
        cases += [dict(market(3, "x", 1), order_id=v) for v in ("", None, "b1", "a1")]
        cases += [dict(cancel(3, "b1"), target_order_id=v) for v in ("", None, 5)]
        cases += [dict(good, seq=v) for v in (2, 1, 0, -4, 2.0, "3", None, True)]   # nonincreasing or noninteger
        cases += [dict(cancel(3, "b1"), seq=2), dict(market(3, "x", 1), seq=1)]
        cases += [dict(good, event_id=v) for v in ("", None, 12)]
        for key in ("seq", "event_id", "type", "order_id", "side", "price_ticks", "qty_units"):
            cases.append({k: v for k, v in good.items() if k != key})
        cases += [{k: v for k, v in market(3, "x", 1).items() if k != "qty_units"},
                  {k: v for k, v in cancel(3, "b1").items() if k != "target_order_id"},
                  {}, None, [], "LIMIT", 3]
        return cases

    def test_invalid_events_are_rejected_without_changing_state(self):
        for cls in VERSIONS:
            for bad in self.invalid_events():
                with self.subTest(version=cls.__name__, event=bad):
                    book = cls()
                    for event in self.SETUP:
                        book.ProcessEvent(event)
                    result = book.ProcessEvent(copy.deepcopy(bad))
                    self.assertEqual(result["status"], "rejected")
                    self.assertIsInstance(result["reason"], str)
                    self.assertTrue(result["reason"])
                    event_id = bad.get("event_id") if isinstance(bad, dict) else None
                    self.assertEqual(result["event_id"], event_id if isinstance(event_id, str) and event_id else None)
                    self.assertEqual(set(result), {"event_id", "status", "reason"})
                    self.assertEqual(book.InspectBook(), self.BOOK)
                    self.assertEqual(book.last_seq, 2)
                    book.check_invariants()
                    # The next valid arrival rank is still accepted.
                    self.assertEqual(book.ProcessEvent(cancel(3, "nobody"))["status"], "not_found")

    def test_rejected_event_does_not_advance_last_accepted_seq(self):
        # seq 9 is rejected for its quantity, so seq 6 is still an increase over 5.
        self.check([limit(5, "b1", "BUY", 100, 5), limit(9, "bad", "BUY", 100, 0), limit(6, "b2", "BUY", 100, 1),
                    limit(6, "b3", "BUY", 100, 1)],
                   [None, None, submitted(6, "b2", "resting", 1), None],
                   [row("b1", "BUY", 100, 5, 5), row("b2", "BUY", 100, 1, 6)])

    def test_sequence_gaps_are_allowed(self):
        self.check([limit(10, "b1", "BUY", 100, 1), limit(1000, "b2", "BUY", 100, 1)], [None, None],
                   [row("b1", "BUY", 100, 1, 10), row("b2", "BUY", 100, 1, 1000)])

    def test_identifier_of_inactive_order_is_not_a_live_duplicate(self):
        # Historical reuse is outside scope: only a currently active identifier is rejected.
        self.check([limit(1, "b1", "BUY", 100, 1), cancel(2, "b1"), limit(3, "b1", "BUY", 99, 2)],
                   [None, None, submitted(3, "b1", "resting", 2)], [row("b1", "BUY", 99, 2, 3)])

    def test_inputs_are_not_mutated(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                events = [limit(1, "b1", "BUY", 100, 5), market(2, "s", 9), cancel(3, "b1")]
                before = copy.deepcopy(events)
                book = cls()
                for event in events:
                    book.ProcessEvent(event)
                self.assertEqual(events, before)

    def test_huge_integers_stay_exact(self):
        big = 10**30 + 7
        self.check([limit(1, "b1", "BUY", big, big), market(2, "s", big - 1)],
                   [None, submitted(2, "s", "filled", 0, [fill("b1", "s", big, big - 1)])],
                   [row("b1", "BUY", big, 1, 1)])


class DirectInterfaceTests(BookTestCase):
    def test_named_operations_match_the_dispatcher(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                self.assertEqual(book.AddLimitOrder("b1", "BUY", 100, 5, seq=1, event_id="e1"),
                                 submitted(1, "b1", "resting", 5))
                self.assertEqual(book.AddLimitOrder("b2", "BUY", 100, 2, seq=2, event_id="e2"),
                                 submitted(2, "b2", "resting", 2))
                self.assertEqual(book.FillMarketSell("s1", 6, event_id="e3"),
                                 submitted(3, "s1", "filled", 0, [fill("b1", "s1", 100, 5), fill("b2", "s1", 100, 1)]))
                self.assertEqual(book.CancelOrder("b2", event_id="e4"), cancelled(4, "b2", "cancelled", 1))
                self.assertEqual(book.CancelOrder("b2"), {"event_id": None, "target_order_id": "b2",
                                                          "status": "not_found", "cancelled_qty_units": 0})
                self.assertEqual(book.InspectBook(), [])

    def test_named_operations_validate_their_arguments(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                book.AddLimitOrder("b1", "BUY", 100, 5, seq=3)
                for result in (book.AddLimitOrder("b2", "BUY", 100, 0, seq=4),
                               book.AddLimitOrder("b2", "UP", 100, 1, seq=4),
                               book.AddLimitOrder("b2", "BUY", 100, 1, seq=3),
                               book.AddLimitOrder("b1", "SELL", 200, 1, seq=4),
                               book.FillMarketSell("s", -1), book.FillMarketSell("b1", 1),
                               book.FillMarketSell("s", 1, seq=3), book.CancelOrder(None),
                               book.CancelOrder("b1", seq=2)):
                    self.assertEqual(result["status"], "rejected")
                self.assertEqual(book.InspectBook(), [row("b1", "BUY", 100, 5, 3)])
                self.assertEqual(book.last_seq, 3)


# ------------------------------------------------------- generated streams
def random_stream(rng, count, invalid_share=0.08):
    """Narrow price band so that limits cross often; identifiers are unrelated to arrival."""
    events, issued, seq = [], [], 0
    for _ in range(count):
        seq += rng.choice((1, 1, 1, 2, 5))
        order_id = f"{rng.randrange(10**6):06d}-{seq}"
        u = rng.random()
        if u < 0.22 and issued:
            event = cancel(seq, rng.choice(issued) if rng.random() < 0.9 else "unknown")
        elif u < 0.37:
            event = market(seq, order_id, rng.randint(1, 12))
        else:
            side = rng.choice(("BUY", "SELL"))
            price = rng.randint(97, 101) if side == "BUY" else rng.randint(99, 103)
            event = limit(seq, order_id, side, price, rng.randint(1, 6))
            issued.append(order_id)
        if rng.random() < invalid_share:
            fault = rng.randrange(7)
            if fault == 0:
                event["seq"] = seq = max(1, seq - rng.randint(1, 3))      # usually nonincreasing
            elif fault == 1 and "qty_units" in event:
                event["qty_units"] = rng.choice((0, -3, 1.5, "2", None, True))
            elif fault == 2 and "price_ticks" in event:
                event["price_ticks"] = rng.choice((0, -100, 99.5, None))
            elif fault == 3:
                event["type"] = rng.choice(("MARKET_BUY", "limit", None))
            elif fault == 4 and "side" in event:
                event["side"] = rng.choice(("buy", "SHORT"))
            elif fault == 5 and issued and "order_id" in event:
                event["order_id"] = rng.choice(issued)                    # duplicate only if still live
            else:
                event.pop(rng.choice(sorted(event)))
        events.append(event)
    return events


class GeneratedStreamTests(BookTestCase):
    def test_random_streams_against_specification_model_after_every_event(self):
        for seed in range(40):
            with self.subTest(seed=seed):
                self.assert_matches_spec(random_stream(random.Random(seed), 250))

    def test_random_valid_streams_reach_deeper_books(self):
        for seed in (101, 102, 103):
            with self.subTest(seed=seed):
                self.assert_matches_spec(random_stream(random.Random(seed), 1500, invalid_share=0))

    def test_supplied_generator_families_after_every_event(self):
        for scenario in generate_orders.SCENARIOS:
            for seed, levels in ((42, 1000), (43, 3), (44, 40)):
                with self.subTest(scenario=scenario, seed=seed, levels=levels):
                    self.assert_matches_spec(list(generate_orders.events(scenario, 600, seed, levels)))

    def test_supplied_sample_files_with_periodic_book_comparison(self):
        for scenario in generate_orders.SCENARIOS:
            with self.subTest(scenario=scenario):
                events = read_events(DATA / f"{scenario}_10000.jsonl.gz")
                self.assertEqual(len(events), 10_000)
                books = self.assert_matches_spec(events, snapshot_every=500)
                self.assertEqual(books[0].InspectBook(), books[1].InspectBook())

    def test_supplied_files_match_their_recorded_checksums_and_generator(self):
        for scenario in generate_orders.SCENARIOS:
            with self.subTest(scenario=scenario):
                path = DATA / f"{scenario}_10000.jsonl.gz"
                meta = json.loads(Path(str(path) + ".metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"])
                regenerated = "".join(json.dumps(e, separators=(",", ":")) + "\n"
                                      for e in generate_orders.events(scenario, 10_000, 42, meta["levels"]))
                self.assertEqual(gzip.decompress(path.read_bytes()).decode(), regenerated)


class StorageBoundTests(BookTestCase):
    def test_churn_does_not_accumulate_inactive_entries(self):
        # 20,000 add/cancel pairs over 500 prices per side while three orders stay active.
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for i, price in enumerate((400, 401, 1600), 1):
                    book.ProcessEvent(limit(i, f"keep{i}", "BUY" if price < 1000 else "SELL", price, 1))
                seq, largest = 3, 0
                for i in range(20_000):
                    side = "BUY" if i % 2 else "SELL"
                    price = 999 - i % 500 if side == "BUY" else 1001 + i % 500
                    book.ProcessEvent(limit(seq + 1, f"c{i}", side, price, 2))
                    book.ProcessEvent(cancel(seq + 2, f"c{i}"))
                    seq += 2
                    if i % 97 == 0:
                        largest = max(largest, book.storage_stats()["stored_entries"])
                stats = book.storage_stats()
                self.assertEqual(book.active_orders(), 3)
                self.assertEqual(stats["active_orders"], 3)
                self.assertLess(max(largest, stats["stored_entries"]), 200,
                                "stored entries grow with submissions rather than active orders")
                book.check_invariants()
                self.assertEqual(book.ProcessEvent(market(seq + 1, "s", 5))["fills"],
                                 [fill("keep2", "s", 401, 1), fill("keep1", "s", 400, 1)])

    def test_book_returns_to_empty_after_mass_cancellation(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for i in range(1, 3001):
                    book.ProcessEvent(limit(i, f"o{i}", "BUY" if i % 2 else "SELL", 100 - i % 50 if i % 2 else 101 + i % 50, 1))
                order = list(range(1, 3001))
                random.Random(5).shuffle(order)
                for k, i in enumerate(order):
                    self.assertEqual(book.ProcessEvent(cancel(3001 + k, f"o{i}"))["status"], "cancelled")
                self.assertEqual(book.InspectBook(), [])
                self.assertEqual((book.active_orders(), book.price_levels()), (0, 0))
                self.assertLess(book.storage_stats()["stored_entries"], 200)
                book.check_invariants()


if __name__ == "__main__":
    unittest.main()
