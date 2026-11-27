"""Isolated warmed-primary worker; invoked only by run_warmed_primary.py."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_ROOT = PROJECT_ROOT / "04_implementation"
WARMUP_ID = "02_data/generated/mixed_1000_seed42.jsonl.gz"
WARMUP_PATH = PROJECT_ROOT / WARMUP_ID
sys.path.insert(0, str(IMPLEMENTATION_ROOT))

from orderbook import BaselineOrderBook, OptimizedOrderBook  # noqa: E402


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_events(path: Path) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line {line_number}: {path}")
            event = json.loads(line)
            if type(event) is not dict:
                raise ValueError(f"line {line_number} is not a JSON object: {path}")
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
        warmup = WARMUP_PATH.resolve(strict=True)
        events, event_stream_digest = _load_events(workload)
        warmup_events, warmup_stream_digest = _load_events(warmup)
        if len(events) != args.expected_events:
            raise ValueError(
                f"expected {args.expected_events} events, observed {len(events)}"
            )
        if len(warmup_events) != 1_000:
            raise ValueError(f"warm-up must contain 1000 events, observed {len(warmup_events)}")
        warmup_sha256 = _sha256(warmup)
        expected_warmup_sha256 = os.environ.get("WARMED_PRIMARY_WARMUP_SHA256")
        if not expected_warmup_sha256 or warmup_sha256 != expected_warmup_sha256:
            raise ValueError("warm-up hash differs from the controller-verified identity")

        engine_class = BaselineOrderBook if args.engine == "baseline" else OptimizedOrderBook
        disposable = engine_class()
        for event in warmup_events:
            disposable.process_event(event)
        del disposable
        gc.collect()
        engine = engine_class()
        if engine.last_accepted_seq is not None or engine.canonical_snapshot() != []:
            raise AssertionError("measured engine is not fresh and empty after warm-up")

        preparation_seconds = time.perf_counter() - preparation_start
        workload_sha256 = _sha256(workload)
        _emit(
            {
                "type": "READY",
                "nonce": args.nonce,
                "pid": os.getpid(),
                "engine": args.engine,
                "workload_id": args.workload_id,
                "event_count": len(events),
                "event_stream_digest": event_stream_digest,
                "workload_sha256": workload_sha256,
                "preparation_seconds": preparation_seconds,
                "gc_enabled": gc.isenabled(),
                "warmup_workload_id": WARMUP_ID,
                "warmup_event_count": len(warmup_events),
                "warmup_sha256": warmup_sha256,
                "warmup_stream_digest": warmup_stream_digest,
                "warmup_engine": "disposable_same_class",
                "measured_engine_fresh_empty": True,
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
