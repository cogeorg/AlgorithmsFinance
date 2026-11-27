"""Adversarial tests, added after the first implementation passed test_orderbook.py.

Nothing in test_orderbook.py was changed or weakened. This file attacks the
engines from angles the first suite did not cover:

  * exhaustive enumeration of every short event sequence over a small alphabet;
  * state-aware fuzzing that aims at the best level, at queue heads and at dead identifiers;
  * the internal thresholds of version B (stale-heap rebuild, capacity release);
  * metamorphic properties (relabelling, scaling, shifting, rebuilding from a snapshot);
  * hostile values and damaged input files;
  * deliberately broken engines ("mutants") that the checks must detect.
"""
import gzip
import itertools
import json
from pathlib import Path
import random
import tempfile
import unittest

import book_b
import book_b1
from book_a import OrderBookA, KEY, SEQ
from book_b import OrderBookB
from book_b1 import OrderBookB1
from events import read_events
from test_orderbook import (BookTestCase, VERSIONS, canonical, cancel, cancelled, fill, limit, market,
                            random_stream, row, spec_step, submitted, without_reason)

HERE = Path(__file__).resolve().parent


class AdversarialCase(BookTestCase):
    def assert_classes_match_spec(self, classes, events, snapshot_every=1):
        """Each class against the specification model: results, books, invariants, conservation.

        snapshot_every=0 is "hands off": nothing but ProcessEvent touches the book until the
        last event. Inspection calls discard stale heap entries as a side effect, so inspecting
        after every event would never let a matching step meet one.
        """
        books = [cls() for cls in classes]
        rows, last_seq = [], 0
        for index, event in enumerate(events):
            full = (snapshot_every == 1 or (snapshot_every and index % snapshot_every == 0)
                    or index == len(events) - 1)
            before = canonical([dict(r) for r in rows]) if snapshot_every == 1 else None
            expected, last_seq = spec_step(rows, last_seq, event)
            for book in books:
                result = book.ProcessEvent(event)
                self.assertEqual(without_reason(result), expected, f"{type(book).__name__} event index {index}")
                self.assertEqual(book.last_seq, last_seq, f"{type(book).__name__} last_seq at index {index}")
                if snapshot_every:
                    self.assertEqual(book.active_orders(), len(rows))
                if full:
                    wanted = canonical([dict(r) for r in rows])
                    self.assertEqual(book.InspectBook(), wanted, f"{type(book).__name__} book at index {index}")
                    book.check_invariants()
                    bids = [r["price_ticks"] for r in wanted if r["side"] == "BUY"]
                    asks = [r["price_ticks"] for r in wanted if r["side"] == "SELL"]
                    self.assertEqual(book.best_bid(), max(bids, default=None))
                    self.assertEqual(book.best_ask(), min(asks, default=None))
                    self.assertEqual(book.price_levels(), len(set(bids)) + len(set(asks)))
                    self.assertEqual(book.storage_stats()["active_orders"], len(wanted))
                    if before is not None:
                        self.assert_snapshot_invariants(wanted)
                        self.assert_conservation(before, event, result, wanted)
        return books, rows


# ------------------------------------------------------ exhaustive small worlds
def alphabet_event(symbol, seq, issued):
    kind = symbol[0]
    if kind == "L":
        _, side, price, qty = symbol
        issued.append(f"o{seq}")
        return limit(seq, f"o{seq}", side, price, qty)
    if kind == "M":
        return market(seq, f"m{seq}", symbol[1])
    target = issued[-symbol[1]] if len(issued) >= symbol[1] else "nobody"
    return cancel(seq, target)


ALPHABET = ([("L", side, price, qty) for side in ("BUY", "SELL") for price in (10, 11) for qty in (1, 2)]
            + [("M", 1), ("M", 3), ("C", 1), ("C", 2)])


class ExhaustiveTests(AdversarialCase):
    def test_every_sequence_of_four_events(self):
        # 12^4 = 20,736 sequences: two prices where both sides overlap, sizes 1-2, sales 1 or 3,
        # cancellation of the latest or the previous submission (alive or not).
        count = 0
        for symbols in itertools.product(ALPHABET, repeat=4):
            issued, rows, last_seq = [], [], 0
            books = [cls() for cls in VERSIONS]
            for seq, symbol in enumerate(symbols, 1):
                event = alphabet_event(symbol, seq, issued)
                expected, last_seq = spec_step(rows, last_seq, event)
                for book in books:
                    if book.ProcessEvent(event) != expected:
                        self.fail(f"{type(book).__name__} differs on {symbols} at event {seq}")
            wanted = canonical(rows)
            for book in books:
                if book.InspectBook() != wanted:
                    self.fail(f"{type(book).__name__} book differs after {symbols}")
                book.check_invariants()
            count += 1
        self.assertEqual(count, 12 ** 4)

    def test_sampled_sequences_of_nine_events(self):
        rng = random.Random(9)
        for _ in range(4000):
            symbols = [rng.choice(ALPHABET) for _ in range(9)]
            issued = []
            events = [alphabet_event(symbol, seq, issued) for seq, symbol in enumerate(symbols, 1)]
            self.assert_classes_match_spec(VERSIONS, events, snapshot_every=3)


# --------------------------------------------------------- state-aware fuzzing
def hunting_stream(rng, count, prices=(95, 105), big=False):
    """Generate against the live specification state so that events aim at weak points."""
    rows, last_seq, events, dead, seq = [], 0, [], [], 0
    low, high = prices
    for _ in range(count):
        seq += 1
        bids = canonical([r for r in rows if r["side"] == "BUY"])
        asks = canonical([r for r in rows if r["side"] == "SELL"])
        qty = rng.choice((1, 2, 10**18, 10**18 + 1)) if big else rng.randint(1, 5)
        move = rng.randrange(16)
        if move == 0 and bids:                         # cancel the order at the very front of the bids
            event = cancel(seq, bids[0]["order_id"])
        elif move == 1 and asks:
            event = cancel(seq, asks[0]["order_id"])
        elif move == 2 and bids:                       # cancel the last order of the best level
            best = [r for r in bids if r["price_ticks"] == bids[0]["price_ticks"]]
            event = cancel(seq, best[-1]["order_id"])
        elif move == 3 and rows:                       # cancel anywhere
            event = cancel(seq, rng.choice(rows)["order_id"])
        elif move == 4 and dead:                       # cancel something that is gone
            event = cancel(seq, rng.choice(dead))
        elif move == 5 and bids:                       # sell exactly the best order's quantity
            event = market(seq, f"m{seq}", bids[0]["qty_units"])
        elif move == 6 and bids:                       # sell exactly one best level, or one unit more
            level = sum(r["qty_units"] for r in bids if r["price_ticks"] == bids[0]["price_ticks"])
            event = market(seq, f"m{seq}", level + rng.choice((0, 1)))
        elif move == 7 and bids:                       # sell the whole side, or more
            event = market(seq, f"m{seq}", sum(r["qty_units"] for r in bids) + rng.choice((0, 0, 7)))
        elif move == 8 and asks:                       # buy limit exactly at / one tick under the best ask
            event = limit(seq, f"x{seq}", "BUY", asks[0]["price_ticks"] - rng.choice((0, 1)), qty)
        elif move == 9 and bids:                       # sell limit exactly at / one tick over the best bid
            event = limit(seq, f"x{seq}", "SELL", bids[0]["price_ticks"] + rng.choice((0, 1)), qty)
        elif move == 10 and dead:                      # resubmit an identifier that is no longer active
            side = rng.choice(("BUY", "SELL"))
            event = limit(seq, rng.choice(dead), side, rng.randint(low, high), qty)
        elif move == 11 and rows:                      # duplicate of a live identifier: must be rejected
            event = limit(seq, rng.choice(rows)["order_id"], "BUY", low, qty)
        elif move == 12 and rows:                      # market sell under a live identifier: rejected
            event = market(seq, rng.choice(rows)["order_id"], qty)
        elif move == 13:                               # limit far through the whole opposite side
            side = rng.choice(("BUY", "SELL"))
            event = limit(seq, f"x{seq}", side, high + 50 if side == "BUY" else max(1, low - 50), qty * 3)
        else:
            side = rng.choice(("BUY", "SELL"))
            event = limit(seq, f"{rng.randrange(1000):03d}/{seq}", side, rng.randint(low, high), qty)
        live_before = {r["order_id"] for r in rows}
        _, last_seq = spec_step(rows, last_seq, event)
        dead.extend(live_before - {r["order_id"] for r in rows})
        events.append(event)
    return events


class HuntingFuzzTests(AdversarialCase):
    def test_targeted_streams_in_a_band_where_both_sides_overlap(self):
        for seed in range(30):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 400))

    def test_single_price_for_everything(self):
        # Every limit crosses or queues at the same price: pure time priority.
        for seed in range(10):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 400, prices=(100, 100)))

    def test_one_unit_and_astronomic_quantities_mixed(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 300, big=True))

    def test_hands_off_streams_meet_stale_heap_entries_inside_matching(self):
        # No inspection between events: stale entries survive until a matching step finds them.
        for seed in range(30):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 500), snapshot_every=0)
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 500, prices=(1, 400)),
                                               snapshot_every=0)

    def test_many_prices_few_orders_each(self):
        for seed in range(6):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, hunting_stream(random.Random(seed), 700, prices=(1, 400)))

    def test_invalid_noise_between_valid_events(self):
        for seed in range(200, 215):
            with self.subTest(seed=seed):
                self.assert_classes_match_spec(VERSIONS, random_stream(random.Random(seed), 300, invalid_share=0.45))


# ----------------------------------------------- thresholds inside version B
class ThresholdTests(AdversarialCase):
    def test_stale_heap_entries_cross_the_rebuild_threshold_repeatedly(self):
        # Open 200 bid levels, cancel them from the worst price upward so that none is the heap top,
        # reopen some stale prices, then trade through what is left.
        events, seq = [], 0
        for cycle in range(4):
            ids = []
            for i in range(200):
                seq += 1
                ids.append(f"c{cycle}-{i}")
                events.append(limit(seq, ids[-1], "BUY", 1000 + i, 1 + i % 3))
            for i in range(0, 190):                    # worst prices first; the top ten stay
                seq += 1
                events.append(cancel(seq, ids[i]))
            for i in (5, 6, 7, 150):                   # reopen prices whose heap entries may be stale
                seq += 1
                events.append(limit(seq, f"r{cycle}-{i}", "BUY", 1000 + i, 2))
            seq += 1
            events.append(market(seq, f"m{cycle}", 9))
            seq += 1
            events.append(limit(seq, f"s{cycle}", "SELL", 1004, 10**6))    # sweeps every bid >= 1004, rests
            seq += 1
            events.append(cancel(seq, f"s{cycle}"))
        books, _ = self.assert_classes_match_spec(VERSIONS, events)
        for book in books[1:]:
            stats = book.storage_stats()
            self.assertLessEqual(stats["heap_entries"], 2 * stats["price_levels"] + book_b.HEAP_SLACK)

    def test_stale_entries_stay_bounded_when_matching_removes_the_live_levels(self):
        # Cancellations leave stale heap entries at the worst prices while the best prices stay
        # occupied; an exact-size sale then removes every live level without reaching the stale ones.
        # Found by review of the rebuild rule: it was only checked on cancellation.
        events, seq = [], 0
        for i in range(60):
            seq += 1
            events.append(limit(seq, f"b{i}", "BUY", 1000 + i, 1))
        for i in range(40):                            # the 40 worst prices go stale, 20 best stay
            seq += 1
            events.append(cancel(seq, f"b{i}"))
        events.append(market(seq + 1, "exact", 20))    # consumes exactly the 20 live levels
        books, rows = self.assert_classes_match_spec(VERSIONS, events)
        self.assertEqual(rows, [])
        for book in books[1:]:
            stats = book.storage_stats()
            self.assertLessEqual(stats["heap_entries"], 2 * stats["price_levels"] + book_b.HEAP_SLACK)

    def test_capacity_release_by_cancellation_then_continued_trading(self):
        # Exceed SHRINK_MIN, then fall below one eighth of the peak: version B copies its tables.
        total = book_b.SHRINK_MIN + 2500
        rng = random.Random(77)
        events = [limit(i, f"o{i}", "BUY" if i % 2 else "SELL",
                        5000 - rng.randrange(60) if i % 2 else 5001 + rng.randrange(60), rng.randint(1, 4))
                  for i in range(1, total + 1)]
        order = list(range(1, total + 1))
        rng.shuffle(order)
        seq = total
        for i in order[:total - 150]:
            seq += 1
            events.append(cancel(seq, f"o{i}"))
        for extra in hunting_stream(random.Random(3), 600, prices=(4990, 5010)):   # keep trading afterwards
            seq += 1
            extra = dict(extra, seq=seq, event_id=f"e{seq}")
            for key in ("order_id", "target_order_id"):
                if key in extra:
                    extra[key] = "late-" + extra[key]
            events.append(extra)
        books, _ = self.assert_classes_match_spec(VERSIONS, events, snapshot_every=97)
        for book in books[1:]:
            self.assertLess(book._index_peak, total // 2, "capacity release never happened")

    def test_capacity_release_triggered_inside_matching(self):
        # One huge market sell and one huge limit buy erase a 6,000-order book mid-event.
        total = book_b.SHRINK_MIN + 1904
        events = [limit(i, f"o{i}", "BUY" if i % 2 else "SELL", 700 - i % 37 if i % 2 else 701 + i % 41, 2)
                  for i in range(1, total + 1)]
        events += [market(total + 1, "dump", 10**9),
                   limit(total + 2, "lift", "BUY", 10**6, 10**9),
                   limit(total + 3, "after", "SELL", 10**6, 5),
                   limit(total + 4, "bid2", "BUY", 600, 1), market(total + 5, "m", 3), cancel(total + 6, "lift"),
                   cancel(total + 7, "bid2")]
        books, rows = self.assert_classes_match_spec(VERSIONS, events, snapshot_every=500)
        self.assertEqual(rows, [])
        for book in books[1:]:
            self.assertLessEqual(book._index_peak, 2, "capacity release never happened")

    def test_queue_survives_capacity_release_in_arrival_order(self):
        # After the tables are copied, the survivors of one long queue must still fill first-in, first-out.
        total = book_b.SHRINK_MIN + 904
        events = [limit(i, f"q{(i * 31) % total}", "BUY", 100, 1) for i in range(1, total + 1)]
        survivors = [e["order_id"] for e in events[::40]]                # every 40th arrival stays
        keep = set(survivors)
        seq = total
        for e in reversed(events):
            if e["order_id"] not in keep:
                seq += 1
                events.append(cancel(seq, e["order_id"]))
        events.append(market(seq + 1, "s", len(survivors) - 1))
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for event in events[:-1]:
                    book.ProcessEvent(event)
                book.check_invariants()
                result = book.ProcessEvent(events[-1])
                self.assertEqual([f["maker_id"] for f in result["fills"]], survivors[:-1])
                self.assertEqual([r["order_id"] for r in book.InspectBook()], survivors[-1:])


# ------------------------------------------------------ metamorphic properties
def run(cls, events):
    book = cls()
    return book, [book.ProcessEvent(event) for event in events]


class MetamorphicTests(AdversarialCase):
    def streams(self):
        for seed in range(8):
            yield hunting_stream(random.Random(1000 + seed), 300)
            yield random_stream(random.Random(2000 + seed), 300, invalid_share=0.05)

    def test_relabelling_identifiers_changes_nothing_but_the_labels(self):
        # Reverse-sorted new names: if spelling carried priority, fills would change.
        for events in self.streams():
            names = sorted({e[k] for e in events for k in ("order_id", "target_order_id")
                            if isinstance(e.get(k), str) and e.get(k)})
            mapping = {name: f"Z{len(names) - i:06d}" for i, name in enumerate(names)}

            def rename(value):
                if isinstance(value, dict):
                    return {k: (mapping.get(v, v) if k in ("order_id", "target_order_id", "maker_id", "taker_id")
                                and isinstance(v, str) else rename(v)) for k, v in value.items()}
                return [rename(v) for v in value] if isinstance(value, list) else value
            for cls in VERSIONS:
                book, results = run(cls, events)
                renamed_book, renamed_results = run(cls, [rename(e) for e in events])
                self.assertEqual(rename(results), renamed_results)
                self.assertEqual(rename(book.InspectBook()), renamed_book.InspectBook())

    def test_scaling_quantities_scales_fills(self):
        factor = 10**9 + 7

        def scale(value):
            if isinstance(value, dict):
                return {k: (v * factor if k in ("qty_units", "unfilled_qty_units", "cancelled_qty_units")
                            and type(v) is int else scale(v)) for k, v in value.items()}
            return [scale(v) for v in value] if isinstance(value, list) else value
        for events in self.streams():
            for cls in VERSIONS:
                book, results = run(cls, events)
                scaled_book, scaled_results = run(cls, [scale(e) for e in events])
                self.assertEqual(scale(results), scaled_results)
                self.assertEqual(scale(book.InspectBook()), scaled_book.InspectBook())

    def test_shifting_prices_and_stretching_arrival_ranks(self):
        def move(value):
            if isinstance(value, dict):
                out = {}
                for k, v in value.items():
                    if k == "price_ticks" and type(v) is int:
                        out[k] = v + 10**12 if v > 0 else v
                    elif k in ("seq", "arrival_seq") and type(v) is int and v > 0:
                        out[k] = v * 1000 + 3
                    else:
                        out[k] = move(v)
                return out
            return [move(v) for v in value] if isinstance(value, list) else value
        for events in self.streams():
            for cls in VERSIONS:
                book, results = run(cls, events)
                moved_book, moved_results = run(cls, [move(e) for e in events])
                self.assertEqual([without_reason(move(r)) for r in results],
                                 [without_reason(r) for r in moved_results])
                self.assertEqual(move(book.InspectBook()), moved_book.InspectBook())

    def test_book_rebuilt_from_its_inspection_behaves_identically(self):
        # The inspection must contain the complete state that matters for the future.
        for events in self.streams():
            half = len(events) // 2
            for cls in VERSIONS:
                book, _ = run(cls, events[:half])
                rebuilt = cls()
                for r in sorted(book.InspectBook(), key=lambda r: r["arrival_seq"]):
                    result = rebuilt.AddLimitOrder(r["order_id"], r["side"], r["price_ticks"], r["qty_units"],
                                                   r["arrival_seq"])
                    self.assertEqual((result["status"], result["fills"]), ("resting", []))
                rebuilt.last_seq = book.last_seq
                self.assertEqual(rebuilt.InspectBook(), book.InspectBook())
                for event in events[half:]:
                    self.assertEqual(rebuilt.ProcessEvent(event), book.ProcessEvent(event))
                self.assertEqual(rebuilt.InspectBook(), book.InspectBook())

    def test_one_sale_equals_the_same_quantity_sold_in_pieces(self):
        rng = random.Random(4)
        for _ in range(60):
            bids = [limit(i, f"b{i}", "BUY", rng.randint(90, 99), rng.randint(1, 9)) for i in range(1, 40)]
            total = rng.randint(1, 260)
            pieces, left = [], total
            while left:
                pieces.append(rng.randint(1, left))
                left -= pieces[-1]
            for cls in VERSIONS:
                whole, results = run(cls, bids + [market(100, "s", total)])
                parts, part_results = run(cls, bids + [market(100 + i, "s", q) for i, q in enumerate(pieces)])
                merged = {}
                for result in part_results[len(bids):]:
                    for f in result["fills"]:
                        key = (f["maker_id"], f["price_ticks"])
                        merged[key] = merged.get(key, 0) + f["qty_units"]
                single = {(f["maker_id"], f["price_ticks"]): f["qty_units"] for f in results[-1]["fills"]}
                self.assertEqual(list(merged.items()), list(single.items()))      # same makers, same order
                self.assertEqual(whole.InspectBook(), parts.InspectBook())

    def test_results_and_inspections_are_detached_from_the_book(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                event = limit(1, "b1", "BUY", 100, 5)
                first = book.ProcessEvent(event)
                event.update(order_id="hacked", price_ticks=1, qty_units=999, side="SELL")
                first.update(unfilled_qty_units=0, order_id="hacked")
                rows = book.InspectBook()
                rows[0].update(qty_units=10**9, price_ticks=1, order_id="hacked")
                rows.clear()
                sale = book.ProcessEvent(market(2, "s", 2))
                sale["fills"][0]["qty_units"] = 10**9
                sale["fills"].clear()
                self.assertEqual(book.InspectBook(), [row("b1", "BUY", 100, 3, 1)])
                self.assertEqual(book.ProcessEvent(cancel(3, "b1")), cancelled(3, "b1", "cancelled", 3))
                book.check_invariants()


# ---------------------------------------------------------- hostile values
class StrLike(str):
    pass


class IntLike(int):
    pass


class HostileValueTests(AdversarialCase):
    def test_unusual_but_valid_identifiers(self):
        ids = ["", " ", "  b1", "b1 ", "B1", "b1", "ｂ１", "b\u0000", "é", "é", "0", "00", "-1", "null", "None",
               "x" * 5000, "🙂", "a\nb", '"quoted"', "CANCEL", "e1"][1:]
        events = [limit(i, order_id, "BUY", 100, 1) for i, order_id in enumerate(ids, 1)]
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for event in events:
                    self.assertEqual(book.ProcessEvent(event)["status"], "resting", repr(event["order_id"]))
                self.assertEqual(book.active_orders(), len(ids))      # none of them collide
                sale = book.ProcessEvent(market(100, "s", len(ids)))
                self.assertEqual([f["maker_id"] for f in sale["fills"]], ids)   # arrival order, not spelling
                self.assertEqual(book.InspectBook(), [])

    def test_lookalike_types_are_rejected_and_leave_no_trace(self):
        nan, inf = float("nan"), float("inf")
        good = limit(2, "x", "BUY", 100, 1)
        bad = [dict(good, qty_units=v) for v in (nan, inf, -inf, IntLike(3), 1e3, 3 + 0j, b"3", [3], {"v": 3}, (3,))]
        bad += [dict(good, price_ticks=v) for v in (nan, inf, IntLike(100), "100", b"100", [100])]
        bad += [dict(good, seq=v) for v in (nan, inf, IntLike(2), [2], "2", 2.0)]
        bad += [dict(good, order_id=v) for v in (StrLike("x"), b"x", ["x"], ("x",), {"id": "x"}, 0, 1.5)]
        bad += [dict(good, side=v) for v in (StrLike("BUY"), b"BUY", ["BUY"], {"BUY"}, " BUY", "BUY ", "Buy")]
        bad += [dict(good, type=v) for v in (["LIMIT"], {"LIMIT": 1}, " LIMIT", "LIMIT ", b"LIMIT", "CANCEL_ALL")]
        bad += [dict(good, event_id=v) for v in (["e"], {"e": 1}, b"e", 0, StrLike("e"))]
        bad += [dict(cancel(2, "b1"), target_order_id=v) for v in (["b1"], {"b1"}, b"b1", StrLike("b1"), 1)]
        for cls in VERSIONS:
            for event in bad:
                with self.subTest(version=cls.__name__, event=repr(event)):
                    book = cls()
                    book.ProcessEvent(limit(1, "b1", "BUY", 100, 5))
                    result = book.ProcessEvent(event)
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual((book.InspectBook(), book.last_seq), ([row("b1", "BUY", 100, 5, 1)], 1))
                    book.check_invariants()

    def test_extra_and_contradictory_fields_are_ignored(self):
        self.check([dict(limit(1, "b1", "BUY", 100, 5), target_order_id="b1", note={"deep": [1, 2]}, qty=99),
                    dict(cancel(2, "b1"), order_id="b1", side="SELL", price_ticks=-5, qty_units="x"),
                    dict(market(3, "s", 1), side="BUY", price_ticks=0, target_order_id="s")],
                   [submitted(1, "b1", "resting", 5), cancelled(2, "b1", "cancelled", 5),
                    submitted(3, "s", "unfilled", 1)], [])

    def test_identifier_shared_by_event_and_order_and_reused_across_kinds(self):
        # A market sell never becomes active, so its identifier stays free; a filled limit frees its own.
        self.check([limit(1, "e1", "BUY", 100, 2), market(2, "m", 1), limit(3, "m", "BUY", 99, 1),
                    market(4, "e1", 1), market(5, "x", 1), limit(6, "e1", "SELL", 99, 1)],
                   [submitted(1, "e1", "resting", 2), submitted(2, "m", "filled", 0, [fill("e1", "m", 100, 1)]),
                    submitted(3, "m", "resting", 1), {"event_id": "e4", "status": "rejected",
                                                      "reason": "order_id is already active"},
                    submitted(5, "x", "filled", 0, [fill("e1", "x", 100, 1)]),
                    submitted(6, "e1", "filled", 0, [fill("m", "e1", 99, 1)])], [])

    def test_replayed_and_out_of_order_events_are_rejected(self):
        events = [limit(1, "b1", "BUY", 100, 5), limit(2, "a1", "SELL", 101, 5), market(3, "s", 2)]
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                first = [book.ProcessEvent(e) for e in events]
                state = book.InspectBook()
                for event in events + events[::-1]:
                    self.assertEqual(book.ProcessEvent(event)["status"], "rejected")
                self.assertEqual((book.InspectBook(), book.last_seq), (state, 3))
                self.assertEqual(first[2]["fills"], [fill("b1", "s", 100, 2)])

    def test_extreme_prices_and_sequence_numbers(self):
        top = 2**200
        self.check([limit(1, "lo", "BUY", 1, 1), limit(top, "hi", "BUY", top, 1), limit(top + 1, "ask", "SELL", top + 1, 1),
                    market(top + 2, "s", 2), limit(top + 3, "one", "SELL", 1, 1)],
                   [None, None, None, submitted(top + 2, "s", "filled", 0, [fill("hi", "s", top, 1), fill("lo", "s", 1, 1)]),
                    None],
                   [row("one", "SELL", 1, 1, top + 3), row("ask", "SELL", top + 1, 1, top + 1)])

    def test_incoming_order_never_trades_with_its_own_residual_or_same_side(self):
        # A buy that sweeps the asks and rests must not appear as an ask, and a later buy cannot hit it.
        self.check([limit(1, "a1", "SELL", 100, 1), limit(2, "b1", "BUY", 100, 3), limit(3, "b2", "BUY", 100, 3),
                    limit(4, "a2", "SELL", 100, 4)],
                   [None, submitted(2, "b1", "resting", 2, [fill("a1", "b1", 100, 1)]), submitted(3, "b2", "resting", 3),
                    submitted(4, "a2", "filled", 0, [fill("b1", "a2", 100, 2), fill("b2", "a2", 100, 2)])],
                   [row("b2", "BUY", 100, 1, 3)])

    def test_alternating_exact_crosses_never_leave_a_crossed_or_dirty_book(self):
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                for i in range(1, 2001):
                    side, price = ("BUY", 100 + i % 7) if i % 2 else ("SELL", 100 + (i + 3) % 7)
                    book.ProcessEvent(limit(i, f"o{i}", side, price, 1 + i % 4))
                    bid, ask = book.best_bid(), book.best_ask()
                    self.assertTrue(bid is None or ask is None or bid < ask, f"crossed after event {i}")
                book.check_invariants()


# ------------------------------------------------------------ damaged files
class DirtyFileTests(unittest.TestCase):
    LINES = [json.dumps(limit(1, "b1", "BUY", 100, 5)), json.dumps(market(2, "s", 2))]

    def write(self, folder, name, data):
        path = Path(folder) / name
        path.write_bytes(data)
        return path

    def test_blank_lines_windows_line_endings_and_byte_order_mark(self):
        with tempfile.TemporaryDirectory() as folder:
            text = "﻿" + "\r\n".join([self.LINES[0], "", "   ", self.LINES[1], ""])
            plain = self.write(folder, "dirty.jsonl", text.encode("utf-8"))
            packed = self.write(folder, "dirty.jsonl.gz", gzip.compress(text.encode("utf-8")))
            for path in (plain, packed):
                self.assertEqual(read_events(path), [limit(1, "b1", "BUY", 100, 5), market(2, "s", 2)])

    def test_file_without_final_newline_and_empty_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(read_events(self.write(folder, "a.jsonl", "\n".join(self.LINES).encode()))), 2)
            self.assertEqual(read_events(self.write(folder, "empty.jsonl", b"")), [])
            self.assertEqual(read_events(self.write(folder, "empty.jsonl.gz", gzip.compress(b""))), [])

    def test_malformed_line_is_reported_with_its_line_number_not_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            for broken in ('{"seq": 2, "event_id": "e2", "type": ', "{'seq': 2}", "seq=2", '{"seq": 2}}'):
                path = self.write(folder, "bad.jsonl", "\n".join([self.LINES[0], broken, self.LINES[1]]).encode())
                with self.assertRaises(ValueError) as caught:
                    read_events(path)
                self.assertIn("line 2", str(caught.exception))

    def test_line_the_json_parser_refuses_for_other_reasons_also_names_its_line(self):
        # An integer of more than 4,300 digits is refused with a plain ValueError, not a JSONDecodeError
        # (found by an independent review); the reader must still say which line it was.
        huge = '{"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "h", "side": "BUY", "price_ticks": 1, ' \
               '"qty_units": ' + "9" * 5000 + "}"
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "huge.jsonl", "\n".join([self.LINES[0], huge]).encode())
            with self.assertRaises(ValueError) as caught:
                read_events(path)
            self.assertIn("line 2 is not valid JSON", str(caught.exception))

    def test_truncated_gzip_file_is_an_error_not_a_short_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            data = gzip.compress(("\n".join(self.LINES * 500) + "\n").encode())
            path = self.write(folder, "cut.jsonl.gz", data[:len(data) // 2])
            with self.assertRaises((EOFError, OSError, ValueError)):
                read_events(path)

    def test_valid_json_that_is_not_a_valid_event_reaches_the_book_and_is_rejected(self):
        lines = ["42", "null", "[]", '"LIMIT"', "{}", '{"seq": NaN, "event_id": "n", "type": "CANCEL", "target_order_id": "x"}',
                 '{"seq": 1e0, "event_id": "f", "type": "CANCEL", "target_order_id": "x"}',
                 '{"seq": 1, "seq": 0, "event_id": "dup-key", "type": "CANCEL", "target_order_id": "x"}',
                 '{"seq": 1, "event_id": "b", "type": "LIMIT", "order_id": "b", "side": "BUY", "price_ticks": 100.0, "qty_units": 1}',
                 '{"seq": 123456789012345678901234567890, "event_id": "ok", "type": "LIMIT", "order_id": "b", "side": "BUY", '
                 '"price_ticks": 100, "qty_units": 1}']
        with tempfile.TemporaryDirectory() as folder:
            events = read_events(self.write(folder, "odd.jsonl", "\n".join(lines).encode()))
        for cls in VERSIONS:
            with self.subTest(version=cls.__name__):
                book = cls()
                statuses = [book.ProcessEvent(event)["status"] for event in events]
                self.assertEqual(statuses, ["rejected"] * 9 + ["resting"])
                self.assertEqual(book.InspectBook(), [row("b", "BUY", 100, 1, 123456789012345678901234567890)])


# ----------------------------------------------------------------- mutants
class TakerPrice:
    """Bug: a crossing limit trades at its own limit instead of the resting price."""
    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        unfilled = super()._add_limit(order_id, is_buy, price, qty, seq, fills)
        for f in fills:
            f["price_ticks"] = price
        return unfilled


class SeqAdvancesOnReject:
    """Bug: a rejected event still consumes its arrival rank."""
    def ProcessEvent(self, event):
        result = super().ProcessEvent(event)
        if result["status"] == "rejected" and isinstance(event, dict) and type(event.get("seq")) is int:
            self.last_seq = max(self.last_seq, event["seq"])
        return result


class MarketResidualRests:
    """Bug: the unfilled part of a market sell becomes an ask."""
    def _market_sell(self, order_id, qty, fills):
        unfilled = super()._market_sell(order_id, qty, fills)
        if unfilled:
            self._add_limit(order_id, False, 10**9, unfilled, self.last_seq, [])
        return unfilled


class NoDuplicateCheck:
    """Bug: submitting a live identifier again silently replaces the resting order."""
    def AddLimitOrder(self, order_id, *args, **kwargs):
        if type(order_id) is str and order_id in self._live:
            self._cancel(order_id)
        return super().AddLimitOrder(order_id, *args, **kwargs)


class ReversedFills:
    """Bug: fills are reported in the wrong order."""
    def _market_sell(self, order_id, qty, fills):
        unfilled = super()._market_sell(order_id, qty, fills)
        fills.reverse()
        return unfilled


class CancelReportsOriginalSize:
    """Bug: a cancellation after a partial fill reports more than the residual."""
    def _cancel(self, order_id):
        removed = super()._cancel(order_id)
        return removed + 1 if removed else 0


class StrictCrossing:
    """Bug: a limit at exactly the opposite best price does not trade."""
    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        opposite = self.best_ask() if is_buy else self.best_bid()
        if opposite == price:
            saved = self._match
            self._match = lambda *args: args[-2]            # qty is the second-to-last argument
            try:
                return super()._add_limit(order_id, is_buy, price, qty, seq, fills)
            finally:
                self._match = saved
        return super()._add_limit(order_id, is_buy, price, qty, seq, fills)


class LastInFirstOutA:
    """Bug in A: among equal prices the newest order is chosen."""
    def _best(self, side):
        return min(side, key=lambda r: (r[KEY], -r[SEQ]))


class GhostAfterCancelA:
    """Bug in A: the cancelled order leaves the index but stays in the list."""
    def _cancel(self, order_id):
        record = self._live.pop(order_id, None)
        return record[2] if record else 0


class NewestFirstB:
    """Bug in B: a new order jumps to the head of its queue."""
    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        unfilled = super()._add_limit(order_id, is_buy, price, qty, seq, fills)
        if unfilled:
            self._levels[-price if is_buy else price].move_to_end(order_id, last=False)
        return unfilled


class PartialLosesPlaceB:
    """Bug in B: a partially filled maker is sent to the back of its queue."""
    def _match(self, heap, limit, taker_id, qty, fills):
        unfilled = super()._match(heap, limit, taker_id, qty, fills)
        if fills:
            price, maker = fills[-1]["price_ticks"], fills[-1]["maker_id"]
            for key in (price, -price):
                if maker in self._levels.get(key, ()):
                    self._levels[key].move_to_end(maker)
        return unfilled


class _NeverForgets(set):
    def discard(self, key):
        pass


class ForgetsHeapB:
    """Bug in B: a key popped from a heap is still believed to be in it, so reopening that
    price does not push it again."""
    def __init__(self):
        super().__init__()
        self._in_heap = _NeverForgets()

    def check_invariants(self):                      # hide the direct evidence: behaviour must reveal it
        pass


class LeaksEmptyLevelsB:
    """Bug in B: a level emptied by cancellation is never deleted."""
    def _cancel(self, order_id):
        record = self._live.pop(order_id, None)
        if record is None:
            return 0
        del self._levels[record[1]][order_id]
        return record[0]


class GhostInQueueB:
    """Bug in B: a cancelled order leaves the index but stays in its queue."""
    def _cancel(self, order_id):
        record = self._live.pop(order_id, None)
        return record[0] if record else 0

    def check_invariants(self):
        pass


class StaleTopTrustedB:
    """Bug in B: the heap top is used as the best price without checking that its level exists."""
    def _match(self, heap, limit, taker_id, qty, fills):
        if heap and heap[0] not in self._levels:
            return qty
        return super()._match(heap, limit, taker_id, qty, fills)


class NewestFirstB1:
    """Bug in B1: a new order jumps to the head of its queue."""
    def _add_limit(self, order_id, is_buy, price, qty, seq, fills):
        unfilled = super()._add_limit(order_id, is_buy, price, qty, seq, fills)
        if unfilled:
            (self._bids if is_buy else self._asks).levels[price].move_to_end(order_id, last=False)
        return unfilled


class PartialLosesPlaceB1:
    """Bug in B1: a partially filled maker is sent to the back of its queue."""
    def _match(self, side, limit, taker_buys, taker_id, qty, fills):
        unfilled = super()._match(side, limit, taker_buys, taker_id, qty, fills)
        if fills:
            level = side.levels.get(fills[-1]["price_ticks"])
            if level and fills[-1]["maker_id"] in level:
                level.move_to_end(fills[-1]["maker_id"])
        return unfilled


class StaleHeapNeverRevalidatedB1(book_b1._Side):
    """Bug in B1: reopening a price whose heap entry was discarded does not push it again."""
    __slots__ = ()

    def best_price(self):
        heap, levels, sign = self.heap, self.levels, self.sign
        while heap:
            price = heap[0] * sign
            if price in levels:
                return price
            book_b1.heappop(heap)            # forgets to remove the price from in_heap
        return None


class ForgetsHeapB1:
    side_class = StaleHeapNeverRevalidatedB1


class LeaksEmptyLevelsB1:
    """Bug in B1: a level emptied by cancellation is never deleted."""
    def _cancel(self, order_id):
        order = self._live.pop(order_id, None)
        if order is None:
            return 0
        del (self._bids if order.is_buy else self._asks).levels[order.price][order_id]
        return order.qty


GENERIC_MUTANTS = (TakerPrice, SeqAdvancesOnReject, MarketResidualRests, NoDuplicateCheck, ReversedFills,
                   CancelReportsOriginalSize, StrictCrossing)
MUTANTS = ([(m, OrderBookA) for m in GENERIC_MUTANTS + (LastInFirstOutA, GhostAfterCancelA)]
           + [(m, OrderBookB) for m in GENERIC_MUTANTS + (NewestFirstB, PartialLosesPlaceB, ForgetsHeapB,
                                                          LeaksEmptyLevelsB, GhostInQueueB, StaleTopTrustedB)]
           + [(m, OrderBookB1) for m in GENERIC_MUTANTS + (NewestFirstB1, PartialLosesPlaceB1, ForgetsHeapB1,
                                                           LeaksEmptyLevelsB1)])


class MutantTests(AdversarialCase):
    """The checks above are only worth something if they notice a broken engine."""

    def battery(self, cls):
        for seed in range(6):
            self.assert_classes_match_spec([cls], hunting_stream(random.Random(seed), 300))
            self.assert_classes_match_spec([cls], random_stream(random.Random(seed), 250))
            self.assert_classes_match_spec([cls], hunting_stream(random.Random(seed), 300), snapshot_every=0)

    def test_the_battery_accepts_the_real_engines(self):
        for cls in VERSIONS:
            self.battery(cls)

    def test_every_planted_bug_is_detected(self):
        for mutation, base in MUTANTS:
            with self.subTest(bug=mutation.__name__, base=base.__name__):
                broken = type(f"{mutation.__name__}_{base.__name__}", (mutation, base), {})
                with self.assertRaises(AssertionError, msg=mutation.__doc__):
                    self.battery(broken)


if __name__ == "__main__":
    unittest.main()
