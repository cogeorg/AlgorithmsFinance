"""Isolated measurements. Launched by benchmark.py; standard library only."""
from collections import Counter
from contextlib import contextmanager
import copy
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import signal
import statistics
import sys
import time
import threading
import tracemalloc

from lob.version_a import OrderBook as VersionA
from lob.version_b import OrderBook as VersionB

ROOT = Path(__file__).resolve().parent


class PhaseTimeout(Exception):
    pass


@contextmanager
def deadline(seconds):
    def expired(signum, frame):
        raise PhaseTimeout("phase wall-time limit exceeded")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def emit(config, **values):
    row = {k: config.get(k) for k in ("job_id", "version", "scenario", "seed", "event_count", "levels")}
    row.update(values)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    row["worker_reported_max_rss_bytes"] = rss if sys.platform == "darwin" else rss * 1024
    sys.stdout.write(json.dumps(row, separators=(",", ":"))+"\n")
    sys.stdout.flush()


def read_events(path, maximum=None):
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            rows.append(json.loads(line))
            if maximum is not None and len(rows) >= maximum:
                break
    return rows


def digest(book):
    data = json.dumps(book.inspect_book(), separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def percentile(values, fraction):
    """Nearest-rank: sorted sample at ceil(p*n)-1; no interpolation."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def summarize_latencies(samples):
    return dict(samples=len(samples), median_seconds=statistics.median(samples) if samples else None,
                p95_seconds=percentile(samples, .95), p99_seconds=percentile(samples, .99))


def metadata(config):
    """Untimed workload accounting, using B independently from measured engines."""
    book = VersionB()
    alive, prices = {}, Counter()
    peak_b = peak_p = total_fills = 0
    rows = read_events(config["path"])
    for event in rows:
        result = book.process_event(event)
        if result["status"] == "rejected":
            raise AssertionError("generated input was rejected")
        total_fills += len(result.get("fills", []))
        for fill in result.get("fills", []):
            oid = fill["maker_id"]
            alive[oid][1] -= fill["qty_units"]
            if not alive[oid][1]:
                key, _ = alive.pop(oid)
                prices[key] -= 1
                if not prices[key]:
                    del prices[key]
        if event["type"] == "CANCEL" and result["status"] == "cancelled":
            key, _ = alive.pop(event["target_order_id"])
            prices[key] -= 1
            if not prices[key]:
                del prices[key]
        elif event["type"] == "LIMIT" and result["unfilled_qty_units"]:
            key = (event["side"], event["price_ticks"])
            alive[event["order_id"]] = [key, result["unfilled_qty_units"]]
            prices[key] += 1
        peak_b, peak_p = max(peak_b, len(alive)), max(peak_p, len(prices))
    snapshot = book.inspect_book()
    if len(alive) != len(snapshot) or sum(v[1] for v in alive.values()) != sum(o["qty_units"] for o in snapshot):
        raise AssertionError("independent workload accounting mismatch")
    return dict(active_order_peak=peak_b, price_level_peak=peak_p,
                fill_count=total_fills, remaining_orders=len(snapshot),
                final_digest=digest(book), counts_source="separate B workload-accounting replay")


def primary(config, factory):
    # Same small warm-up prefix for both versions; no timed run reuses its book.
    warm = read_events(config["path"], 1000)
    book = factory()
    for event in warm:
        book.process_event(event)
    del book, warm
    prefix = (config["event_count"] if config["scenario"] in ("buildup", "crowded")
              else config["event_count"] * 4 // 5 if config["scenario"] == "sweep" else None)
    for repeat in range(1, config["repeats"] + 1):
        start_app = time.perf_counter()
        try:
            with deadline(config["phase_limit_seconds"]):
                events = read_events(config["path"])
        except PhaseTimeout:
            emit(config, phase="input_parse", repeat=repeat, status="stopped_time_limit",
                 elapsed_seconds=time.perf_counter() - start_app)
            for phase in ("replay", "parse_plus_replay"):
                emit(config, phase=phase, repeat=repeat, status="not_run_input_time_limit",
                     elapsed_seconds=None, events_processed=0)
            if prefix is not None:
                emit(config, phase="construction", repeat=repeat, status="not_run_input_time_limit",
                     elapsed_seconds=None, events_processed=0)
            continue
        parsed = time.perf_counter() - start_app
        emit(config, phase="input_parse", repeat=repeat, status="completed", elapsed_seconds=parsed)
        count = 0
        fills = 0
        construction = None
        status = "completed"
        start = time.perf_counter()
        try:
            with deadline(config["phase_limit_seconds"]):
                book = factory()
                for event in events:
                    result = book.process_event(event)
                    count += 1
                    fills += len(result.get("fills", []))
                    if count == prefix:
                        construction = time.perf_counter() - start
        except PhaseTimeout:
            status = "stopped_time_limit"
        elapsed = time.perf_counter() - start
        # All reporting, inspection, hashes and stdout writes are outside engine time.
        if status == "completed":
            if count != config["event_count"] or (config["metadata"]["final_digest"] is not None and digest(book) != config["metadata"]["final_digest"]):
                raise AssertionError("measured engine final state differs from reference")
        emit(config, phase="replay", repeat=repeat, status=status,
             elapsed_seconds=elapsed, events_processed=count, fill_count=fills,
             throughput_events_per_second=count / elapsed if status == "completed" else None,
             active_order_peak=config["metadata"]["active_order_peak"],
             price_level_peak=config["metadata"]["price_level_peak"],
             peak_source="separate workload-accounting replay, not primary instrumentation",
             correctness=("final_digest_matches" if config["metadata"]["final_digest"] is not None else "no_reference_for_optional_million") if status == "completed" else "not_checked_partial")
        # A directly observed composition of this repeat's parse and replay clocks.
        # Diagnostic emit/inspection time between phases is intentionally excluded.
        emit(config, phase="parse_plus_replay", repeat=repeat, status=status,
             elapsed_seconds=parsed + elapsed, events_processed=count,
             measurement="sum of same-repeat measured parse and replay, excludes reporting")
        if prefix is not None:
            emit(config, phase="construction", repeat=repeat,
                 status="completed" if construction is not None else status,
                 elapsed_seconds=construction if construction is not None else elapsed,
                 events_processed=prefix if construction is not None else count,
                 measurement="prefix checkpoint within the same uninterrupted replay; not additive")
        del book, events


def latency(config, factory):
    events = read_events(config["path"])
    warm = factory()
    for event in events[:1000]:
        warm.process_event(event)
    del warm
    samples, types = [], []
    book = factory()
    status = "completed"
    start = time.perf_counter()
    try:
        with deadline(config["phase_limit_seconds"]):
            for event in events:
                begin = time.perf_counter()
                result = book.process_event(event)
                elapsed = time.perf_counter() - begin
                samples.append(elapsed)
                types.append(event["type"])
    except PhaseTimeout:
        status = "stopped_time_limit"
    if status == "completed" and digest(book) != config["metadata"]["final_digest"]:
        raise AssertionError("latency-run final state mismatch")
    output = Path(config["results_dir"]) / "latency" / (config["job_id"] + ".csv.gz")
    output.parent.mkdir(exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("event_index", "event_type", "elapsed_seconds", "position"))
        for index, (elapsed, kind) in enumerate(zip(samples, types), 1):
            position = "early" if index <= max(1, len(events) // 10) else "late" if index > len(events) * 9 // 10 else "middle"
            writer.writerow((index, kind, format(elapsed, ".12g"), position))
    emit(config, phase="latency", repeat=1, status=status, events_processed=len(samples),
         raw_file=str(output.relative_to(Path(config["results_dir"]))),
         population="full_stream" if status == "completed" else "completed_events_prefix_only",
         percentile_convention="nearest_rank_ceil_p_times_n", **summarize_latencies(samples))
    for kind in ("LIMIT", "CANCEL", "MARKET_SELL"):
        subset = [s for s, t in zip(samples, types) if t == kind]
        if subset:
            emit(config, phase="latency_by_type", repeat=1, event_type=kind, status=status,
                 **summarize_latencies(subset))
    for label, subset in (("early", samples[:max(1, len(events) // 10)]),
                          ("late", samples[len(events) * 9 // 10:])):
        if subset:
            emit(config, phase="latency_by_position", repeat=1, position=label, status=status,
                 **summarize_latencies(subset))


def memory(config, factory):
    # Input parsing and existing event objects precede tracing in both engines.
    events = read_events(config["path"])
    count = 0
    samples = []
    status = "completed"
    tracemalloc.start()
    start = time.perf_counter()
    try:
        with deadline(config["phase_limit_seconds"]):
            book = factory()
            for event in events:
                result = book.process_event(event)
                count += 1
                if count in (1, 2) or count % max(1, len(events) // 10) == 0:
                    current, peak = tracemalloc.get_traced_memory()
                    samples.append(dict(event_index=count, traced_current_bytes=current,
                        traced_peak_bytes=peak, active_orders=len(book._orders)))
    except PhaseTimeout:
        status = "stopped_time_limit"
    # Keep current event output alive while taking the allocation readings.
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if status == "completed" and digest(book) != config["metadata"]["final_digest"]:
        raise AssertionError("memory-run final state mismatch")
    emit(config, phase="memory", repeat=1, status=status, events_processed=count,
         traced_peak_bytes=peak, traced_current_bytes=current,
         memory_scope="incremental engine allocations + live latest output + small probe buffer; excludes preloaded input allocations",
         snapshots=samples)


def operations(config, factory):
    events = read_events(config["path"], 200)
    book = factory()
    counts = Counter()
    source = str(ROOT / "lob" / ("version_a.py" if config["version"] == "A" else "version_b.py"))
    def trace(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == source:
            counts[frame.f_lineno] += 1
        return trace
    sys.settrace(trace)
    try:
        for event in events:
            book.process_event(event)
    finally:
        sys.settrace(None)
    source_lines = Path(source).read_text().splitlines()
    emit(config, phase="operation_counts", repeat=1, status="completed", events_processed=len(events),
         line_counts=[dict(line=n, executions=c, source=source_lines[n-1].strip()) for n,c in sorted(counts.items())],
         measurement="separate 200-event line-traced diagnostic; never primary timing")


def bid_events(count, levels, seed):
    rng = random.Random(seed)
    return [dict(seq=i + 1, event_id=f"b{i}", type="LIMIT", order_id=f"b{i}", side="BUY",
                 price_ticks=6000000 - rng.randrange(levels), qty_units=rng.randint(1, 100) * 1000000)
            for i in range(count)]


def liquidation(config, factory):
    events = bid_events(config["event_count"], config["levels"], config["seed"])
    total = sum(e["qty_units"] for e in events)
    template = factory()
    warm = factory()
    for event in events[:1000]:
        warm.process_event(event)
    del warm
    start = time.perf_counter()
    try:
        with deadline(config["phase_limit_seconds"]):
            for event in events:
                template.process_event(event)
    except PhaseTimeout:
        emit(config, phase="sell_template_construction", repeat=1, status="stopped_time_limit",
             elapsed_seconds=time.perf_counter() - start)
        # Preserve every planned sale, explicitly blocked before matching.
        for ratio in (10, 100, 200):
            for repeat in range(1, config["repeats"] + 1):
                emit(config, phase="individual_sale", repeat=repeat, sale_percent=ratio,
                     requested_qty_units=max(1, (total * ratio + 99) // 100),
                     status="not_run_template_time_limit", elapsed_seconds=None)
        return
    emit(config, phase="sell_template_construction", repeat=1, status="completed", elapsed_seconds=time.perf_counter()-start)
    makers = sorted(events, key=lambda e: (-e["price_ticks"], e["seq"]))
    for ratio in (10, 100, 200):
        requested = max(1, (total * ratio + 99) // 100)
        expected = []
        remainder = requested
        for e in makers:
            quantity = min(remainder, e["qty_units"])
            if quantity:
                expected.append(dict(maker_id=e["order_id"], taker_id="sale",
                    price_ticks=e["price_ticks"], qty_units=quantity))
                remainder -= quantity
            if not remainder:
                break
        sell = dict(seq=len(events)+1, event_id="sale", type="MARKET_SELL", order_id="sale", qty_units=requested)
        # Warm up the same sale shape on a disposable fresh clone.
        warm = copy.deepcopy(template)
        warm.FillMarketSell(sell)
        del warm
        for repeat in range(1, config["repeats"] + 1):
            start = time.perf_counter()
            try:
                with deadline(config["phase_limit_seconds"]):
                    book = copy.deepcopy(template)
            except PhaseTimeout:
                emit(config, phase="sell_reset", repeat=repeat, sale_percent=ratio, status="stopped_time_limit",
                     elapsed_seconds=time.perf_counter()-start)
                emit(config, phase="individual_sale", repeat=repeat, sale_percent=ratio,
                     requested_qty_units=requested, status="not_run_reset_time_limit", elapsed_seconds=None)
                continue
            reset = time.perf_counter()-start
            emit(config, phase="sell_reset", repeat=repeat, sale_percent=ratio, status="completed", elapsed_seconds=reset)
            start = time.perf_counter()
            try:
                with deadline(config["phase_limit_seconds"]):
                    result = book.FillMarketSell(sell)
            except PhaseTimeout:
                emit(config, phase="individual_sale", repeat=repeat, sale_percent=ratio,
                     requested_qty_units=requested, status="stopped_time_limit", elapsed_seconds=time.perf_counter()-start)
                del book
                continue
            elapsed = time.perf_counter()-start
            if result["fills"] != expected or result["unfilled_qty_units"] != remainder:
                raise AssertionError("liquidation differs from independent sorted-prefix expectation")
            emit(config, phase="individual_sale", repeat=repeat, status="completed", elapsed_seconds=elapsed,
                 sale_percent=ratio, requested_qty_units=requested, available_bid_qty_units=total,
                 fill_count=len(result["fills"]), makers_touched=len(result["fills"]),
                 price_levels_visited=len({f["price_ticks"] for f in result["fills"]}),
                 unfilled_qty_units=result["unfilled_qty_units"], reset_seconds=reset,
                 active_order_peak=len(events), price_level_peak=len({e["price_ticks"] for e in events}),
                 correctness="independent_price_fifo_prefix_matches")
            del book


def main():
    config = json.loads(sys.argv[1])
    # Process-local RSS guard avoids privileged process inspection. Sampling is
    # outside engine calls, but its small background cost affects both versions.
    def guard():
        while True:
            time.sleep(.1)
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss = rss if sys.platform == "darwin" else rss * 1024
            if rss > config["rss_limit_bytes"]:
                emit(config, phase="worker", repeat=1, status="stopped_rss_limit", elapsed_seconds=None)
                os._exit(93)
    threading.Thread(target=guard, daemon=True).start()
    factory = VersionA if config.get("version") == "A" else VersionB
    mode = config["mode"]
    if mode == "metadata":
        result = metadata(config)
        emit(config, phase="workload_metadata", repeat=1, status="completed", **result)
    elif mode == "timing":
        primary(config, factory)
    elif mode == "latency":
        latency(config, factory)
    elif mode == "memory":
        memory(config, factory)
    elif mode == "operations":
        operations(config, factory)
    elif mode == "liquidation":
        liquidation(config, factory)
    else:
        raise ValueError(mode)


if __name__ == "__main__":
    main()
