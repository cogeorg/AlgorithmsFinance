"""JSON Lines input and replay helpers."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterable

from .common import BaseLimitOrderBook


def read_events(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def replay_events(
    book: BaseLimitOrderBook,
    events: Iterable[dict[str, Any]],
    *,
    keep_results: bool = True,
    validate_each: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for event in events:
        result = book.process_event(event)
        if keep_results:
            results.append(result)
        if validate_each and result["status"] != "rejected":
            book.validate_invariants()
    return results
