"""Measure the second revision step: first revision (B1) against the submitted version B.

    python tuning.py

Three engines replay the same pre-parsed streams in one process, interleaved repeat by
repeat so that machine drift affects them alike:

  B1 original   book_b1.py behind the event envelope as it was before tuning (kept below)
  B1            book_b1.py behind the current shared envelope
  B             book_b.py, the submitted revision

The first row therefore shows the whole step, the second separates what the envelope
contributed from what the book structure contributed. Results of all three are compared
event by event before anything is timed. Writes results/tuning.json. This is a diagnostic
comparison of two revisions; the baseline-versus-revision measurements are benchmark.py's.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

from book_b import OrderBookB
from book_b1 import OrderBookB1
from events import BUY, SELL, NO_SEQ, read_events, rejected
import workloads

HERE = Path(__file__).resolve().parent
SOURCE_FILES = ("events.py", "book_b.py", "book_b1.py", "tuning.py")


class OriginalEnvelope:
    """The dispatcher and the three operations exactly as first written: one check after
    another, with a helper call for the arrival rank and one for the duplicate test."""

    def _is_live(self, order_id):
        return order_id in self._live

    def ProcessEvent(self, event):
        if not isinstance(event, dict):
            return rejected(None, "event must be a JSON object")
        event_id = event.get("event_id")
        if type(event_id) is not str or not event_id:
            return rejected(None, "event_id must be a non-empty string")
        kind = event.get("type")
        if kind == "LIMIT":
            return self.AddLimitOrder(event.get("order_id"), event.get("side"), event.get("price_ticks"),
                                      event.get("qty_units"), event.get("seq"), event_id)
        if kind == "MARKET_SELL":
            return self.FillMarketSell(event.get("order_id"), event.get("qty_units"), event_id, event.get("seq"))
        if kind == "CANCEL":
            return self.CancelOrder(event.get("target_order_id"), event_id, event.get("seq"))
        return rejected(event_id, "type must be LIMIT, MARKET_SELL or CANCEL")

    def AddLimitOrder(self, order_id, side, price_ticks, qty_units, seq, event_id=None):
        reason = self._seq_error(seq)
        if reason is None:
            if type(order_id) is not str or not order_id:
                reason = "order_id must be a non-empty string"
            elif type(side) is not str or (side != BUY and side != SELL):
                reason = "side must be BUY or SELL"
            elif type(price_ticks) is not int or price_ticks <= 0:
                reason = "price_ticks must be a positive integer"
            elif type(qty_units) is not int or qty_units <= 0:
                reason = "qty_units must be a positive integer"
            elif self._is_live(order_id):
                reason = "order_id is already active"
        if reason is not None:
            return rejected(event_id, reason)
        self.last_seq = seq
        fills = []
        unfilled = self._add_limit(order_id, side == BUY, price_ticks, qty_units, seq, fills)
        return {"event_id": event_id, "order_id": order_id, "status": "resting" if unfilled else "filled",
                "unfilled_qty_units": unfilled, "fills": fills}

    def FillMarketSell(self, order_id, qty_units, event_id=None, seq=NO_SEQ):
        reason = None if seq is NO_SEQ else self._seq_error(seq)
        if reason is None:
            if type(order_id) is not str or not order_id:
                reason = "order_id must be a non-empty string"
            elif type(qty_units) is not int or qty_units <= 0:
                reason = "qty_units must be a positive integer"
            elif self._is_live(order_id):
                reason = "order_id is already active"
        if reason is not None:
            return rejected(event_id, reason)
        if seq is not NO_SEQ:
            self.last_seq = seq
        fills = []
        unfilled = self._market_sell(order_id, qty_units, fills)
        status = "filled" if not unfilled else ("partial" if fills else "unfilled")
        return {"event_id": event_id, "order_id": order_id, "status": status,
                "unfilled_qty_units": unfilled, "fills": fills}

    def CancelOrder(self, target_order_id, event_id=None, seq=NO_SEQ):
        reason = None if seq is NO_SEQ else self._seq_error(seq)
        if reason is None and (type(target_order_id) is not str or not target_order_id):
            reason = "target_order_id must be a non-empty string"
        if reason is not None:
            return rejected(event_id, reason)
        if seq is not NO_SEQ:
            self.last_seq = seq
        removed = self._cancel(target_order_id)
        return {"event_id": event_id, "target_order_id": target_order_id,
                "status": "cancelled" if removed else "not_found", "cancelled_qty_units": removed}


class OriginalB1(OriginalEnvelope, OrderBookB1):
    version = "B1 original"


ENGINES = (("B1 original", OriginalB1), ("B1", OrderBookB1), ("B", OrderBookB))


def replay_seconds(cls, events):
    book = cls()
    process = book.ProcessEvent
    gc.collect()
    started = time.perf_counter()
    for event in events:
        process(event)
    return time.perf_counter() - started


def compare(name, events, repeats):
    books = [cls() for _, cls in ENGINES]
    for index, event in enumerate(events):
        results = [book.ProcessEvent(event) for book in books]
        if any(result != results[0] for result in results[1:]):
            raise SystemExit(f"{name}: engines disagree at event index {index}")
    if any(book.InspectBook() != books[0].InspectBook() for book in books[1:]):
        raise SystemExit(f"{name}: final books differ")
    del books                                            # nothing but the timed book stays alive
    for _, cls in ENGINES:                               # warm-up, untimed
        replay_seconds(cls, events[:2000])
    raw = {label: [] for label, _ in ENGINES}
    for _ in range(repeats):
        for label, cls in ENGINES:
            raw[label].append(replay_seconds(cls, events))
    medians = {label: statistics.median(values) for label, values in raw.items()}
    row = {"workload": name, "events": len(events), "identical_results_and_book": True,
           "repeat_seconds": raw, "median_seconds": medians,
           "ns_per_event": {label: medians[label] / len(events) * 1e9 for label in medians},
           "b_time_as_share_of_original": medians["B"] / medians["B1 original"],
           "b_time_as_share_of_b1": medians["B"] / medians["B1"]}
    print(f"{name:28} " + "  ".join(f"{label} {medians[label] * 1e3:8.1f} ms" for label in medians)
          + f"   B/original {row['b_time_as_share_of_original']:.2f}", flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--events", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--output", type=Path, default=HERE / "results" / "tuning.json")
    args = parser.parse_args()
    rows = []
    for scenario in workloads.SCENARIOS:
        workloads.ensure_dataset(scenario, args.events, args.seed)
        events = read_events(workloads.dataset_path(scenario, args.events, args.seed))
        rows.append(compare(scenario, events, args.repeats))
    bids = list(workloads.bid_book_events(args.events, 1000, args.seed))
    total = sum(event["qty_units"] for event in bids)
    sale = {"seq": len(bids) + 1, "event_id": "sale", "type": "MARKET_SELL", "order_id": "sale", "qty_units": total}
    rows.append(compare("bid book + 100% market sell", bids + [sale], args.repeats))
    report = {"tool": "tuning.py", "python": platform.python_version(), "platform": platform.platform(),
              "timer": "time.perf_counter around the whole replay loop; fresh book and gc.collect() per repeat",
              "repeats": args.repeats, "seed": args.seed, "engines": [label for label, _ in ENGINES],
              "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                for name in SOURCE_FILES},
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
