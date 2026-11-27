#!/usr/bin/env python3
"""Replay an event file through Version A or B and print results.

  python replay.py data/worked_example.jsonl --impl b
  python replay.py data/mixed_10000.jsonl.gz --impl a --quiet
"""
import argparse
import json
from collections import Counter

from lob.book_a import BookA
from lob.book_b import BookB
from lob.common import format_usd, gross_proceeds_tick_units, read_events


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--impl", choices=("a", "b"), default="b")
    p.add_argument("--quiet", action="store_true", help="print only a summary")
    args = p.parse_args()
    book = BookA() if args.impl == "a" else BookB()
    statuses = Counter()
    fills = proceeds = 0
    for ev in read_events(args.path):
        res = book.process(ev)
        statuses[res["status"]] += 1
        fills += len(res.get("fills", ()))
        proceeds += gross_proceeds_tick_units(res.get("fills", ()))
        if not args.quiet:
            print(json.dumps(res))
    remaining = book.inspect_book()
    if not args.quiet:
        print("remaining_orders:")
        for o in remaining:
            print(json.dumps(o))
    print(json.dumps({"impl": args.impl.upper(), "statuses": dict(statuses), "fills": fills,
                      "gross_proceeds_tick_units": proceeds,
                      "gross_proceeds_usd": format_usd(proceeds),
                      "remaining_orders": len(remaining)}))


if __name__ == "__main__":
    main()
