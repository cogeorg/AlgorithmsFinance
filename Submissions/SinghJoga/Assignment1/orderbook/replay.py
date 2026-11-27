"""Replay a JSONL or JSONL.GZ event stream through one saved engine version."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any, TextIO


def _open_events(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def replay(path: Path, version: str) -> dict[str, Any]:
    if version == "baseline":
        from orderbook.baseline import OrderBook
    else:
        from orderbook.revised import OrderBook

    book = OrderBook()
    results = []
    with _open_events(path) as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at line {line_number}: {error}") from error
            results.append(book.process_event(event))
    return {
        "version": version,
        "last_accepted_seq": book.last_accepted_seq,
        "results": results,
        "book": book.inspect_book(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL or JSONL.GZ event stream")
    parser.add_argument("--version", choices=("baseline", "revised"), default="baseline")
    args = parser.parse_args()
    print(json.dumps(replay(args.input, args.version), indent=2))


if __name__ == "__main__":
    main()
