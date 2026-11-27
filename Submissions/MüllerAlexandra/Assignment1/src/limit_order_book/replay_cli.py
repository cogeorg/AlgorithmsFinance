"""Replay one JSON Lines event file with either submitted implementation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from .baseline import BaselineOrderBook
from .revised import RevisedOrderBook
from .stream_io import iter_events, replay_events


JsonObject = dict[str, Any]
IMPLEMENTATIONS = {
    "baseline": BaselineOrderBook,
    "revised": RevisedOrderBook,
}


def build_replay_document(*, version: str, input_path: Path) -> JsonObject:
    """Replay a plain/gzip JSON Lines file and return results plus final state."""
    try:
        factory = IMPLEMENTATIONS[version]
    except KeyError as error:
        raise ValueError(f"unknown version: {version}") from error

    resolved = input_path.resolve(strict=True)
    book = factory()
    results = replay_events(book, iter_events(resolved))
    final_book = book.inspect_book()
    rejected = sum(result.get("status") == "rejected" for result in results)
    return {
        "schema_version": 1,
        "version": version,
        "input": {
            "path": str(resolved),
            "gzip_compressed": resolved.suffix == ".gz",
            "event_count": len(results),
        },
        "retained_event_results": True,
        "results": results,
        "final_book": final_book,
        "summary": {
            "event_count": len(results),
            "rejected_event_count": rejected,
            "final_active_orders": len(final_book),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        choices=sorted(IMPLEMENTATIONS),
        required=True,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Plain .jsonl or gzip-compressed .jsonl.gz event stream",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Exclusive JSON output path; omit to print JSON to standard output",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    document = build_replay_document(
        version=args.version,
        input_path=args.input,
    )
    text = json.dumps(document, indent=2) + "\n"
    if args.out is None:
        sys.stdout.write(text)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return 0
