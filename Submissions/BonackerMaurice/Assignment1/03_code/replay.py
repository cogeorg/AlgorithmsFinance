"""Replay event files through one order-book version.

Usage (from Assignment1/):
    python 03_code/replay.py <file> [<file> ...] --version a
        [--check] [--results OUT.jsonl] [--csv OUT.csv] [--print-book]

<file> is .jsonl or .jsonl.gz, one JSON event per line. Events are processed
one at a time in file order (the supplied files are in strictly increasing
seq order; an event with a non-increasing seq is rejected, never reordered).
Input lines:
  - empty (whitespace-only) lines are skipped;
  - a line that is not valid JSON (also: invalid UTF-8, nesting too deep to
    parse) gives the result {"event_id": null, "status": "rejected",
    "reason": "malformed JSON line <n>"}, n = 1-based line number in the
    (decompressed) file, and the replay continues; the book is not touched;
  - valid JSON that is not a valid event is rejected by validation.py.

Two passes per file, each on a fresh empty book, with events preloaded
(file reading and JSON parsing are NOT timed):
  1. checked pass (only with --check): after every event runs
     assert_invariants() and the per-event conservation/priority check, and
     records peak active orders and peak occupied price levels.
  2. timed pass: plain process_event loop, one run, time.perf_counter.
     wall_seconds = this single replay. It is an exploration number, not
     the benchmark (no warm-up, no repeats).

--results writes one JSON result per event (from the timed pass; one file only).
--print-book prints the final book after the summary line: a header line
"final book: ...", then one JSON object per resting order (bids best first,
then asks best first; FIFO within a price).
--csv writes one summary row per file; rows of other versions already in
that CSV are kept, rows of this version are replaced.
"""

import argparse
import csv
import gzip
import importlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invariants import check_event  # noqa: E402

CSV_FIELDS = ["version", "scenario", "events", "fills", "rejected",
              "not_found_cancels", "peak_active_orders", "peak_price_levels",
              "final_book_size", "invariants_ok", "wall_seconds"]


class MalformedLine:
    """Stands in for an input line that could not be parsed as JSON."""

    __slots__ = ("line_no",)

    def __init__(self, line_no):
        self.line_no = line_no

    def __repr__(self):
        return f"MalformedLine({self.line_no})"


def load_events(path):
    """Read a .jsonl or .jsonl.gz file: one item per non-empty line, in file order.

    A parsable line becomes its JSON value (normally an event dict). A line
    that cannot be parsed becomes MalformedLine(n), n = its 1-based line
    number. The file is read as bytes, so invalid UTF-8 in one line only
    affects that line.
    """
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    items = []
    with opener(path, "rb") as fh:
        for n, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except (ValueError, RecursionError):   # bad JSON or UTF-8; too deeply nested
                items.append(MalformedLine(n))
    return items


def malformed_result(item):
    """The result for a MalformedLine (the book is not involved)."""
    return {"event_id": None, "status": "rejected",
            "reason": f"malformed JSON line {item.line_no}"}


def process(book, item):
    """book.process_event for a parsed line; a rejected result for a malformed one."""
    if type(item) is MalformedLine:
        return malformed_result(item)
    return book.process_event(item)


def scenario_name(path):
    """buildup_10000.jsonl.gz -> buildup"""
    stem = Path(path).name.split(".")[0]
    return re.sub(r"_\d+$", "", stem)


def make_book(version):
    return importlib.import_module(f"lob_{version}").OrderBook()


def checked_replay(events, version):
    """Replay with every check after every event. Returns a stats dict."""
    book = make_book(version)
    stats = {"fills": 0, "rejected": 0, "not_found_cancels": 0,
             "peak_active_orders": 0, "peak_price_levels": 0,
             "invariants_ok": True, "first_error": ""}
    before = book.inspect_book()
    for i, event in enumerate(events, start=1):
        result = process(book, event)
        after = book.inspect_book()
        try:
            book.assert_invariants()
            check_event(before, event, result, after)   # rejected: book unchanged
        except AssertionError as exc:
            if stats["invariants_ok"]:
                where = (f"seq {event.get('seq')}" if isinstance(event, dict)
                         else f"item {i} of the file")
                stats["first_error"] = f"{where}: {exc}"
            stats["invariants_ok"] = False
        status = result["status"]
        stats["fills"] += len(result.get("fills", []))
        stats["rejected"] += status == "rejected"
        stats["not_found_cancels"] += status == "not_found"
        stats["peak_active_orders"] = max(stats["peak_active_orders"], len(after))
        levels = len({(o["side"], o["price_ticks"]) for o in after})
        stats["peak_price_levels"] = max(stats["peak_price_levels"], levels)
        before = after
    stats["final_book_size"] = len(before)
    return stats


def timed_replay(events, version):
    """One plain replay on a fresh book. Returns (results, seconds, book)."""
    book = make_book(version)
    process_event = book.process_event
    start = time.perf_counter()
    results = [malformed_result(e) if type(e) is MalformedLine else process_event(e)
               for e in events]
    seconds = time.perf_counter() - start
    return results, seconds, book


def write_summary_csv(path, version, rows):
    """Write rows, keeping any existing rows of OTHER versions in the file.

    So `--version b --csv same.csv` adds Version B next to Version A.
    """
    kept = []
    if Path(path).exists():
        with open(path, newline="", encoding="utf-8") as fh:
            kept = [r for r in csv.DictReader(fh) if r["version"] != version]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(kept + rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+")
    parser.add_argument("--version", choices=["a", "b_sorted", "b_heap"], required=True)
    parser.add_argument("--check", action="store_true",
                        help="check invariants after every event")
    parser.add_argument("--results", help="write per-event results (JSON lines)")
    parser.add_argument("--csv", help="write one summary row per file")
    parser.add_argument("--print-book", action="store_true",
                        help="print the final book (one JSON order per line)")
    args = parser.parse_args(argv)
    if args.results and len(args.files) > 1:
        parser.error("--results takes exactly one input file")

    rows = []
    all_ok = True
    for path in args.files:
        events = load_events(path)
        results, seconds, book = timed_replay(events, args.version)
        row = {
            "version": args.version,
            "scenario": scenario_name(path),
            "events": len(events),
            "fills": sum(len(r.get("fills", [])) for r in results),
            "rejected": sum(r["status"] == "rejected" for r in results),
            "not_found_cancels": sum(r["status"] == "not_found" for r in results),
            "peak_active_orders": "",
            "peak_price_levels": "",
            "final_book_size": len(book.inspect_book()),
            "invariants_ok": "not checked",
            "wall_seconds": f"{seconds:.6f}",
        }
        if args.check:
            stats = checked_replay(events, args.version)
            # Both passes must agree on the counts.
            for key in ("fills", "rejected", "not_found_cancels", "final_book_size"):
                assert stats[key] == row[key], (key, stats[key], row[key])
            row["peak_active_orders"] = stats["peak_active_orders"]
            row["peak_price_levels"] = stats["peak_price_levels"]
            row["invariants_ok"] = stats["invariants_ok"]
            all_ok = all_ok and stats["invariants_ok"]
            if stats["first_error"]:
                print(f"  FIRST INVARIANT ERROR: {stats['first_error']}")
        rows.append(row)
        print("  ".join(f"{k}={row[k]}" for k in CSV_FIELDS))
        if args.print_book:
            final = book.inspect_book()
            print(f"final book: {len(final)} resting orders (bids best first, then asks "
                  "best first; FIFO within a price)")
            for order in final:
                print(json.dumps(order))

        if args.results:
            with open(args.results, "w", encoding="utf-8") as fh:
                for r in results:
                    fh.write(json.dumps(r) + "\n")

    if args.csv:
        write_summary_csv(args.csv, args.version, rows)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
