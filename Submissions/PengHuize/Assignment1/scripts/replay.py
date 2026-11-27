"""Replay one JSONL or JSONL.GZ stream with either implementation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lob import make_book
from lob.io import read_events, replay_events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--version", choices=("A", "B"), default="B")
    parser.add_argument("--validate-each", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    read_start = time.perf_counter()
    events = read_events(args.path)
    read_seconds = time.perf_counter() - read_start

    book = make_book(args.version)
    replay_start = time.perf_counter()
    results = replay_events(
        book, events, keep_results=True, validate_each=args.validate_each
    )
    replay_seconds = time.perf_counter() - replay_start
    payload = {
        "version": book.version,
        "source": str(args.path),
        "event_count": len(events),
        "read_parse_seconds": read_seconds,
        "replay_seconds": replay_seconds,
        "throughput_events_per_second": len(events) / replay_seconds,
        "results": results,
        "remaining_orders": book.inspect_book(),
    }
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
