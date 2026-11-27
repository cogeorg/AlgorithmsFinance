"""Untimed, event-by-event A/B parity check for a supplied 10,000-event stream."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderbook.baseline import OrderBook as BaselineBook
from orderbook.revised import OrderBook as RevisedBook


def _read_events(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _check_invariants(snapshot: dict) -> int:
    bids = snapshot["bids"]
    asks = snapshot["asks"]
    active = bids + asks
    order_ids = [order["order_id"] for order in active]
    assert len(order_ids) == len(set(order_ids)), "duplicate active order IDs"
    assert all(order["qty_units"] > 0 for order in active), "nonpositive residual"
    if bids and asks:
        assert bids[0]["price_ticks"] < asks[0]["price_ticks"], "crossed resting book"
    return len(active)


def _save(path: Path, state: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        required=True,
        choices=("buildup", "crowded", "mixed", "sweep", "cancel_churn"),
    )
    parser.add_argument("--progress", type=Path, required=True)
    args = parser.parse_args()
    input_path = ROOT / "data" / f"{args.scenario}_10000.jsonl.gz"
    progress_path = args.progress
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    data = input_path.read_bytes()
    events = _read_events(input_path)
    baseline = BaselineBook()
    revised = RevisedBook()
    start = time.perf_counter()
    state = {
        "scenario": args.scenario,
        "input": str(input_path.relative_to(ROOT)),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "target_events": 10000,
        "status": "running",
        "completed_events": 0,
        "max_active_orders": 0,
        "started_elapsed_seconds": 0.0,
    }
    _save(progress_path, state)
    try:
        if len(events) != 10000:
            raise AssertionError(f"expected 10000 input events, got {len(events)}")
        for index, event in enumerate(events, 1):
            left = baseline.process_event(event)
            right = revised.process_event(event)
            if left != right:
                raise AssertionError(
                    f"ordered result mismatch after event {index}: {left!r} != {right!r}"
                )
            if baseline.last_accepted_seq != revised.last_accepted_seq:
                raise AssertionError(f"accepted sequence mismatch after event {index}")
            left_book = baseline.inspect_book()
            right_book = revised.inspect_book()
            if left_book != right_book:
                raise AssertionError(f"canonical book mismatch after event {index}")
            active = _check_invariants(left_book)
            state["completed_events"] = index
            state["max_active_orders"] = max(state["max_active_orders"], active)
            if index % 100 == 0:
                state["elapsed_seconds"] = time.perf_counter() - start
                _save(progress_path, state)
        state["status"] = "completed"
        state["elapsed_seconds"] = time.perf_counter() - start
        state["last_accepted_seq"] = baseline.last_accepted_seq
        _save(progress_path, state)
        print(json.dumps(state, indent=2))
        return 0
    except Exception as error:
        state["status"] = "failed"
        state["error"] = repr(error)
        state["elapsed_seconds"] = time.perf_counter() - start
        _save(progress_path, state)
        print(json.dumps(state, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
