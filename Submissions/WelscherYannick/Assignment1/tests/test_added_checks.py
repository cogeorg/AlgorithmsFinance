"""Checks added after the revision (the original tests stay byte-identical to the tests-first commit).

They strengthen existing scenarios without changing any expected value:
  * every event of the long-queue, invalid-input, rejection and typed-entry scenarios also goes
    through the independent oracle (the original tests checked these results directly);
  * the five supplied samples must be present (a glob over missing files would pass vacuously);
  * Version B's secondary structures (order index, sorted key lists) must also be empty after
    cancellation churn and match the active book after mixed flow.
"""
import gzip
import json
import unittest
from pathlib import Path

from lob.book_a import BookA
from lob.book_b import BookB
from tests import oracle
from tests.test_spec import C, L, M, SpecMixin, fill, order

DATA = Path(__file__).resolve().parent.parent / "data"


class OracleCoverageMixin:
    """Re-runs scenarios whose original tests did not route every event through the oracle."""

    impl = None
    # Reuse only the helpers, not SpecMixin's tests (those already run in tests/test_spec.py).
    setUp = SpecMixin.setUp
    run_events = SpecMixin.run_events

    def typed(self, method, ev):
        before = self.book.inspect_book()
        r = getattr(self.book, method)(ev)
        if r["status"] == "rejected":  # wrong type for the entry point: the oracle cannot know that
            self.assertEqual(self.book.inspect_book(), before)
        else:
            self.last_seq = oracle.check_event(before, ev, r, self.book.inspect_book(), self.last_seq)
        return r

    def test_oracle_long_queue_including_build(self):
        n = 500
        self.run_events(*[L(i, f"q{(n - i):04d}", "BUY", 100, 1) for i in range(1, n + 1)])
        (r,) = self.run_events(M(n + 1, "s1", 300))
        self.assertEqual([f["maker_id"] for f in r["fills"]], [f"q{(n - i):04d}" for i in range(1, 301)])
        self.assertEqual(self.book.inspect_book()[0], order(f"q{n - 301:04d}", "BUY", 100, 1, 301))

    def test_oracle_invalid_inputs(self):
        self.run_events(L(1, "b1", "BUY", 100, 10), L(2, "a1", "SELL", 105, 10))
        bad = [
            {**L(3, "x", "BUY", 100, 1), "type": "MARKET_BUY"}, {**L(3, "x", "BUY", 100, 1), "type": None},
            L(3, "x", "HOLD", 100, 1), L(3, "x", "buy", 100, 1), L(3, "x", None, 100, 1),
            L(3, "x", "BUY", 0, 1), L(3, "x", "BUY", -100, 1), L(3, "x", "BUY", 100.5, 1),
            L(3, "x", "BUY", 100.0, 1), L(3, "x", "BUY", True, 1), L(3, "x", "BUY", "100", 1),
            L(3, "x", "BUY", None, 1), L(3, "x", "BUY", 100, 0), L(3, "x", "BUY", 100, -1),
            L(3, "x", "BUY", 100, 1.0), L(3, "x", "BUY", 100, True), L(3, "x", "BUY", 100, "1"),
            M(3, "s", 0), M(3, "s", 2.5), M(3, "s", False), M(3, "s", -3),
            L(3, "b1", "BUY", 99, 1), L(3, "a1", "BUY", 99, 1), M(3, "b1", 1),
            L(2, "x", "BUY", 99, 1), L(1, "x", "BUY", 99, 1),
            {**L(3, "x", "BUY", 99, 1), "seq": True}, {**L(3, "x", "BUY", 99, 1), "seq": 3.0},
            {**L(3, "x", "BUY", 99, 1), "seq": "3"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "price_ticks"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "order_id"},
            {k: v for k, v in L(3, "x", "BUY", 99, 1).items() if k != "seq"},
            {k: v for k, v in C(3, "b1").items() if k != "target_order_id"},
            "not an event",
        ]
        for ev in bad:
            with self.subTest(ev=ev):
                (r,) = self.run_events(ev)  # oracle re-derives that ev is invalid and the book is unchanged
                self.assertEqual(r["status"], "rejected")
        (r,) = self.run_events(L(3, "x", "BUY", 99, 1))
        self.assertEqual(r["status"], "resting")

    def test_oracle_rejection_reports_event_id(self):
        (r,) = self.run_events(L(1, "x", "BUY", 0, 1))
        self.assertEqual((r["status"], r["event_id"]), ("rejected", "ev1"))

    def test_oracle_typed_entry_points(self):
        self.assertEqual(self.typed("AddLimitOrder", L(1, "x", "BUY", -1, 1))["status"], "rejected")
        self.assertEqual(self.typed("AddLimitOrder", M(1, "s", 1))["status"], "rejected")
        self.assertEqual(self.typed("AddLimitOrder", L(1, "b1", "BUY", 100, 4))["status"], "resting")
        self.assertEqual(self.typed("FillMarketSell", M(2, "s1", 1))["fills"], [fill("b1", "s1", 100, 1)])
        r = self.typed("CancelOrder", C(3, "b1"))
        self.assertEqual((r["status"], r["cancelled_qty_units"]), ("cancelled", 3))


class TestOracleCoverageA(OracleCoverageMixin, unittest.TestCase):
    impl = BookA


class TestOracleCoverageB(OracleCoverageMixin, unittest.TestCase):
    impl = BookB


class TestDataAndStorage(unittest.TestCase):
    def test_five_supplied_samples_present_and_well_formed(self):
        paths = sorted(DATA.glob("*_10000.jsonl.gz"))
        self.assertEqual(len(paths), 5)
        for path in paths:
            with gzip.open(path, "rt") as fh:
                seqs = [json.loads(line)["seq"] for line in fh]
            self.assertEqual(len(seqs), 10000)
            self.assertTrue(all(b > a for a, b in zip(seqs, seqs[1:])))

    def _replay(self, name):
        with gzip.open(DATA / name, "rt") as fh:
            events = [json.loads(line) for line in fh]
        self.assertEqual(len(events), 10000)
        book = BookB()
        for ev in events:
            book.process(ev)
        return book

    def test_version_b_secondary_structures_empty_after_churn(self):
        counts = self._replay("cancel_churn_10000.jsonl.gz").storage_counts()
        self.assertEqual(counts, {"stored_orders": 0, "index_entries": 0, "stored_levels": 0, "level_keys": 0})

    def test_version_b_secondary_structures_match_book_after_mixed(self):
        book = self._replay("mixed_10000.jsonl.gz")
        orders = book.inspect_book()
        levels = {(o["side"], o["price_ticks"]) for o in orders}
        self.assertEqual(book.storage_counts(), {"stored_orders": len(orders), "index_entries": len(orders),
                                                 "stored_levels": len(levels), "level_keys": len(levels)})


if __name__ == "__main__":
    unittest.main()
