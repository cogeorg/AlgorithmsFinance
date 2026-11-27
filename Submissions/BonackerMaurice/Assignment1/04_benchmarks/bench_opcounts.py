"""Operation counts: a separate diagnostic run on small sizes (not timed).

Called by run_benchmark.py (phase "opcounts"). One child per (dataset,
version) replays the file on a counting subclass of the version; the engine
modules are not changed. Results are checked against the manifest (fills,
final book size), so the counters describe the real replay.

Version A counters (elements of the one order list visited):
    is_live_scanned      validation's duplicate-id scan (stops at a match)
    best_index_scanned   _best_index: every call scans the whole list
    cancel_scanned       CancelOrder's search for the target (stops at a match)
    cancel_shift         list elements moved by `del orders[i]` in a cancel
    orders_scanned       the sum of the three scans
Version B counters:
    best_price_calls, heap_stale_pops (B-heap), levels_created,
    levels_removed_by_match, levels_removed_by_cancel, heap_rebuilds,
    deque_compactions, dead_dropped_by_compaction, dead_dropped_with_level,
    queue_pops (deque.popleft), makers_exhausted, dead_entries_popped
    (= queue_pops - makers_exhausted)
For every counter: the total, the mean per event and the maximum in one event.

Writes <out>/opcounts.csv.

Child mode (internal): bench_opcounts.py --child <file> <version>
"""

import argparse
from collections import deque

from bench_common import (VERSIONS, book_class, dataset_name, emit, load_events,
                          read_manifest, rel, rotated, run_child, stop_note, write_rows)

FIELDS = ["version", "scenario", "seed", "events", "counter", "total", "per_event",
          "max_in_one_event", "status", "note"]
POPS = [0]


class CountingDeque(deque):
    def popleft(self):
        POPS[0] += 1
        return super().popleft()


def _position(orders, order_id):
    for i, o in enumerate(orders):
        if o["order_id"] == order_id:
            return i
    return None


def counting_a():
    base = book_class("a")

    class CountingA(base):
        def __init__(self):
            super().__init__()
            self.ops = dict.fromkeys(["is_live_calls", "is_live_scanned", "best_index_calls",
                                      "best_index_scanned", "cancel_scanned",
                                      "cancel_shift"], 0)

        def _is_live(self, order_id):
            pos = _position(self.orders, order_id)
            self.ops["is_live_calls"] += 1
            self.ops["is_live_scanned"] += len(self.orders) if pos is None else pos + 1
            return super()._is_live(order_id)

        def _best_index(self, maker_side):
            self.ops["best_index_calls"] += 1
            self.ops["best_index_scanned"] += len(self.orders)
            return super()._best_index(maker_side)

        def CancelOrder(self, event_id, target_order_id):
            pos = _position(self.orders, target_order_id)
            n = len(self.orders)
            self.ops["cancel_scanned"] += n if pos is None else pos + 1
            self.ops["cancel_shift"] += 0 if pos is None else n - pos - 1
            return super().CancelOrder(event_id, target_order_id)

    return CountingA


def counting_b(version):
    import lob_b_common
    lob_b_common.deque = CountingDeque        # this child process only
    base = book_class(version)

    class CountingB(base):
        def __init__(self):
            self.ops = dict.fromkeys(["best_price_calls", "heap_stale_pops", "levels_created",
                                      "levels_removed_by_match", "levels_removed_by_cancel",
                                      "heap_rebuilds", "deque_compactions",
                                      "dead_dropped_by_compaction", "dead_dropped_with_level"],
                                     0)
            super().__init__()

        def _heap_len(self, side):
            heaps = getattr(self, "_heaps", None)
            return len(heaps[side]) if heaps is not None else 0

        def _best_price(self, side):
            self.ops["best_price_calls"] += 1
            before = self._heap_len(side)
            price = super()._best_price(side)
            self.ops["heap_stale_pops"] += before - self._heap_len(side)
            return price

        def _index_add(self, side, price):
            self.ops["levels_created"] += 1
            super()._index_add(side, price)

        def _count_rebuild(self, remove, side, price):
            heaps = getattr(self, "_heaps", None)
            before = heaps[side] if heaps is not None else None
            remove(side, price)
            if heaps is not None and self._heaps[side] is not before:
                self.ops["heap_rebuilds"] += 1

        def _index_remove(self, side, price):
            self.ops["levels_removed_by_cancel"] += 1
            self._count_rebuild(super()._index_remove, side, price)

        def _index_remove_best(self, side, price):
            self.ops["levels_removed_by_match"] += 1
            self._count_rebuild(super()._index_remove_best, side, price)

        def _tidy(self, side, price, level, best):
            queue, n, empty = level.queue, len(level.queue), level.live_count == 0
            super()._tidy(side, price, level, best)
            if empty:
                self.ops["dead_dropped_with_level"] += n        # all left were dead
            elif level.queue is not queue:
                self.ops["deque_compactions"] += 1
                self.ops["dead_dropped_by_compaction"] += n - len(level.queue)

    return CountingB


def child(path, version):
    events = load_events(path)
    cls = counting_a() if version == "a" else counting_b(version)
    emit(start=["opcounts"])
    book = cls()
    totals, maxima = {}, {}
    fills = 0
    for event in events:
        before = dict(book.ops)
        pops_before = POPS[0]
        result = book.process_event(event)
        made = result.get("fills", ())
        fills += len(made)
        step = {k: v - before[k] for k, v in book.ops.items()}
        if version == "a":
            step["orders_scanned"] = (step["is_live_scanned"] + step["best_index_scanned"]
                                      + step["cancel_scanned"])
        else:
            step["queue_pops"] = POPS[0] - pops_before
            step["makers_exhausted"] = sum(f["maker_id"] not in book.orders for f in made)
            step["dead_entries_popped"] = step["queue_pops"] - step["makers_exhausted"]
        for k, v in step.items():
            totals[k] = totals.get(k, 0) + v
            maxima[k] = max(maxima.get(k, 0), v)
    emit(stop=["opcounts"])
    emit(result={"totals": totals, "maxima": maxima, "fills": fills,
                 "final_book_size": len(book.inspect_book())})


def run(cfg):
    out = cfg.out / "opcounts.csv"
    rows = []
    manifest = {d["dataset"]: d for d in read_manifest(cfg)}
    cells = [manifest[dataset_name(s, m, cfg.diag_seed, 1000)]
             for m in cfg.opcount_sizes for s in ("buildup", "crowded", "mixed", "sweep",
                                                  "cancel_churn")]
    for i, ds in enumerate(cells):
        for version in rotated(VERSIONS, i):
            got = {}
            stopped = run_child("bench_opcounts.py", [ds["file"], version], cfg.time_limit,
                                lambda msg: got.update(msg.get("result", {})) and False)
            key = {"version": version, "scenario": ds["scenario"], "seed": ds["seed"],
                   "events": ds["events"]}
            if stopped:
                rows.append({**key, "counter": "", "status": "stopped",
                             "note": stop_note(stopped, ["opcounts"], cfg.time_limit)})
            else:
                ok = (got["fills"] == ds["fills"]
                      and got["final_book_size"] == ds["final_book_size"])
                for counter, total in got["totals"].items():
                    rows.append({**key, "counter": counter, "total": total,
                                 "per_event": f"{total / ds['events']:.3f}",
                                 "max_in_one_event": got["maxima"][counter],
                                 "status": "ok" if ok else "mismatch",
                                 "note": "" if ok else "fills or final book differ from manifest"})
            write_rows(out, FIELDS, rows)
            print(f"  opcount {ds['dataset']:34s} {version:8s} "
                  f"{'STOPPED' if stopped else 'ok'}", flush=True)
    print(f"  wrote {rel(out)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=2, required=True)
    args = parser.parse_args()
    child(*args.child)


if __name__ == "__main__":
    main()
