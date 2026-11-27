"""Replay an event file through Version A or B and print a summary.

Usage:
    python3 replay.py data/worked_example.jsonl
    python3 replay.py data/mixed_10000.jsonl.gz --version B
"""
import argparse
import gzip
import json

from orderbook.version_a import OrderBook as BookA
from orderbook.version_b import OrderBook as BookB


def read_events(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--version", choices=["A", "B"], default="A")
    args = parser.parse_args()

    book = BookA() if args.version == "A" else BookB()
    events = read_events(args.path)
    counts = {}
    last = None
    for event in events:
        last = book.process_event(event)
        counts[last["status"]] = counts.get(last["status"], 0) + 1

    print(f"Version {args.version}: {len(events)} events replayed")
    print("Status counts:", counts)
    print("Last result:", json.dumps(last, indent=2))
    print("Remaining active orders:", len(book.snapshot()))


if __name__ == "__main__":
    main()