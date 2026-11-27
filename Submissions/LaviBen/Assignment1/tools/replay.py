#!/usr/bin/env python3
"""Replay a JSONL or JSONL.GZ event stream through either implementation."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orderbook.baseline import BaselineOrderBook  # noqa: E402
from orderbook.revised import RevisedOrderBook  # noqa: E402


def open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL or JSONL.GZ event file")
    parser.add_argument(
        "--version",
        choices=("baseline", "revised"),
        default="revised",
        help="implementation to replay (default: revised)",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="print each event result before the final summary",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    book_class = BaselineOrderBook if args.version == "baseline" else RevisedOrderBook
    book = book_class()
    events_processed = 0

    with open_text(args.input) as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise SystemExit(f"{args.input}:{line_number}: {error}") from error
            result = book.ProcessEvent(event)
            events_processed += 1
            if args.trace:
                print(json.dumps(result, separators=(",", ":"), sort_keys=True))

    print(
        json.dumps(
            {
                "version": args.version,
                "events_processed": events_processed,
                "last_accepted_seq": book.last_accepted_seq,
                "remaining_orders": book.InspectBook(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
