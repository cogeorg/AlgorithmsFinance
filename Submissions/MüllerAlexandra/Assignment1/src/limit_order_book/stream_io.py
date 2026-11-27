"""JSON Lines and gzip replay helpers independent of matching logic."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
import gzip
import json
from pathlib import Path
from typing import TextIO

from .interface import Event, EventResult, OrderBook


def iter_events(path: Path) -> Iterator[dict[str, object]]:
    """Yield JSON events from a plain or gzip-compressed JSON Lines file."""

    handle: TextIO
    if path.suffix == ".gz":
        handle = gzip.open(path, mode="rt", encoding="utf-8", newline="")
    else:
        handle = path.open(mode="r", encoding="utf-8", newline="")

    with handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            yield value


def replay_events(book: OrderBook, events: Iterable[Event]) -> list[EventResult]:
    """Process events in iteration order and return one result per event."""

    return [book.process_event(event) for event in events]

