"""Hand-calculated specification tests, run unchanged against Version A and Version B.

Expected values are written out by hand from ASSIGNMENT.md; prices/quantities are small
integers so every number can be checked mentally. Each test also runs the independent
oracle (tests/oracle.py) after every event.
"""
import gzip
import json
import unittest
from pathlib import Path

from lob.book_a import BookA
from lob.book_b import BookB
from lob.common import format_usd, gross_proceeds_tick_units
from tests import oracle

DATA = Path(__file__).resolve().parent.parent / "data"


def L(seq, oid, side, price, qty):
    return {"seq": seq, "event_id": f"ev{seq}", "type": "LIMIT", "order_id": oid,
            "side": side, "price_ticks": price, "qty_units": qty}


def M(seq, oid, qty):
    return {"seq": seq, "event_id": f"ev{seq}", "type": "MARKET_SELL", "order_id": oid,
            "qty_units": qty}


def C(seq, target):
    return {"seq": seq, "event_id": f"ev{seq}", "type": "CANCEL", "target_order_id": target}


def fill(maker, taker, price, qty):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": price, "qty_units": qty}


def order(oid, side, price, qty, seq):
    return {"order_id": oid, "side": side, "price_ticks": price, "qty_units": qty,
            "arrival_seq": seq}


class SpecMixin:
    impl = None

    def setUp(self):
        self.book = self.impl()
        self.last_seq = 0

    def run_events(self, *events):
        """Process events, checking the independent oracle after each; return results."""
        results = []
        for ev in events:
            before = self.book.inspect_book()
            res = self.book.process(ev)
            after = self.book.inspect_book()
            self.last_seq = oracle.check_event(before, ev, res, after, self.last_seq)
            results.append(res)
        return results

    def assertBook(self, *orders):
        self.assertEqual(self.book.inspect_book(), list(orders))

    # --- empty book and single orders -------------------------------------------------
    def test_empty_book(self):
        self.assertEqual(self.book.inspect_book(), [])

    def test_market_sell_on_empty_book_is_unfilled(self):
        (r,) = self.run_events(M(1, "s1", 5))
        self.assertEqual(r, {"event_id": "ev1", "order_id": "s1", "status": "unfilled",
                             "unfilled_qty_units": 5, "fills": []})
        self.assertBook()

    def test_cancel_on_empty_book_is_not_found(self):
        (r,) = self.run_events(C(1, "b1"))
        self.assertEqual(r, {"event_id": "ev1", "target_order_id": "b1",
                             "status": "not_found", "cancelled_qty_units": 0})

    def test_single_limit_rests(self):
        (r,) = self.run_events(L(1, "b1", "BUY", 100, 10))
        self.assertEqual(r, {"event_id": "ev1", "order_id": "b1", "status": "resting",
                             "unfilled_qty_units": 10, "fills": []})
        self.assertBook(order("b1", "BUY", 100, 10, 1))

    # --- market sells: smaller, exact, oversized ---------------------------------------
    def test_sell_smaller_than_depth(self):
        _, r = self.run_events(L(1, "b1", "BUY", 100, 10), M(2, "s1", 4))
        self.assertEqual(r["status"], "filled")
        self.assertEqual(r["unfilled_qty_units"], 0)
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 4)])
        self.assertBook(order("b1", "BUY", 100, 6, 1))

    def test_sell_equal_to_depth(self):
        _, r = self.run_events(L(1, "b1", "BUY", 100, 10), M(2, "s1", 10))
        self.assertEqual(r["status"], "filled")
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 10)])
        self.assertBook()

    def test_sell_larger_than_depth_is_partial_and_residual_discarded(self):
        _, _, r = self.run_events(L(1, "b1", "BUY", 100, 10), L(2, "a1", "SELL", 105, 3),
                                  M(3, "s1", 15))
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["unfilled_qty_units"], 5)
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 10)])
        self.assertBook(order("a1", "SELL", 105, 3, 2))  # ask untouched, no market residual
        (c,) = self.run_events(C(4, "s1"))
        self.assertEqual(c["status"], "not_found")

    # --- priority ------------------------------------------------------------------------
    def test_several_makers_one_price_fifo(self):
        *_, r = self.run_events(L(1, "b1", "BUY", 100, 3), L(2, "b2", "BUY", 100, 4),
                                L(3, "b3", "BUY", 100, 5), M(4, "s1", 8))
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 3), fill("b2", "s1", 100, 4),
                                      fill("b3", "s1", 100, 1)])
        self.assertBook(order("b3", "BUY", 100, 4, 3))

    def test_several_price_levels_best_price_first(self):
        *_, r = self.run_events(L(1, "b1", "BUY", 99, 5), L(2, "b2", "BUY", 101, 5),
                                L(3, "b3", "BUY", 100, 5), M(4, "s1", 12))
        self.assertEqual(r["fills"], [fill("b2", "s1", 101, 5), fill("b3", "s1", 100, 5),
                                      fill("b1", "s1", 99, 2)])
        self.assertEqual(gross_proceeds_tick_units(r["fills"]), 505 + 500 + 198)
        self.assertBook(order("b1", "BUY", 99, 3, 1))

    def test_partial_fill_keeps_priority_and_later_order_queues_behind(self):
        self.run_events(L(1, "b1", "BUY", 100, 10), L(2, "b2", "BUY", 100, 10), M(3, "s1", 4))
        self.assertBook(order("b1", "BUY", 100, 6, 1), order("b2", "BUY", 100, 10, 2))
        _, r = self.run_events(L(4, "b3", "BUY", 100, 10), M(5, "s2", 10))
        self.assertEqual(r["fills"], [fill("b1", "s2", 100, 6), fill("b2", "s2", 100, 4)])
        self.assertBook(order("b2", "BUY", 100, 6, 2), order("b3", "BUY", 100, 10, 4))

    def test_identifier_spelling_gives_no_priority(self):
        *_, r = self.run_events(L(1, "z9", "BUY", 100, 5), L(2, "b10", "BUY", 100, 5),
                                L(3, "b2", "BUY", 100, 5), L(4, "a1", "BUY", 100, 5),
                                M(5, "s1", 12))
        self.assertEqual([f["maker_id"] for f in r["fills"]], ["z9", "b10", "b2"])
        self.assertBook(order("b2", "BUY", 100, 3, 3), order("a1", "BUY", 100, 5, 4))

    def test_arrival_seq_not_list_position_decides(self):
        # Gaps in seq are allowed; priority follows seq, which equals processing order.
        *_, r = self.run_events(L(10, "late_name_a", "BUY", 100, 1), L(50, "b", "BUY", 100, 1),
                                M(51, "s", 1))
        self.assertEqual(r["fills"], [fill("late_name_a", "s", 100, 1)])
        self.assertBook(order("b", "BUY", 100, 1, 50))

    def test_long_queue_at_one_price(self):
        n = 500
        events = [L(i, f"q{(n - i):04d}", "BUY", 100, 1) for i in range(1, n + 1)]
        self.book = self.impl()
        for ev in events:  # build quickly, then check the big sell with the oracle
            self.book.process(ev)
        self.last_seq = n
        (r,) = self.run_events(M(n + 1, "s1", 300))
        self.assertEqual([f["maker_id"] for f in r["fills"]],
                         [f"q{(n - i):04d}" for i in range(1, 301)])
        remaining = self.book.inspect_book()
        self.assertEqual(len(remaining), 200)
        self.assertEqual(remaining[0], order(f"q{n - 301:04d}", "BUY", 100, 1, 301))

    # --- cancellation --------------------------------------------------------------------
    def test_cancel_before_execution(self):
        _, c, r = self.run_events(L(1, "b1", "BUY", 100, 10), C(2, "b1"), M(3, "s1", 5))
        self.assertEqual(c, {"event_id": "ev2", "target_order_id": "b1",
                             "status": "cancelled", "cancelled_qty_units": 10})
        self.assertEqual(r["status"], "unfilled")
        self.assertBook()

    def test_cancel_after_partial_fill_removes_only_residual(self):
        _, _, c = self.run_events(L(1, "b1", "BUY", 100, 10), M(2, "s1", 4), C(3, "b1"))
        self.assertEqual(c["status"], "cancelled")
        self.assertEqual(c["cancelled_qty_units"], 6)
        self.assertBook()

    def test_cancel_after_full_fill_is_not_found(self):
        _, _, c = self.run_events(L(1, "b1", "BUY", 100, 10), M(2, "s1", 10), C(3, "b1"))
        self.assertEqual(c["status"], "not_found")
        self.assertEqual(c["cancelled_qty_units"], 0)

    def test_repeated_cancel_is_not_found(self):
        _, c1, c2 = self.run_events(L(1, "a1", "SELL", 105, 7), C(2, "a1"), C(3, "a1"))
        self.assertEqual((c1["status"], c1["cancelled_qty_units"]), ("cancelled", 7))
        self.assertEqual((c2["status"], c2["cancelled_qty_units"]), ("not_found", 0))

    def test_unknown_cancel_is_valid_and_advances_seq(self):
        _, c, r = self.run_events(L(1, "b1", "BUY", 100, 10), C(2, "zzz"), L(2, "b2", "BUY", 99, 1))
        self.assertEqual(c["status"], "not_found")
        self.assertEqual(r["status"], "rejected")  # seq 2 was consumed by the valid cancel
        self.assertBook(order("b1", "BUY", 100, 10, 1))

    def test_cancel_of_fully_filled_incoming_limit_is_not_found(self):
        _, r, c = self.run_events(L(1, "a1", "SELL", 100, 5), L(2, "b1", "BUY", 100, 5), C(3, "b1"))
        self.assertEqual(r["status"], "filled")
        self.assertEqual(c["status"], "not_found")

    def test_cancel_middle_of_queue_keeps_others_in_order(self):
        *_, r = self.run_events(L(1, "b1", "BUY", 100, 2), L(2, "b2", "BUY", 100, 2),
                                L(3, "b3", "BUY", 100, 2), C(4, "b2"), M(5, "s1", 3))
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 2), fill("b3", "s1", 100, 1)])

    # --- crossing limit orders --------------------------------------------------------------
    def test_crossing_limit_buy_price_then_time_at_resting_price(self):
        *_, r = self.run_events(L(1, "a1", "SELL", 101, 5), L(2, "a2", "SELL", 102, 5),
                                L(3, "a3", "SELL", 101, 5), L(4, "b1", "BUY", 102, 12))
        self.assertEqual(r, {"event_id": "ev4", "order_id": "b1", "status": "filled",
                             "unfilled_qty_units": 0,
                             "fills": [fill("a1", "b1", 101, 5), fill("a3", "b1", 101, 5),
                                       fill("a2", "b1", 102, 2)]})
        self.assertBook(order("a2", "SELL", 102, 3, 2))

    def test_crossing_limit_buy_residual_rests_with_own_seq(self):
        _, r = self.run_events(L(1, "a1", "SELL", 101, 5), L(2, "b1", "BUY", 103, 8))
        self.assertEqual(r["status"], "resting")
        self.assertEqual(r["unfilled_qty_units"], 3)
        self.assertEqual(r["fills"], [fill("a1", "b1", 101, 5)])
        self.assertBook(order("b1", "BUY", 103, 3, 2))

    def test_crossing_limit_sell_stops_at_limit_and_rests(self):
        *_, r = self.run_events(L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 99, 5),
                                L(3, "b3", "BUY", 98, 5), L(4, "a1", "SELL", 99, 12))
        self.assertEqual(r["fills"], [fill("b1", "a1", 100, 5), fill("b2", "a1", 99, 5)])
        self.assertEqual((r["status"], r["unfilled_qty_units"]), ("resting", 2))
        self.assertBook(order("b3", "BUY", 98, 5, 3), order("a1", "SELL", 99, 2, 4))

    def test_limit_at_exactly_best_opposite_price_crosses(self):
        _, r = self.run_events(L(1, "b1", "BUY", 100, 5), L(2, "a1", "SELL", 100, 3))
        self.assertEqual(r["fills"], [fill("b1", "a1", 100, 3)])
        self.assertEqual(r["status"], "filled")
        self.assertBook(order("b1", "BUY", 100, 2, 1))

    def test_noncrossing_limits_both_rest(self):
        self.run_events(L(1, "b1", "BUY", 100, 5), L(2, "a1", "SELL", 101, 5),
                        L(3, "b2", "BUY", 100, 1), L(4, "a2", "SELL", 102, 1))
        self.assertBook(order("b1", "BUY", 100, 5, 1), order("b2", "BUY", 100, 1, 3),
                        order("a1", "SELL", 101, 5, 2), order("a2", "SELL", 102, 1, 4))

    def test_market_sell_never_touches_asks(self):
        *_, r = self.run_events(L(1, "a1", "SELL", 50, 5), L(2, "b1", "BUY", 40, 2), M(3, "s1", 5))
        self.assertEqual(r["fills"], [fill("b1", "s1", 40, 2)])
        self.assertEqual(r["status"], "partial")
        self.assertBook(order("a1", "SELL", 50, 5, 1))

    # --- validation: rejected events leave everything unchanged ---------------------------
    def _assert_rejected(self, ev):
        before = self.book.inspect_book()
        r = self.book.process(ev)
        self.assertEqual(r["status"], "rejected", ev)
        self.assertTrue(isinstance(r.get("reason"), str) and r["reason"])
        self.assertEqual(self.book.inspect_book(), before)

    def test_invalid_inputs_rejected_without_state_change(self):
        self.run_events(L(1, "b1", "BUY", 100, 10), L(2, "a1", "SELL", 105, 10))
        bad = [
            {**L(3, "x", "BUY", 100, 1), "type": "MARKET_BUY"},
            {**L(3, "x", "BUY", 100, 1), "type": None},
            L(3, "x", "HOLD", 100, 1), L(3, "x", "buy", 100, 1), L(3, "x", None, 100, 1),
            L(3, "x", "BUY", 0, 1), L(3, "x", "BUY", -100, 1), L(3, "x", "BUY", 100.5, 1),
            L(3, "x", "BUY", 100.0, 1), L(3, "x", "BUY", True, 1), L(3, "x", "BUY", "100", 1),
            L(3, "x", "BUY", None, 1),
            L(3, "x", "BUY", 100, 0), L(3, "x", "BUY", 100, -1), L(3, "x", "BUY", 100, 1.0),
            L(3, "x", "BUY", 100, True), L(3, "x", "BUY", 100, "1"),
            M(3, "s", 0), M(3, "s", 2.5), M(3, "s", False), M(3, "s", -3),
            L(3, "b1", "BUY", 99, 1),       # duplicate live identifier (same side)
            L(3, "a1", "BUY", 99, 1),       # duplicate live identifier (other side)
            M(3, "b1", 1),                  # market sell reusing a live identifier
            L(2, "x", "BUY", 99, 1),        # nonincreasing seq (equal)
            L(1, "x", "BUY", 99, 1),        # nonincreasing seq (lower)
            {**L(3, "x", "BUY", 99, 1), "seq": True},
            {**L(3, "x", "BUY", 99, 1), "seq": 3.0},
            {**L(3, "x", "BUY", 99, 1), "seq": "3"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "price_ticks"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "order_id"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "seq"},
            {k: v for k, v in C(3, "b1").items() if k != "target_order_id"},
            "not an event",
        ]
        for ev in bad:
            with self.subTest(ev=ev):
                self._assert_rejected(ev)
        # Rejections did not advance the last accepted seq: seq 3 is still usable.
        (r,) = self.run_events(L(3, "x", "BUY", 99, 1))
        self.assertEqual(r["status"], "resting")

    def test_rejection_reports_event_id_when_available(self):
        r = self.book.process(L(1, "x", "BUY", 0, 1))
        self.assertEqual((r["status"], r["event_id"]), ("rejected", "ev1"))

    def test_typed_entry_points_validate_too(self):
        r = self.book.AddLimitOrder(L(1, "x", "BUY", -1, 1))
        self.assertEqual(r["status"], "rejected")
        r = self.book.AddLimitOrder(M(1, "s", 1))  # wrong type for this entry point
        self.assertEqual(r["status"], "rejected")
        self.assertEqual(self.book.AddLimitOrder(L(1, "b1", "BUY", 100, 4))["status"], "resting")
        r = self.book.FillMarketSell(M(2, "s1", 1))
        self.assertEqual(r["fills"], [fill("b1", "s1", 100, 1)])
        r = self.book.CancelOrder(C(3, "b1"))
        self.assertEqual((r["status"], r["cancelled_qty_units"]), ("cancelled", 3))

    # --- worked example from the package ------------------------------------------------------
    def test_worked_example(self):
        events = [json.loads(line) for line in (DATA / "worked_example.jsonl").read_text().splitlines()]
        expected = json.loads((DATA / "worked_expected.json").read_text())
        results = self.run_events(*events)
        self.assertEqual(results[-1], expected["market_sell_result"])
        self.assertEqual(self.book.inspect_book(), expected["remaining_orders"])
        total = gross_proceeds_tick_units(results[-1]["fills"])
        self.assertEqual(total, expected["gross_proceeds_tick_units"])
        self.assertEqual(format_usd(total), expected["gross_proceeds_usd"])
        # Hand check from the slides: 1, 1, 3, 1 BTC at 60,000 / 60,000 / 59,900 / 59,700.
        self.assertEqual(total, (60000 + 60000 + 3 * 59900 + 59700) * 100 * 10**8)

    # --- small generated streams, oracle after every event -------------------------------------
    def test_random_streams_against_oracle(self):
        from tests.streams import random_stream
        for seed in range(60):
            with self.subTest(seed=seed):
                self.setUp()
                self.run_events(*random_stream(seed, n=150, prices=1 + seed % 5))


class TestSpecA(SpecMixin, unittest.TestCase):
    impl = BookA


class TestSpecB(SpecMixin, unittest.TestCase):
    impl = BookB


class TestHelpers(unittest.TestCase):
    def test_format_usd_rounds_only_for_display(self):
        self.assertEqual(format_usd(3594000000000000), "359400.00")
        self.assertEqual(format_usd(1), "0.00")
        self.assertEqual(format_usd(10**8), "0.01")
        self.assertEqual(format_usd(0), "0.00")

    def test_supplied_samples_are_well_formed(self):
        for path in sorted(DATA.glob("*_10000.jsonl.gz")):
            with gzip.open(path, "rt") as fh:
                seqs = [json.loads(line)["seq"] for line in fh]
            self.assertEqual(len(seqs), 10000)
            self.assertTrue(all(b > a for a, b in zip(seqs, seqs[1:])))


if __name__ == "__main__":
    unittest.main()
