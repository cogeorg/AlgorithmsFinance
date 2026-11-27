"""Replay JSON Lines event files through the common process_event() interface.

Example, from Assignment1:
    python -B dispatcher.py data/worked_example.jsonl --implementation compare

Events are processed in file order. If a later line is malformed, changes from
earlier accepted events remain in the book. The order book is responsible for
event validation, matching and cancellations.
"""

import argparse
import gzip
import json
from pathlib import Path


def read_events(source):
    """Yield JSON objects from an existing .jsonl or .jsonl.gz file."""
    path = Path(source)
    if path.is_dir():
        raise IsADirectoryError(f"Expected an event file, got a directory: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Event file not found: {path}")

    if path.name.endswith(".jsonl.gz"):
        opener = gzip.open
    elif path.name.endswith(".jsonl"):
        opener = open
    else:
        raise ValueError(f"Expected a .jsonl or .jsonl.gz event file: {path}")

    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(event, dict):
                raise ValueError(
                    f"{path}:{line_number}: each event must be a JSON object"
                )
            yield event


def replay_file(source, book):
    """Return ordered results while mutating the supplied book event by event."""
    events = read_events(source)
    try:
        return [book.process_event(event) for event in events]
    finally:
        # Close the file even if a book handler raises (important on Windows).
        events.close()


def main(argv=None):
    from order_book import IMPLEMENTATIONS, create_order_book

    parser = argparse.ArgumentParser(description="Replay an order book event file.")
    parser.add_argument("path", type=Path, help="A .jsonl or .jsonl.gz event file.")
    parser.add_argument(
        "--implementation", type=str.lower, choices=IMPLEMENTATIONS,
        default="baseline", help="Book version (default: baseline).",
    )
    args = parser.parse_args(argv)
    book = create_order_book(args.implementation)
    try:
        results = replay_file(args.path, book)
    except (OSError, ValueError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps({
        "implementation": args.implementation,
        "results": results,
        "book": book.inspect_book(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
