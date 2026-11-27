#!/usr/bin/env python3
"""Operation counts (separate from timing): explains WHY the versions scale differently.

Instrumented subclasses count work without changing behaviour:
  Version A: list entries visited by the duplicate-id scan, the best-price scan and the
             cancel scan (each visited Order object = 1 step).
  Version B: hash lookups are O(1) and counted per event; additionally new / removed price
             levels and the number of keys shifted by list insert/delete (memmove length).
Both: maker fills F. Counts are exact for the given input and independent of the machine.
"""
from bisect import bisect_left

from _util import RESULTS, SCENARIOS, input_path, write_csv
from lob.book_a import BookA
from lob.book_b import BookB
from lob.common import read_events


class CountingA(BookA):
    def __init__(self):
        super().__init__()
        self.steps = 0

    def _is_live(self, order_id):
        # mirrors BookA._is_live: visits entries until the id is found (all if absent)
        for n, o in enumerate(self.bids, 1):
            if o.order_id == order_id:
                self.steps += n
                return True
        for n, o in enumerate(self.asks, 1):
            if o.order_id == order_id:
                self.steps += len(self.bids) + n
                return True
        self.steps += len(self.bids) + len(self.asks)
        return False

    def _best_index(self, orders, highest):
        self.steps += len(orders)
        return super()._best_index(orders, highest)

    def _cancel(self, target_order_id):
        # count the entries BookA._cancel visits, then let it do the actual removal
        visited = 0
        for book in (self.bids, self.asks):
            for o in book:
                visited += 1
                if o.order_id == target_order_id:
                    self.steps += visited
                    return super()._cancel(target_order_id)
        self.steps += visited
        return None


class CountingB(BookB):
    def __init__(self):
        super().__init__()
        self.level_adds = self.level_removes = self.keys_shifted = 0

    def _add_level(self, levels, keys, price, key):
        self.level_adds += 1
        self.keys_shifted += len(keys) - bisect_left(keys, key)
        return super()._add_level(levels, keys, price, key)

    def _remove_level(self, levels, keys, price, key):
        self.level_removes += 1
        self.keys_shifted += len(keys) - 1 - bisect_left(keys, key)
        super()._remove_level(levels, keys, price, key)


def main():
    rows = []
    for n in (1000, 10000, 100000):
        for scenario in SCENARIOS:
            events = read_events(input_path(scenario, n, 42))
            b = CountingB()
            fills = 0
            for ev in events:
                fills += len(b.process(ev).get("fills", ()))
            # levels removed while matching (best level popped, no shift) are not routed
            # through _remove_level; they cost O(1) and are counted via fills/levels.
            base = {"run_kind": "counts", "scenario": scenario, "seed": 42, "events": n, "levels": 1000,
                    "fills": fills, "phase": "replay"}
            rows.append({**base, "version": "B", "work_steps": len(events) + fills + b.keys_shifted,
                         "note": f"events {len(events)} (O(1) dict ops each) + fills {fills} + keys shifted "
                                 f"{b.keys_shifted}; levels created {b.level_adds}, removed by cancel "
                                 f"{b.level_removes}"})
            if n <= 10000 or scenario in ("mixed", "cancel_churn"):
                a = CountingA()
                for ev in events:
                    a.process(ev)
                rows.append({**base, "version": "A", "work_steps": a.steps,
                             "note": f"list entries visited by linear scans; per event {a.steps / len(events):.1f}"})
                print(f"{scenario:12s} {n:>7d}: A steps {a.steps:>14,d}  B steps {len(events) + fills + b.keys_shifted:>10,d}", flush=True)
            else:
                rows.append({**base, "version": "A", "status": "not_attempted",
                             "note": "counting run skipped: replay is O(M^2) for this scenario"})
                print(f"{scenario:12s} {n:>7d}: A not attempted  B steps {len(events) + fills + b.keys_shifted:>10,d}", flush=True)
    write_csv(RESULTS / "op_counts.csv", rows)


if __name__ == "__main__":
    main()
