"""Isolated worker for one Stage 4E measurement or diagnostic run."""

from __future__ import annotations

import csv
import gc
import gzip
import hashlib
import io
import json
import math
import os
import sys
import time
import traceback
import tracemalloc
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_ROOT = PROJECT_ROOT / "04_implementation"
sys.path.insert(0, str(IMPLEMENTATION_ROOT))

from orderbook import BaselineOrderBook, OptimizedOrderBook  # noqa: E402


TRACE_LIMIT_BYTES = 1024 * 1024 * 1024


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)


def _stable_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _stable_digest(value: Any) -> str:
    return hashlib.sha256(_stable_bytes(value)).hexdigest()


def _update_digest(digest: Any, value: Any) -> None:
    encoded = _stable_bytes(value)
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line {line_number}: {path}")
            event = json.loads(line)
            if type(event) is not dict:
                raise TypeError(f"line {line_number} is not an object: {path}")
            events.append(event)
    return events


def _engine_class(name: str) -> type[BaselineOrderBook] | type[OptimizedOrderBook]:
    if name == "baseline":
        return BaselineOrderBook
    if name == "optimized":
        return OptimizedOrderBook
    raise ValueError(f"unknown engine: {name}")


def _warm(engine_class: type[Any], events: list[dict[str, Any]]) -> None:
    disposable = engine_class()
    for event in events:
        disposable.process_event(event)


def _state_metrics(engine: Any) -> dict[str, int]:
    if isinstance(engine, BaselineOrderBook):
        prices = {(order.side, order.price_ticks) for order in engine._orders}
        queues: Counter[tuple[str, int]] = Counter(
            (order.side, order.price_ticks) for order in engine._orders
        )
        return {
            "active_orders": len(engine._orders),
            "occupied_price_levels": len(prices),
            "maximum_fifo_length": max(queues.values(), default=0),
            "bid_heap_entries": 0,
            "ask_heap_entries": 0,
            "stale_heap_entries": 0,
        }
    stale = sum(not engine._is_heap_entry_valid("BUY", entry) for entry in engine._bid_heap)
    stale += sum(not engine._is_heap_entry_valid("SELL", entry) for entry in engine._ask_heap)
    levels = list(engine._bid_levels.values()) + list(engine._ask_levels.values())
    return {
        "active_orders": len(engine._active_by_id),
        "occupied_price_levels": len(levels),
        "maximum_fifo_length": max((len(level.orders) for level in levels), default=0),
        "bid_heap_entries": len(engine._bid_heap),
        "ask_heap_entries": len(engine._ask_heap),
        "stale_heap_entries": stale,
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    if not values:
        raise ValueError("percentile requires observations")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _ordinary_median(values: list[int]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _latency_summary(rows: list[tuple[int, str, int, str]]) -> dict[str, Any]:
    groups: dict[str, list[int]] = {"all": [row[2] for row in rows]}
    for _, event_type, duration, window in rows:
        groups.setdefault(f"type:{event_type}", []).append(duration)
        if window != "middle":
            groups.setdefault(f"window:{window}", []).append(duration)
            groups.setdefault(f"window:{window}|type:{event_type}", []).append(duration)
    return {
        key: {
            "observations": len(values),
            "median_ns": _ordinary_median(values),
            "p95_nearest_rank_ns": _nearest_rank(values, 0.95),
            "p99_nearest_rank_ns": _nearest_rank(values, 0.99),
        }
        for key, values in sorted(groups.items())
    }


def _write_latency_csv(
    destination: Path,
    nonce: str,
    rows: list[tuple[int, str, int, str]],
) -> tuple[int, str]:
    if destination.exists():
        raise FileExistsError(f"latency output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".{nonce}.tmp")
    if temporary.exists():
        raise FileExistsError(f"latency temporary output already exists: {temporary}")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
                with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                    writer = csv.writer(text)
                    writer.writerow(("event_index", "event_type", "latency_ns", "window"))
                    writer.writerows(rows)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination.stat().st_size, _sha256(destination)


def _run_latency(spec: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    engine = _engine_class(spec["engine"])()
    calibration = []
    for _ in range(10_000):
        start = time.perf_counter_ns()
        calibration.append(time.perf_counter_ns() - start)
    window_size = max(1, len(events) // 10)
    rows: list[tuple[int, str, int, str]] = []
    replay_start = time.perf_counter()
    for offset, event in enumerate(events):
        start = time.perf_counter_ns()
        engine.process_event(event)
        duration = time.perf_counter_ns() - start
        window = "early" if offset < window_size else "late" if offset >= len(events) - window_size else "middle"
        rows.append((offset + 1, event["type"], duration, window))
    replay_seconds = time.perf_counter() - replay_start
    destination = PROJECT_ROOT / spec["latency_raw_path"]
    raw_bytes, raw_hash = _write_latency_csv(destination, spec["nonce"], rows)
    snapshot = engine.canonical_snapshot()
    return {
        "instrumented_replay_seconds": replay_seconds,
        "timer_calibration_median_ns": _ordinary_median(calibration),
        "timer_calibration_p99_ns": _nearest_rank(calibration, 0.99),
        "percentile_convention": "ordinary median; nearest-rank P95/P99",
        "early_late_convention": "first 10% and last 10% by stream position",
        "observations": len(rows),
        "summary": _latency_summary(rows),
        "raw_path": spec["latency_raw_path"],
        "raw_bytes": raw_bytes,
        "raw_sha256": raw_hash,
        "final_snapshot_digest": _stable_digest(snapshot),
        "final_state": _state_metrics(engine),
    }


def _run_memory(spec: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoints = {
        max(1, math.ceil(len(events) * 0.10)): "10_percent",
        max(1, math.ceil(len(events) * 0.50)): "50_percent",
        len(events): "100_percent",
    }
    state_engine = _engine_class(spec["engine"])()
    state_samples: dict[str, Any] = {}
    active_order_peak = 0
    occupied_price_level_peak = 0
    buildup_levels: set[tuple[str, int]] = set()
    state_pass_started = time.perf_counter()
    for index, event in enumerate(events, 1):
        state_engine.process_event(event)
        if isinstance(state_engine, BaselineOrderBook):
            active_orders = len(state_engine._orders)
            if spec["scenario"] == "buildup":
                buildup_levels.add((event["side"], event["price_ticks"]))
                occupied_levels = len(buildup_levels)
            else:
                occupied_levels = len(
                    {(order.side, order.price_ticks) for order in state_engine._orders}
                )
        else:
            active_orders = len(state_engine._active_by_id)
            occupied_levels = len(state_engine._bid_levels) + len(state_engine._ask_levels)
        active_order_peak = max(active_order_peak, active_orders)
        occupied_price_level_peak = max(occupied_price_level_peak, occupied_levels)
        if index in checkpoints:
            state_samples[checkpoints[index]] = _state_metrics(state_engine)
    state_pass_seconds = time.perf_counter() - state_pass_started
    state_snapshot_digest = _stable_digest(state_engine.canonical_snapshot())
    del state_engine
    del buildup_levels
    gc.collect()

    samples: dict[str, Any] = {}
    tracemalloc.start()
    try:
        engine = _engine_class(spec["engine"])()
        started = time.perf_counter()
        for index, event in enumerate(events, 1):
            event_result = engine.process_event(event)
            current_after_event, peak_after_event = tracemalloc.get_traced_memory()
            if index in checkpoints:
                samples[checkpoints[index]] = {
                    "event_index": index,
                    "traced_current_bytes": current_after_event,
                    "traced_peak_bytes": peak_after_event,
                    "state_from_untraced_equivalent_pass": state_samples[checkpoints[index]],
                }
            if index % 1000 == 0 and peak_after_event > TRACE_LIMIT_BYTES:
                raise MemoryError("traced allocations exceeded the approved 1 GiB safeguard")
            del event_result
        elapsed = time.perf_counter() - started
        current, peak = tracemalloc.get_traced_memory()
        snapshot = engine.canonical_snapshot()
        if _stable_digest(snapshot) != state_snapshot_digest:
            raise AssertionError("traced and untraced memory passes ended in different states")
        return {
            "traced_replay_seconds": elapsed,
            "untraced_state_pass_seconds": state_pass_seconds,
            "traced_current_bytes": current,
            "traced_peak_bytes": peak,
            "active_order_peak": active_order_peak,
            "occupied_price_level_peak": occupied_price_level_peak,
            "samples": samples,
            "post_stream": {
                "traced_current_bytes": current,
                "traced_peak_bytes": peak,
                "state": state_samples["100_percent"],
            },
            "boundary": {
                "preloaded_events_included": False,
                "engine_and_book_included": True,
                "event_results_retained": False,
                "returned_event_outputs": "current result held through its per-event allocation read, then discarded",
                "per_event_allocation_reads": len(events),
                "saved_trade_history_included": False,
                "state_inspection_in_traced_pass": False,
                "native_or_total_rss_included": False,
            },
            "final_snapshot_digest": _stable_digest(snapshot),
            "final_state": _state_metrics(engine),
        }
    finally:
        tracemalloc.stop()


def _run_concentration(spec: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    engine = _engine_class(spec["engine"])()
    started = time.perf_counter()
    for event in events:
        engine.process_event(event)
    engine_seconds = time.perf_counter() - started
    snapshot = engine.canonical_snapshot()
    state = _state_metrics(engine)
    return {
        "engine_seconds": engine_seconds,
        "final_snapshot_digest": _stable_digest(snapshot),
        "final_state": state,
        "active_order_peak": state["active_orders"],
        "occupied_price_level_peak": state["occupied_price_levels"],
        "maximum_fifo_length": state["maximum_fifo_length"],
        "peak_rule": "buildup contains only passive LIMIT events, so final values equal peaks",
    }


def _liquidation_oracle(
    snapshot: list[dict[str, Any]], order_id: str, quantity: int
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]], int, int]:
    residual = quantity
    fills: list[dict[str, Any]] = []
    remaining = {order["order_id"]: dict(order) for order in snapshot}
    levels: set[int] = set()
    proceeds = 0
    bids = [order for order in snapshot if order["side"] == "BUY"]
    for maker in bids:
        if residual == 0:
            break
        executed = min(residual, maker["qty_units"])
        fills.append(
            {
                "maker_id": maker["order_id"],
                "taker_id": order_id,
                "price_ticks": maker["price_ticks"],
                "qty_units": executed,
            }
        )
        levels.add(maker["price_ticks"])
        proceeds += maker["price_ticks"] * executed
        residual -= executed
        remaining[maker["order_id"]]["qty_units"] -= executed
        if remaining[maker["order_id"]]["qty_units"] == 0:
            del remaining[maker["order_id"]]
    expected_snapshot = sorted(
        remaining.values(),
        key=lambda order: (
            0 if order["side"] == "BUY" else 1,
            -order["price_ticks"] if order["side"] == "BUY" else order["price_ticks"],
            order["arrival_seq"],
        ),
    )
    return fills, residual, expected_snapshot, proceeds, len(levels)


def _construct_liquidation(spec: dict[str, Any], events: list[dict[str, Any]]) -> tuple[Any, dict[str, Any]]:
    engine = _engine_class(spec["engine"])()
    started = time.perf_counter()
    for event in events:
        engine.process_event(event)
    construction_seconds = time.perf_counter() - started
    snapshot = engine.canonical_snapshot()
    active_ids = {order["order_id"] for order in snapshot}
    depth = sum(order["qty_units"] for order in snapshot if order["side"] == "BUY")
    if depth <= 0:
        raise ValueError("liquidation source has no active bid depth")
    ratio = spec["ratio_percent"]
    quantity = max(1, (depth + 9) // 10) if ratio == 10 else depth if ratio == 100 else 2 * depth
    order_id = f"stage4e_liquidation_{spec['nonce']}"
    event_id = f"stage4e_liquidation_event_{spec['nonce']}"
    source_order_ids = {
        value
        for source_event in events
        for value in (source_event.get("order_id"), source_event.get("target_order_id"))
        if value is not None
    }
    source_event_ids = {source_event.get("event_id") for source_event in events}
    if order_id in active_ids or order_id in source_order_ids:
        raise ValueError("liquidation order identifier collides with source or active state")
    if event_id in source_event_ids:
        raise ValueError("liquidation event identifier collides with the source stream")
    last_seq = engine.last_accepted_seq
    if type(last_seq) is not int:
        raise ValueError("constructed book lacks an accepted sequence")
    next_seq = last_seq + 1
    if next_seq in {source_event.get("seq") for source_event in events}:
        raise ValueError("liquidation sequence collides with the source stream")
    event = {
        "seq": next_seq,
        "event_id": event_id,
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": quantity,
    }
    return engine, {
        "construction_seconds": construction_seconds,
        "pre_sale_snapshot": snapshot,
        "active_bid_depth_units": depth,
        "liquidation_quantity_units": quantity,
        "liquidation_event": event,
    }


def _execute_liquidation(engine: Any, context: dict[str, Any]) -> dict[str, Any]:
    event = context["liquidation_event"]
    expected_fills, expected_residual, expected_snapshot, proceeds, levels = _liquidation_oracle(
        context["pre_sale_snapshot"], event["order_id"], event["qty_units"]
    )
    started = time.perf_counter()
    result = engine.FillMarketSell(event)
    liquidation_seconds = time.perf_counter() - started
    final_snapshot = engine.canonical_snapshot()
    if result["fills"] != expected_fills:
        raise AssertionError("liquidation fills differ from independent oracle")
    if result["unfilled_qty_units"] != expected_residual:
        raise AssertionError("liquidation residual differs from independent oracle")
    if final_snapshot != expected_snapshot:
        raise AssertionError("liquidation final book differs from independent oracle")
    actual_proceeds = sum(fill["price_ticks"] * fill["qty_units"] for fill in result["fills"])
    if actual_proceeds != proceeds:
        raise AssertionError("liquidation proceeds differ from independent oracle")
    return {
        "construction_seconds": context["construction_seconds"],
        "liquidation_seconds": liquidation_seconds,
        "active_bid_depth_units": context["active_bid_depth_units"],
        "liquidation_quantity_units": context["liquidation_quantity_units"],
        "fill_count": len(result["fills"]),
        "makers_touched": len(result["fills"]),
        "price_levels_visited": levels,
        "unfilled_qty_units": result["unfilled_qty_units"],
        "proceeds_tick_quantity_units": proceeds,
        "result_digest": _stable_digest(result),
        "pre_sale_snapshot_digest": _stable_digest(context["pre_sale_snapshot"]),
        "final_snapshot_digest": _stable_digest(final_snapshot),
        "oracle_verified": True,
    }


class _DiagnosticOptimized(OptimizedOrderBook):
    def __init__(self) -> None:
        super().__init__()
        self.diagnostic_counts: Counter[str] = Counter()

    def _discard_stale_heap_top(self, side: str) -> None:
        before = len(self._heap_for_side(side))
        super()._discard_stale_heap_top(side)
        self.diagnostic_counts["stale_top_pops"] += before - len(self._heap_for_side(side))

    def _maybe_compact(self, side: str) -> None:
        heap = self._heap_for_side(side)
        levels = self._levels_for_side(side)
        threshold = self._COMPACTION_MULTIPLIER * len(levels) + self._COMPACTION_SLACK
        rebuild = len(heap) > threshold
        before = len(heap)
        self.diagnostic_counts["maybe_compact_calls"] += 1
        super()._maybe_compact(side)
        if rebuild:
            self.diagnostic_counts["heap_rebuilds"] += 1
            self.diagnostic_counts["heap_entries_before_rebuild"] += before
            self.diagnostic_counts["heap_entries_after_rebuild"] += len(heap)

    def _best_level(self, side: str) -> Any:
        self.diagnostic_counts["best_level_queries"] += 1
        return super()._best_level(side)


def _run_diagnostics(spec: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    if spec["engine"] == "optimized":
        measured: Any = _DiagnosticOptimized()
        reference: Any = OptimizedOrderBook()
    else:
        measured = BaselineOrderBook()
        reference = BaselineOrderBook()
    counts: Counter[str] = Counter()
    active_peak = 0
    level_peak = 0
    fifo_peak = 0
    result_digest = hashlib.sha256()
    diagnostic_started = time.perf_counter()

    for event in events:
        if spec["engine"] == "baseline":
            active_before = len(measured._orders)
            counts["estimated_active_list_observations"] += 1
            counts["estimated_active_list_length_sum"] += active_before
            counts["estimated_active_list_length_peak"] = max(
                counts["estimated_active_list_length_peak"], active_before
            )
            if event["type"] in {"LIMIT", "MARKET_SELL"}:
                counts["estimated_duplicate_id_comparisons"] += active_before
                counts["estimated_maker_filter_scan_entries"] += active_before
                if event["type"] == "MARKET_SELL":
                    eligible = sum(order.side == "BUY" for order in measured._orders)
                elif event["side"] == "BUY":
                    eligible = sum(
                        order.side == "SELL" and order.price_ticks <= event["price_ticks"]
                        for order in measured._orders
                    )
                else:
                    eligible = sum(
                        order.side == "BUY" and order.price_ticks >= event["price_ticks"]
                        for order in measured._orders
                    )
                counts["estimated_maker_sort_inputs"] += eligible
                counts["estimated_exhausted_cleanup_scan_entries"] += active_before
            elif event["type"] == "CANCEL":
                comparisons = active_before
                for index, order in enumerate(measured._orders):
                    if order.order_id == event["target_order_id"]:
                        comparisons = index + 1
                        break
                counts["estimated_cancellation_comparisons"] += comparisons

        measured_result = measured.process_event(event)
        reference_result = reference.process_event(event)
        if measured_result != reference_result:
            raise AssertionError("diagnostic wrapper changed an event result")
        counts["fills"] += len(measured_result.get("fills", ()))
        _update_digest(result_digest, measured_result)
        state = _state_metrics(measured)
        active_peak = max(active_peak, state["active_orders"])
        level_peak = max(level_peak, state["occupied_price_levels"])
        fifo_peak = max(fifo_peak, state["maximum_fifo_length"])

    measured_snapshot = measured.canonical_snapshot()
    reference_snapshot = reference.canonical_snapshot()
    if measured_snapshot != reference_snapshot:
        raise AssertionError("diagnostic wrapper changed the final snapshot")
    if isinstance(measured, _DiagnosticOptimized):
        counts.update(measured.diagnostic_counts)
        final_state = _state_metrics(measured)
        counts["final_stale_heap_entries"] = final_state["stale_heap_entries"]
        counts["final_heap_entries"] = (
            final_state["bid_heap_entries"] + final_state["ask_heap_entries"]
        )
    diagnostic_seconds = time.perf_counter() - diagnostic_started
    return {
        "diagnostic_seconds": diagnostic_seconds,
        "diagnostic_timing_boundary": "instrumented measured/reference dual replay plus state inspection; not primary timing",
        "operation_counts": dict(counts),
        "operation_count_semantics": (
            "baseline scan/comparison counts are analytical estimates from pre-event active state; "
            "optimized wrapper method calls, heap pops and rebuilds are directly observed; "
            "fills and state peaks are exact"
        ),
        "active_order_peak": active_peak,
        "occupied_price_level_peak": level_peak,
        "maximum_fifo_length": fifo_peak,
        "ordered_result_digest": result_digest.hexdigest(),
        "final_snapshot_digest": _stable_digest(measured_snapshot),
        "uninstrumented_equivalence_verified": True,
    }


def _run_self_test() -> None:
    assert _nearest_rank([1, 2, 3, 4], 0.95) == 4
    assert _nearest_rank([1, 2, 3, 4], 0.99) == 4
    assert _ordinary_median([1, 2, 3, 4]) == 2.5
    snapshot = [
        {"order_id": "b1", "side": "BUY", "price_ticks": 100, "qty_units": 3, "arrival_seq": 1},
        {"order_id": "b2", "side": "BUY", "price_ticks": 99, "qty_units": 2, "arrival_seq": 2},
        {"order_id": "a1", "side": "SELL", "price_ticks": 101, "qty_units": 7, "arrival_seq": 3},
    ]
    fills, residual, remaining, proceeds, levels = _liquidation_oracle(snapshot, "s", 4)
    assert [fill["maker_id"] for fill in fills] == ["b1", "b2"]
    assert residual == 0 and proceeds == 3 * 100 + 99 and levels == 2
    assert next(order for order in remaining if order["order_id"] == "b2")["qty_units"] == 1
    _emit({"type": "SELF_TEST", "status": "passed"})


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        _run_self_test()
        return 0
    nonce = sys.argv[1] if len(sys.argv) == 2 else ""
    stage = "specification"
    try:
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("controller did not provide a specification")
        spec = json.loads(line)
        if spec.get("nonce") != nonce:
            raise RuntimeError("specification nonce mismatch")
        stage = "preparation"
        preparation_start = time.perf_counter()
        workload = (PROJECT_ROOT / spec["workload_id"]).resolve(strict=True)
        warmup = (PROJECT_ROOT / spec["warmup_workload_id"]).resolve(strict=True)
        events = _load_events(workload)
        warmup_events = _load_events(warmup)
        if len(events) != spec["event_count"]:
            raise ValueError("workload event count differs from plan")
        engine_class = _engine_class(spec["engine"])
        _warm(engine_class, warmup_events)
        gc.collect()
        preparation_seconds = time.perf_counter() - preparation_start
        _emit(
            {
                "type": "READY",
                "nonce": nonce,
                "mode": spec["mode"],
                "event_count": len(events),
                "workload_sha256": _sha256(workload),
                "warmup_event_count": len(warmup_events),
                "preparation_seconds": preparation_seconds,
                "gc_enabled": gc.isenabled(),
                "measured_engine_is_fresh": True,
            }
        )
        command = json.loads(sys.stdin.readline())
        if command != {"type": "START", "nonce": nonce}:
            raise RuntimeError("invalid START command")
        _emit({"type": "STARTED", "nonce": nonce})
        stage = "measurement"
        if spec["mode"] == "latency":
            result = _run_latency(spec, events)
        elif spec["mode"] == "memory":
            result = _run_memory(spec, events)
        elif spec["mode"] == "concentration":
            result = _run_concentration(spec, events)
        elif spec["mode"] == "diagnostics":
            result = _run_diagnostics(spec, events)
        elif spec["mode"] == "liquidation":
            engine, context = _construct_liquidation(spec, events)
            _emit(
                {
                    "type": "CONSTRUCTED",
                    "nonce": nonce,
                    "construction_seconds": context["construction_seconds"],
                    "active_bid_depth_units": context["active_bid_depth_units"],
                    "liquidation_quantity_units": context["liquidation_quantity_units"],
                }
            )
            command = json.loads(sys.stdin.readline())
            if command != {"type": "LIQUIDATE", "nonce": nonce}:
                raise RuntimeError("invalid LIQUIDATE command")
            result = _execute_liquidation(engine, context)
        else:
            raise ValueError(f"unsupported mode: {spec['mode']}")
        _emit({"type": "DONE", "nonce": nonce, "result": result})
        return 0
    except BaseException as exc:
        _emit(
            {
                "type": "ERROR",
                "nonce": nonce,
                "stage": stage,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(limit=8),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
