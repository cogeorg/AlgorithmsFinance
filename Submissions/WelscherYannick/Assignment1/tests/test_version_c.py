"""Version C (experiment in bench/variants/book_c_deque.py): same specification tests and oracle as
A and B, C vs B after every event, a cancel-heavy stress test with id reuse that triggers compaction,
and C's own structural invariants (bounded stale entries)."""
import gzip
import json
import random
import unittest
from pathlib import Path

from bench.variants.book_c_deque import BookC
from lob.book_b import BookB
from tests import test_added_checks as added
from tests.streams import random_stream
from tests.test_spec import SpecMixin

ROOT = Path(__file__).resolve().parent.parent


class TestSpecC(SpecMixin, unittest.TestCase):
    impl = BookC


class TestOracleCoverageC(added.OracleCoverageMixin, unittest.TestCase):
    impl = BookC


def read(path):
    with gzip.open(path, "rt") as fh:
        return [json.loads(line) for line in fh]


class TestCvsB(unittest.TestCase):
    def test_random_streams_every_event(self):
        for seed in range(500, 700):
            with self.subTest(seed=seed):
                b, c = BookB(), BookC()
                for ev in random_stream(seed, n=400, prices=1 + seed % 4, invalid_rate=0.08):
                    self.assertEqual(b.process(ev), c.process(ev), ev)
                    self.assertEqual(b.inspect_book(), c.inspect_book(), ev)
                    c.check_internal()

    def test_cancel_heavy_streams_force_compaction(self):
        # many cancels on a few prices with ids reused after cancel: exercises lazy deletion + compaction
        for seed in range(40):
            rng = random.Random(seed)
            b, c = BookB(), BookC()
            live, seq = [], 0
            for i in range(3000):
                seq += 1
                r = rng.random()
                if r < 0.45 and live:
                    ev = {"seq": seq, "event_id": f"e{i}", "type": "CANCEL", "target_order_id": live.pop(rng.randrange(len(live)))}
                elif r < 0.55:
                    ev = {"seq": seq, "event_id": f"e{i}", "type": "MARKET_SELL", "order_id": f"m{i}", "qty_units": rng.randint(1, 30)}
                else:
                    oid = f"o{rng.randrange(60)}"  # small id space: ids are reused once not live
                    ev = {"seq": seq, "event_id": f"e{i}", "type": "LIMIT", "order_id": oid, "side": "BUY",
                          "price_ticks": 100 - rng.randrange(2), "qty_units": rng.randint(1, 10)}
                rb, rc = b.process(ev), c.process(ev)
                self.assertEqual(rb, rc, ev)
                if ev["type"] == "LIMIT" and rb["status"] == "resting":
                    live.append(ev["order_id"])
                live = [x for x in live if x in b.index]
                c.check_internal()
            self.assertEqual(b.inspect_book(), c.inspect_book())

    def test_supplied_samples_every_event(self):
        for path in sorted((ROOT / "data").glob("*_10000.jsonl.gz")):
            with self.subTest(sample=path.name):
                b, c = BookB(), BookC()
                for i, ev in enumerate(read(path)):
                    self.assertEqual(b.process(ev), c.process(ev))
                    if i % 200 == 0:
                        self.assertEqual(b.inspect_book(), c.inspect_book())
                        c.check_internal()
                self.assertEqual(b.inspect_book(), c.inspect_book())
                c.check_internal()

    def test_churn_leaves_nothing(self):
        c = BookC()
        for ev in read(ROOT / "data" / "cancel_churn_10000.jsonl.gz"):
            c.process(ev)
        self.assertEqual(c.storage_counts(), {"stored_orders": 0, "stale_entries": 0, "index_entries": 0,
                                              "stored_levels": 0, "level_keys": 0})


if __name__ == "__main__":
    unittest.main()
