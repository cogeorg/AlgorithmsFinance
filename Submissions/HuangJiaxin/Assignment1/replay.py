"""Replay an event file through one version of the order book.

    python replay.py data/supplied/worked_example.jsonl                 # version B, summary + book
    python replay.py data/supplied/mixed_10000.jsonl.gz --version A --results out.jsonl

Prints a summary (accepted/rejected events, fills, proceeds) and the final book in
canonical order. With --results, writes one JSON result per event (JSON Lines).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lob.book_a import OrderBookA  # noqa: E402
from lob.book_b import OrderBookB  # noqa: E402
from lob.events_io import iter_events  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help=".jsonl or .jsonl.gz event file")
    ap.add_argument("--version", choices=["A", "B"], default="B")
    ap.add_argument("--results", help="write every event result to this JSON Lines file")
    ap.add_argument("--max-book-lines", type=int, default=20)
    args = ap.parse_args()

    book = OrderBookA() if args.version == "A" else OrderBookB()
    counts, fills, gross = {}, 0, 0
    out = open(args.results, "w") if args.results else None
    for event in iter_events(args.file):
        r = book.process(event)
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        for f in r.get("fills", []):
            fills += 1
            gross += f["price_ticks"] * f["qty_units"]
        if out:
            out.write(json.dumps(r) + "\n")
    if out:
        out.close()

    snap = book.snapshot()
    print(f"version {args.version}, file {args.file}")
    print("results by status: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"maker fills: {fills}, gross proceeds: {gross} tick-units = {gross / 10**10:,.2f} USD")
    for side in ("bids", "asks"):
        orders = snap[side]
        print(f"{side}: {len(orders)} active orders")
        for o in orders[:args.max_book_lines]:
            print(f"  {o['order_id']:>12} {o['price_ticks'] / 100:>12,.2f} USD "
                  f"{o['qty_units'] / 10**8:>12.8f} BTC  arrival {o['arrival_seq']}")
        if len(orders) > args.max_book_lines:
            print(f"  ... {len(orders) - args.max_book_lines} more")


if __name__ == "__main__":
    main()
