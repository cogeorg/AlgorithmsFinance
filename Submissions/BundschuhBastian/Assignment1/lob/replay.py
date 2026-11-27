"""Replay an event file through one version and print the results.

Usage (from Assignment1/):
    .venv/bin/python -m lob.replay data/worked_example.jsonl --version A
    .venv/bin/python -m lob.replay data/mixed_10000.jsonl.gz --version B --quiet

Prints one JSON result per event (unless --quiet), then a summary line with the final
snapshot, the total gross value in tick-units and in USD (display only, SPEC.md D17).
"""
from __future__ import annotations

import argparse
import json

from lob import VERSIONS
from lob.common import gross_value, load_events, proceeds_usd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="JSON Lines file, optionally .gz")
    parser.add_argument("--version", choices=sorted(VERSIONS), default="B")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    args = parser.parse_args(argv)

    book = VERSIONS[args.version]()
    total_value = 0
    counts: dict[str, int] = {}
    for event in load_events(args.path):
        result = book.process(event)
        total_value += gross_value(result["fills"])
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if not args.quiet:
            print(json.dumps(result, separators=(",", ":")))

    summary = {
        "version": args.version,
        "status_counts": counts,
        "gross_value_tick_units": total_value,
        "gross_value_usd": proceeds_usd(total_value),
        "remaining_orders": book.snapshot(),
    }
    print(json.dumps(summary, indent=None if args.quiet else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
