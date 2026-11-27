"""Replay an event file through one or both order-book versions.

    python replay.py data/worked_example.jsonl --version B --expect data/worked_expected.json
    python replay.py data/mixed_10000.jsonl.gz --compare

Prints a JSON summary. Reading/parsing and engine time are reported separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from book_a import OrderBookA
from book_b import OrderBookB
from events import format_usd, gross_value, read_events

BOOKS = {"A": OrderBookA, "B": OrderBookB}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def replay(cls, events):
    """Fresh book; returns (book, per-event results, engine seconds)."""
    book = cls()
    process = book.ProcessEvent
    started = time.perf_counter()
    results = [process(event) for event in events]
    return book, results, time.perf_counter() - started


def summarize(book, results, seconds):
    statuses = {}
    for result in results:
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
    fills = [fill for result in results for fill in result.get("fills", ())]
    value = gross_value(fills)
    return {"version": book.version, "events": len(results), "engine_seconds": round(seconds, 6),
            "statuses": dict(sorted(statuses.items())), "maker_fills": len(fills),
            "filled_qty_units": sum(fill["qty_units"] for fill in fills),
            "gross_value_tick_units": value, "gross_value_usd": format_usd(value),
            "active_orders": book.active_orders(), "price_levels": book.price_levels(),
            "best_bid_ticks": book.best_bid(), "best_ask_ticks": book.best_ask(),
            "results_sha256": digest(results), "book_sha256": digest(book.InspectBook())}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path, help="JSON Lines event file, optionally .gz")
    parser.add_argument("--version", choices=sorted(BOOKS), default="B")
    parser.add_argument("--compare", action="store_true",
                        help="run both versions and require identical results and final books")
    parser.add_argument("--expect", type=Path, help="worked_expected.json to check the last result and book against")
    parser.add_argument("--last-result", action="store_true", help="include the final event's full result")
    parser.add_argument("--book", action="store_true", help="include the remaining orders")
    args = parser.parse_args()

    started = time.perf_counter()
    events = read_events(args.file)
    report = {"file": args.file.as_posix(), "read_parse_seconds": round(time.perf_counter() - started, 6), "runs": []}
    outcomes = []
    for name in (sorted(BOOKS) if args.compare else [args.version]):
        book, results, seconds = replay(BOOKS[name], events)
        outcomes.append((book, results))
        report["runs"].append(summarize(book, results, seconds))
    book, results = outcomes[-1]
    ok = True
    if args.compare:
        (book_a, results_a), (book_b, results_b) = outcomes
        report["versions_identical"] = results_a == results_b and book_a.InspectBook() == book_b.InspectBook()
        ok = report["versions_identical"]
    if args.expect:
        expected = json.loads(args.expect.read_text(encoding="utf-8"))
        value = gross_value(results[-1].get("fills", ()))
        report["matches_expected"] = (results[-1] == expected["market_sell_result"]
                                      and book.InspectBook() == expected["remaining_orders"]
                                      and value == expected["gross_proceeds_tick_units"]
                                      and format_usd(value) == expected["gross_proceeds_usd"])
        report["last_sale_gross_proceeds_usd"] = format_usd(value)
        ok = ok and report["matches_expected"]
    if args.last_result or args.expect:
        report["last_result"] = results[-1] if results else None
    if args.book or args.expect:
        report["remaining_orders"] = book.InspectBook()
    print(json.dumps(report, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
