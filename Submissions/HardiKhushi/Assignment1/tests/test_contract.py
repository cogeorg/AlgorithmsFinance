"""Independent expected results; this file is written before either engine."""
import copy
import importlib
import json
import os
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = os.environ.get("ORDERBOOK_VERSIONS", "baseline,revised").split(",")


def limit(seq, ident, side="BUY", price=100, qty=10):
    return dict(seq=seq, event_id=f"event-{seq}", type="LIMIT", order_id=ident,
                side=side, price_ticks=price, qty_units=qty)


def market(seq, qty, ident="sale"):
    return dict(seq=seq, event_id=f"event-{seq}", type="MARKET_SELL",
                order_id=ident, qty_units=qty)


def cancel(seq, target):
    return dict(seq=seq, event_id=f"event-{seq}", type="CANCEL", target_order_id=target)


def fill(maker, taker, price, qty):
    return dict(maker_id=maker, taker_id=taker, price_ticks=price, qty_units=qty)


def resting(ident, side, price, qty, seq):
    return dict(order_id=ident, side=side, price_ticks=price, qty_units=qty,
                arrival_seq=seq)


class Contract:
    def setUp(self):
        self.book = importlib.import_module(f"orderbook.{self.version}").OrderBook()

    def replay(self, rows):
        return [self.book.process(row) for row in rows]

    def test_empty_book(self):
        self.assertEqual(self.book.inspect(), [])
        self.assertEqual(self.book.process(market(1, 3)), dict(
            event_id="event-1", order_id="sale", status="unfilled",
            unfilled_qty_units=3, fills=[]))
        self.assertEqual(self.book.inspect(), [])

    def test_one_order_and_defensive_inspection(self):
        row = limit(1, "b")
        before = copy.deepcopy(row)
        self.assertEqual(self.book.AddLimitOrder(row), dict(
            event_id="event-1", order_id="b", status="resting",
            unfilled_qty_units=10, fills=[]))
        expected = [resting("b", "BUY", 100, 10, 1)]
        self.assertEqual(self.book.inspect(), expected)
        self.book.inspect()[0]["qty_units"] = 999
        self.assertEqual(self.book.inspect(), expected)
        self.assertEqual(row, before)

    def test_smaller_sale_and_subsequent_fill(self):
        self.book.process(limit(1, "b", qty=10))
        first = self.book.FillMarketSell(market(2, 3, "s1"))
        self.assertEqual(first["fills"], [fill("b", "s1", 100, 3)])
        self.assertEqual(first["status"], "filled")
        self.assertEqual(self.book.inspect(), [resting("b", "BUY", 100, 7, 1)])
        second = self.book.process(market(3, 7, "s2"))
        self.assertEqual(second["fills"], [fill("b", "s2", 100, 7)])
        self.assertEqual(second["status"], "filled")
        self.assertEqual(self.book.inspect(), [])
        self.assertEqual(first["fills"], [fill("b", "s1", 100, 3)])

    def test_exact_and_oversized_sales(self):
        for qty, status, residual in ((10, "filled", 0), (15, "partial", 5)):
            with self.subTest(qty=qty):
                self.setUp()
                self.book.process(limit(1, "b"))
                result = self.book.process(market(2, qty))
                self.assertEqual(result["fills"], [fill("b", "sale", 100, 10)])
                self.assertEqual(result["status"], status)
                self.assertEqual(result["unfilled_qty_units"], residual)
                self.assertEqual(self.book.inspect(), [])

    def test_fifo_ignores_identifier_spelling(self):
        self.replay([limit(1, "z", qty=4), limit(2, "a", qty=6)])
        result = self.book.process(market(3, 7))
        self.assertEqual(result["fills"], [fill("z", "sale", 100, 4),
                                            fill("a", "sale", 100, 3)])
        self.assertEqual(self.book.inspect(), [resting("a", "BUY", 100, 3, 2)])

    def test_best_price_before_arrival(self):
        self.replay([limit(1, "low", price=99, qty=2),
                     limit(2, "high", price=101, qty=3),
                     limit(3, "middle", price=100, qty=4)])
        result = self.book.process(market(4, 6))
        self.assertEqual(result["fills"], [fill("high", "sale", 101, 3),
                                            fill("middle", "sale", 100, 3)])
        self.assertEqual(self.book.inspect(), [resting("middle", "BUY", 100, 1, 3),
                                               resting("low", "BUY", 99, 2, 1)])

    def test_partial_maker_keeps_priority(self):
        self.replay([limit(1, "z", qty=5), market(2, 2, "s1"),
                     limit(3, "a", qty=9)])
        result = self.book.process(market(4, 4, "s2"))
        self.assertEqual(result["fills"], [fill("z", "s2", 100, 3),
                                            fill("a", "s2", 100, 1)])

    def test_cancel_active_then_repeat_and_unknown(self):
        self.book.process(limit(1, "b"))
        self.assertEqual(self.book.CancelOrder(cancel(2, "b")), dict(
            event_id="event-2", target_order_id="b", status="cancelled",
            cancelled_qty_units=10))
        for seq, target in ((3, "b"), (4, "unknown")):
            self.assertEqual(self.book.process(cancel(seq, target)), dict(
                event_id=f"event-{seq}", target_order_id=target, status="not_found",
                cancelled_qty_units=0))
        self.assertEqual(self.book.inspect(), [])

    def test_cancel_after_partial_and_full_fill(self):
        self.replay([limit(1, "b"), market(2, 3)])
        self.assertEqual(self.book.process(cancel(3, "b"))["cancelled_qty_units"], 7)
        self.replay([limit(4, "c"), market(5, 10, "s2")])
        self.assertEqual(self.book.process(cancel(6, "c"))["status"], "not_found")

    def test_cancel_middle_of_long_queue(self):
        for seq in range(1, 401):
            self.book.process(limit(seq, f"b{401-seq}", qty=1))
        self.book.process(cancel(401, "b201"))
        result = self.book.process(market(402, 500))
        self.assertEqual(result["fills"], [fill(f"b{i}", "sale", 100, 1)
                                           for i in range(400, 0, -1) if i != 201])
        self.assertEqual(result["unfilled_qty_units"], 101)
        self.assertEqual(self.book.inspect(), [])

    def test_crossing_buy_uses_resting_ask_prices(self):
        self.replay([limit(1, "a2", "SELL", 103, 4),
                     limit(2, "z", "SELL", 101, 3),
                     limit(3, "a", "SELL", 101, 2)])
        result = self.book.process(limit(4, "buy", "BUY", 102, 7))
        self.assertEqual(result["fills"], [fill("z", "buy", 101, 3),
                                            fill("a", "buy", 101, 2)])
        self.assertEqual(result["status"], "resting")
        self.assertEqual(result["unfilled_qty_units"], 2)
        self.assertEqual(self.book.inspect(), [resting("buy", "BUY", 102, 2, 4),
                                               resting("a2", "SELL", 103, 4, 1)])

    def test_crossing_sell_and_exact_spread(self):
        self.replay([limit(1, "b1", price=105, qty=3),
                     limit(2, "b2", price=102, qty=4)])
        result = self.book.process(limit(3, "sell", "SELL", 102, 9))
        self.assertEqual(result["fills"], [fill("b1", "sell", 105, 3),
                                            fill("b2", "sell", 102, 4)])
        self.assertEqual(self.book.inspect(), [resting("sell", "SELL", 102, 2, 3)])
        self.assertEqual(self.book.process(limit(4, "buy", price=102, qty=2))["status"],
                         "filled")
        self.assertEqual(self.book.inspect(), [])

    def test_non_crossing_and_canonical_order(self):
        self.replay([limit(1, "a2", "SELL", 110, 1),
                     limit(2, "b1", price=99, qty=2),
                     limit(3, "a1", "SELL", 109, 3),
                     limit(4, "b2", price=100, qty=4)])
        self.assertEqual(self.book.inspect(), [resting("b2", "BUY", 100, 4, 4),
            resting("b1", "BUY", 99, 2, 2), resting("a1", "SELL", 109, 3, 3),
            resting("a2", "SELL", 110, 1, 1)])

    def test_market_sale_does_not_touch_asks(self):
        self.book.process(limit(1, "ask", "SELL", 100, 8))
        self.assertEqual(self.book.process(market(2, 4))["status"], "unfilled")
        self.assertEqual(self.book.inspect(), [resting("ask", "SELL", 100, 8, 1)])

    def test_invalid_events_are_atomic_and_do_not_advance_sequence(self):
        self.book.process(limit(1, "live"))
        bad = [None, [], {}, limit(2, "x", side="bad"), limit(2, "live"),
               market(2, 2, "live"), dict(market(2, 2), type="UNKNOWN"),
               limit(1, "old"), limit(0, "zero"), limit(True, "boolseq"),
               dict(limit(2, "x"), side=[]), dict(limit(2, "x"), type=[])]
        for field in ("price_ticks", "qty_units"):
            for value in (0, -1, 1.5, "10", None, True, False):
                bad.append(dict(limit(2, "x"), **{field: value}))
        for field in ("event_id", "order_id", "seq", "qty_units", "price_ticks", "side"):
            row = limit(2, "x")
            del row[field]
            bad.append(row)
        bad += [dict(limit(2, "x"), order_id=[]), dict(limit(2, "x"), event_id=""),
                dict(cancel(2, "x"), target_order_id=[]), dict(market(2, 2), qty_units=0)]
        expected = self.book.inspect()
        for row in bad:
            with self.subTest(event=row):
                original = copy.deepcopy(row)
                result = self.book.process(row)
                self.assertEqual(result["status"], "rejected")
                self.assertTrue(result["reason"])
                self.assertEqual(self.book.inspect(), expected)
                self.assertEqual(row, original)
        self.assertEqual(self.book.process(limit(2, "good"))["status"], "resting")

    def test_unknown_cancel_advances_sequence(self):
        self.assertEqual(self.book.process(cancel(10, "unknown"))["status"], "not_found")
        self.assertEqual(self.book.process(limit(9, "old"))["status"], "rejected")

    def test_worked_example(self):
        expected = json.loads((ROOT / "data/worked_expected.json").read_text())
        results = self.replay([json.loads(line) for line in
                               (ROOT / "data/worked_example.jsonl").read_text().splitlines()])
        self.assertEqual(results[-1], expected["market_sell_result"])
        self.assertEqual(self.book.inspect(), expected["remaining_orders"])
        proceeds = sum(f["price_ticks"] * f["qty_units"] for f in results[-1]["fills"])
        self.assertEqual(proceeds, 3594000000000000)
        self.assertEqual(proceeds, expected["gross_proceeds_tick_units"])

    def test_generated_sales_against_independent_sorted_expectations(self):
        rng = random.Random(208)
        for trial in range(30):
            self.setUp()
            orders = [limit(i, f"id-{61-i}", price=rng.randrange(95, 106),
                            qty=rng.randrange(1, 20)) for i in range(1, 61)]
            self.replay(orders)
            qty = rng.randrange(1, 1500)
            remaining = qty
            expected_fills, expected_book = [], []
            for row in sorted(orders, key=lambda r: (-r["price_ticks"], r["seq"])):
                taken = min(remaining, row["qty_units"])
                if taken:
                    expected_fills.append(fill(row["order_id"], "sale", row["price_ticks"], taken))
                    remaining -= taken
                if row["qty_units"] > taken:
                    expected_book.append(resting(row["order_id"], "BUY", row["price_ticks"],
                                                 row["qty_units"] - taken, row["seq"]))
            result = self.book.process(market(61, qty))
            self.assertEqual(result["fills"], expected_fills)
            self.assertEqual(result["unfilled_qty_units"], remaining)
            self.assertEqual(self.book.inspect(), expected_book)


for version in VERSIONS:
    globals()[f"Test_{version}"] = type(f"Test_{version}", (Contract, unittest.TestCase),
                                       {"version": version})


class TestDifferential(unittest.TestCase):
    @unittest.skipUnless(len(VERSIONS) > 1, "revision not implemented in baseline-only stage")
    def test_generated_streams_every_event_and_conservation(self):
        from generate_orders import events
        engines = [importlib.import_module(f"orderbook.{v}").OrderBook for v in VERSIONS]
        for scenario in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
            for seed in (42, 43, 44):
                books = [engine() for engine in engines]
                for event in events(scenario, 300, seed, 12):
                    before = {r["order_id"]: r for r in books[0].inspect()}
                    results = [b.process(event) for b in books]
                    snapshots = [b.inspect() for b in books]
                    self.assertTrue(all(r == results[0] for r in results))
                    self.assertTrue(all(s == snapshots[0] for s in snapshots))
                    result, after = results[0], snapshots[0]
                    self.assertNotEqual(result["status"], "rejected")
                    if event["type"] != "CANCEL":
                        fills = result["fills"]
                        self.assertEqual(event["qty_units"], sum(f["qty_units"] for f in fills)
                                         + result["unfilled_qty_units"])
                        executed = {f["maker_id"]: f["qty_units"] for f in fills}
                        current = {r["order_id"]: r["qty_units"] for r in after}
                        for ident, old in before.items():
                            self.assertEqual(current.get(ident, 0), old["qty_units"]
                                             - executed.get(ident, 0))
                        if event["type"] == "MARKET_SELL":
                            self.assertNotIn(event["order_id"], current)
                    else:
                        old = before.get(event["target_order_id"], {}).get("qty_units", 0)
                        self.assertEqual(result["cancelled_qty_units"], old)
                    ids = [r["order_id"] for r in after]
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertTrue(all(r["qty_units"] > 0 for r in after))
                    bids = [r["price_ticks"] for r in after if r["side"] == "BUY"]
                    asks = [r["price_ticks"] for r in after if r["side"] == "SELL"]
                    if bids and asks:
                        self.assertLess(max(bids), min(asks))


if __name__ == "__main__":
    unittest.main()
