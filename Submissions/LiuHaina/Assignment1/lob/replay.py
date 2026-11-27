"""Replay JSONL or JSONL.gz without retaining full event/trade history."""
import argparse
import gzip
import json
from pathlib import Path
from .version_a import OrderBook as VersionA
from .version_b import OrderBook as VersionB


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--version", choices=("a", "b"), default="a")
    args = parser.parse_args()
    book = VersionA() if args.version == "a" else VersionB()
    count = rejected = gross = 0
    last = None
    opener = gzip.open if args.path.suffix == ".gz" else open
    with opener(args.path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                parser.error(f"invalid JSON at line {line_number}: {exc.msg}")
            last = book.process_event(event)
            count += 1
            rejected += last["status"] == "rejected"
            gross += sum(f["price_ticks"] * f["qty_units"] for f in last.get("fills", []))
    dollars, fraction = divmod(gross, 10**10)
    print(json.dumps(dict(version=args.version.upper(), events=count, rejected_events=rejected,
        last_result=last, remaining_orders=book.inspect_book(),
        total_gross_proceeds_tick_units=gross,
        total_gross_proceeds_usd_exact=f"{dollars}.{fraction:010d}"), indent=2))


if __name__ == "__main__":
    main()
