"""Isolated worker for one benchmark replay; invoked by run_benchmarks.py."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_ROOT = PROJECT_ROOT / "04_implementation"
sys.path.insert(0, str(IMPLEMENTATION_ROOT))

from orderbook import BaselineOrderBook, OptimizedOrderBook  # noqa: E402


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_events(path: Path) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line {line_number}")
            event = json.loads(line)
            if type(event) is not dict:
                raise ValueError(f"line {line_number} is not a JSON object")
            events.append(event)
            canonical = json.dumps(
                event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            digest.update(len(canonical).to_bytes(8, "big"))
            digest.update(canonical)
    return events, digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("baseline", "optimized"), required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--workload-id", required=True)
    parser.add_argument("--expected-events", type=int, required=True)
    parser.add_argument("--nonce", required=True)
    args = parser.parse_args()

    stage = "preparation"
    try:
        preparation_start = time.perf_counter()
        workload = Path(args.workload).resolve(strict=True)
        events, event_stream_digest = _load_events(workload)
        if len(events) != args.expected_events:
            raise ValueError(
                f"expected {args.expected_events} events, observed {len(events)}"
            )
        engine_class = (
            BaselineOrderBook if args.engine == "baseline" else OptimizedOrderBook
        )
        engine = engine_class()
        gc.collect()
        preparation_seconds = time.perf_counter() - preparation_start
        workload_sha256 = hashlib.sha256(workload.read_bytes()).hexdigest()
        _emit(
            {
                "type": "READY",
                "nonce": args.nonce,
                "pid": __import__("os").getpid(),
                "engine": args.engine,
                "workload_id": args.workload_id,
                "event_count": len(events),
                "event_stream_digest": event_stream_digest,
                "workload_sha256": workload_sha256,
                "preparation_seconds": preparation_seconds,
                "gc_enabled": gc.isenabled(),
            }
        )

        stage = "handshake"
        command_line = sys.stdin.readline()
        if not command_line:
            raise RuntimeError("controller closed stdin before START")
        command = json.loads(command_line)
        if command != {"type": "START", "nonce": args.nonce}:
            raise RuntimeError("invalid START command or nonce")
        _emit({"type": "STARTED", "nonce": args.nonce})

        stage = "processing"
        start = time.perf_counter()
        for event in events:
            engine.process_event(event)
        engine_seconds = time.perf_counter() - start

        stage = "post_run"
        snapshot = engine.canonical_snapshot()
        _emit(
            {
                "type": "DONE",
                "nonce": args.nonce,
                "engine_seconds": engine_seconds,
                "snapshot_digest": _stable_digest(snapshot),
                "final_active_orders": len(snapshot),
                "last_accepted_seq": engine.last_accepted_seq,
            }
        )
        return 0
    except BaseException as exc:
        _emit(
            {
                "type": "ERROR",
                "nonce": args.nonce,
                "stage": stage,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-8:],
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
