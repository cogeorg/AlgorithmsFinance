"""Reproducible order-book benchmarks; timing, latency and memory stay separate.

Run python -B benchmark.py --help. All measurements use the standard library.
The default matrix is a plan until the explicit run command is used.
"""

import argparse
from datetime import datetime, timezone
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
import uuid
import zlib

import generate_orders


ROOT = Path(__file__).resolve().parent
SCENARIOS = generate_orders.SCENARIOS
VERSIONS = ("baseline", "revised")
EXPERIMENTS = ("replay", "market-sell", "queue-concentration", "cancel-churn")
PHASES = ("io", "timing", "latency", "memory", "diagnostics")
REPETITIONS = 5
METRICS = (
    "read_seconds", "decompress_seconds", "parse_seconds", "io_total_seconds",
    "initialization_seconds", "construction_seconds", "replay_seconds",
    "total_compute_seconds", "throughput_events_per_second",
    "latency_median_seconds", "latency_p95_seconds", "latency_p99_seconds",
    "latency_sample_count", "memory_peak_bytes", "memory_current_bytes",
    "memory_after_construction_bytes", "memory_before_final_cancel_bytes",
    "memory_after_cancellation_bytes", "active_orders_peak", "occupied_prices_peak",
    "retained_queue_entries_peak", "inactive_queue_entries_peak", "heap_entries_peak",
    "active_orders_final", "occupied_prices_final", "retained_queue_entries_final",
    "inactive_queue_entries_final", "heap_entries_final",
    "retained_queue_entries_before_final_cancel", "inactive_entries_before_final_cancel",
    "heap_entries_before_final_cancel", "active_orders_before_final_cancel",
    "fill_count", "price_levels_visited", "unfilled_qty_units", "cancelled_qty_units",
    "rejected_event_count", "processed_events", "compressed_bytes", "decoded_bytes",
)
BOUNDARIES = {
    "clock": "time.perf_counter; GC enabled, collect before each repetition",
    "io": "Warm-cache reads, gzip decompression and UTF-8/JSON parsing timed separately; "
          "validation and SHA-256 checks outside clocks. Five reads plus an untimed warm-up.",
    "timing": "Preloaded events; direct engine classes; five fresh books and an untimed "
              "fresh-book warm-up. No inspection, counters, deepcopy or comparison. "
              "Replay discards each returned result; single-sale retains its result "
              "until the clock stops. Result creation is included.",
    "total_compute": "Initialization + construction + replay, summed within each repetition. "
                     "I/O excluded. Summary is median of these sums, not sum of medians.",
    "latency": "Separate instrumented pass; clocks surround each process_event call and "
               "result disposal for replay. Sample-list append excluded. No overhead "
               "subtraction. Single-sale experiments use five fresh books/samples.",
    "percentiles": "Median uses statistics.median (average middle pair for even n); "
                   "P95/P99 use nearest rank, sorted[ceil(p*n)-1], without interpolation.",
    "memory": "Separate worker process and separate tracemalloc run per fresh book. "
              "Input, imports and warm-up excluded; book construction, setup, engine "
              "allocations and transient results included. No saved event-result history. "
              "Current bytes measured after GC; peak includes temporary cleanup and "
              "instrumentation allocations. Tracemalloc is Python allocation memory, "
              "not process RSS. Five repetitions; construction checkpoint included.",
    "diagnostics": "Separate untimed pass; counters after every setup/replay event. "
                   "Final canonical snapshot and ordered-result digests compare versions. "
                   "Diagnostic costs are never part of primary timing.",
    "limits": "Per-worker wall timeout and global campaign deadline are enforced by the "
              "parent. Compressed/decompressed payload limits checked before parse. "
              "Traced-allocation cap checked between memory-run events; an individual "
              "event can exceed it before the check. No OS RSS/CPU hard cap.",
    "sale": "Setup uses a fresh identical passive bid book per sale. Construction "
            "timed separately. Integer ceil(depth * percent / 100); 10%, 100%, 200%. "
            "Throughput counts one sale, not its setup events. price_levels_visited "
            "counts distinct executed fill prices after the primary timer stops; "
            "it is reported for single-sale timing and diagnostics only.",
    "queue_concentration": "Same order count, requested 4 versus 1000 levels. Actual "
                           "occupied levels are min(order_count, requested_levels).",
    "churn": "An old active head remains while same-price orders are added/cancelled; "
             "capture retained storage and memory before final head cancellation and "
             "after it. Stream size is 2 * requested_count + 2.",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    """Replace a checkpoint atomically, outside all measurement clocks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def throughput(count, seconds):
    return count / seconds if seconds > 0 else None


def requested_quantity(depth, percent):
    """Round a positive fractional sale upward using integers only."""
    if type(depth) is not int or depth <= 0 or type(percent) is not int or percent not in (10, 100, 200):
        raise ValueError("Expected positive integer depth and percentage 10, 100 or 200")
    return (depth * percent + 99) // 100


def latency_statistics(samples):
    if not samples:
        raise ValueError("At least one latency sample is required")
    ordered = sorted(samples)
    return {
        "latency_median_seconds": statistics.median(ordered),
        "latency_p95_seconds": ordered[(95 * len(ordered) + 99) // 100 - 1],
        "latency_p99_seconds": ordered[(99 * len(ordered) + 99) // 100 - 1],
        "latency_sample_count": len(ordered),
    }


def controlled_orders(count, seed, levels):
    """Deterministic passive bid book with exactly min(count, levels) prices."""
    rng = random.Random(seed)
    for index in range(count):
        seq = index + 1
        yield {
            "seq": seq, "event_id": f"controlled-{seq}", "type": "LIMIT",
            "order_id": f"bid-{seq}", "side": "BUY",
            "price_ticks": 6_000_000 - index % levels,
            "qty_units": rng.randint(1, 100) * 1_000_000,
        }


def churn_orders(count):
    """Keep an old active head while cancelling younger same-price orders."""
    yield {"seq": 1, "event_id": "anchor", "type": "LIMIT", "order_id": "anchor",
           "side": "BUY", "price_ticks": 6_000_000, "qty_units": 100_000_000}
    for index in range(count):
        seq = 2 * index + 2
        order_id = f"churn-{index}"
        yield {"seq": seq, "event_id": f"add-{seq}", "type": "LIMIT",
               "order_id": order_id, "side": "BUY",
               "price_ticks": 6_000_000, "qty_units": 100_000_000}
        yield {"seq": seq + 1, "event_id": f"cancel-{seq}", "type": "CANCEL",
               "target_order_id": order_id}
    yield {"seq": 2 * count + 2, "event_id": "cancel-anchor",
           "type": "CANCEL", "target_order_id": "anchor"}


def case_matrix(args):
    cases = []
    for count in args.counts:
        for seed in args.seeds:
            for experiment in args.experiments:
                if experiment == "replay":
                    variants = [(scenario, args.levels, None) for scenario in args.scenarios]
                elif experiment == "market-sell":
                    variants = [("controlled_bids", args.levels, p) for p in (10, 100, 200)]
                elif experiment == "queue-concentration":
                    variants = [("controlled_bids", levels, 100) for levels in (4, 1000)]
                else:
                    variants = [("anchored_cancel_churn", 1, None)]
                for scenario, levels, percent in variants:
                    setup_count = count if percent is not None else 0
                    file_count = 2 * count + 2 if experiment == "cancel-churn" else count
                    cases.append({
                        "case_id": f"{experiment}_{scenario}_n{count}_s{seed}_l{levels}"
                                   + (f"_p{percent}" if percent is not None else ""),
                        "experiment": experiment, "scenario": scenario, "seed": seed,
                        "requested_count": count, "levels": levels, "sale_percent": percent,
                        "construction_event_count": setup_count, "source_event_count": file_count,
                        "event_count": file_count + (1 if percent is not None else 0),
                        "actual_controlled_price_levels": min(count, levels)
                        if percent is not None else None,
                    })
    return cases


def source_settings(case):
    return {key: case[key] for key in
            ("scenario", "source_event_count", "seed", "levels")}


def metadata_matches(meta, case):
    return (meta.get("scenario") == case["scenario"]
            and meta.get("events") == case["source_event_count"]
            and meta.get("seed") == case["seed"]
            and meta.get("levels") == case["levels"])


def ensure_workload(case, data_dir):
    """Reuse verified fixtures; never overwrite supplied or mismatched files."""
    data_dir = Path(data_dir)
    settings = source_settings(case)
    conventional = data_dir / f'{case["scenario"]}_{case["source_event_count"]}.jsonl.gz'
    key = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]
    target = data_dir / "benchmark" / f'{case["scenario"]}_{key}.jsonl.gz'
    for candidate in (conventional, target):
        sidecar = candidate.with_suffix(candidate.suffix + ".metadata.json")
        if candidate.exists():
            if not sidecar.is_file():
                raise ValueError(f"Existing workload has no metadata: {candidate}")
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            if metadata_matches(meta, case):
                if meta.get("sha256") != sha256(candidate):
                    raise ValueError(f"Workload checksum mismatch: {candidate}")
                return dict(path=str(candidate.resolve()), sha256=meta["sha256"],
                            metadata=meta, reused=True)
            if candidate == target:
                raise ValueError(f"Refusing to overwrite mismatched workload: {candidate}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if case["experiment"] == "replay":
        rows = generate_orders.events(case["scenario"], case["source_event_count"],
                                      case["seed"], case["levels"])
        generator = "generate_orders.events / random.Random"
    elif case["experiment"] == "cancel-churn":
        rows = churn_orders(case["requested_count"])
        generator = "benchmark.churn_orders / deterministic"
    else:
        rows = controlled_orders(case["requested_count"], case["seed"], case["levels"])
        generator = "benchmark.controlled_orders / random.Random"
    generate_orders.write_stream(target, rows)
    meta = dict(synthetic=True, calibrated_to_exchange_data=False,
                scenario=case["scenario"], events=case["source_event_count"],
                seed=case["seed"], levels=case["levels"], generator=generator,
                python=platform.python_version(), price_tick_usd="0.01",
                quantity_unit_btc="0.00000001", compressed_bytes=target.stat().st_size,
                sha256=sha256(target), generator_source_sha256=sha256(ROOT / "generate_orders.py"),
                benchmark_source_sha256=sha256(__file__))
    write_json(target.with_suffix(target.suffix + ".metadata.json"), meta)
    return dict(path=str(target.resolve()), sha256=meta["sha256"], metadata=meta, reused=False)


def load_events(path, payload_limit, expected_count):
    """Return preloaded events plus independent I/O phase clocks."""
    start = time.perf_counter()
    with Path(path).open("rb") as stream:
        raw = stream.read(payload_limit + 1)
    read_seconds = time.perf_counter() - start
    if len(raw) > payload_limit:
        raise ValueError("Compressed/file payload limit exceeded")
    decompress_seconds = None
    if str(path).endswith(".gz"):
        start = time.perf_counter()
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as stream:
            decoded = stream.read(payload_limit + 1)
        decompress_seconds = time.perf_counter() - start
    else:
        decoded = raw
    if len(decoded) > payload_limit:
        raise ValueError("Decompressed payload limit exceeded")
    start = time.perf_counter()
    events = [json.loads(line) for line in decoded.decode("utf-8").splitlines() if line.strip()]
    parse_seconds = time.perf_counter() - start
    # Validation is deliberately outside all I/O and engine measurement clocks.
    if len(events) != expected_count:
        raise ValueError(f"Expected {expected_count} events, got {len(events)}")
    previous = 0
    event_ids = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Workload events must be JSON objects")
        seq = event.get("seq")
        if type(seq) is not int or seq <= previous:
            raise ValueError("Workload sequences must be increasing positive built-in integers")
        previous = seq
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip() or event_id in event_ids:
            raise ValueError("Workload event_id values must be unique nonblank strings")
        event_ids.add(event_id)
        for field in ("price_ticks", "qty_units"):
            if field in event and (type(event[field]) is not int or event[field] <= 0):
                raise ValueError(f"Workload {field} must be a positive built-in integer")
    return events, dict(read_seconds=read_seconds, decompress_seconds=decompress_seconds,
                        parse_seconds=parse_seconds,
                        io_total_seconds=read_seconds + (decompress_seconds or 0) + parse_seconds,
                        compressed_bytes=len(raw), decoded_bytes=len(decoded))


def split_task(case, events):
    if case["sale_percent"] is None:
        return [], events, None
    quantity = requested_quantity(sum(e["qty_units"] for e in events), case["sale_percent"])
    sale = {"seq": len(events) + 1, "event_id": "measured-sale", "type": "MARKET_SELL",
            "order_id": "measured-sale", "qty_units": quantity}
    return events, [sale], quantity


def base_row(job, repetition):
    case = job["case"]
    row = {key: None for key in METRICS}
    row.update({key: case.get(key) for key in (
        "case_id", "experiment", "scenario", "seed", "event_count", "requested_count",
        "source_event_count", "construction_event_count", "levels", "sale_percent",
        "actual_controlled_price_levels")})
    row.update(version=job["version"], phase=job["phase"], repetition=repetition,
               statistic="raw", status="complete", error=None,
               workload_path=case["source"]["path"], workload_sha256=case["source"]["sha256"],
               requested_sale_qty_units=None, result_digest=None, snapshot_digest=None,
               latency_samples_path=None)
    return row


def summarize(rows, expected):
    summary = dict(rows[0])
    summary.update(statistic="median", repetition=None,
                   completed_repetitions=sum(r["status"] == "complete" for r in rows),
                   expected_repetitions=expected)
    complete = len(rows) == expected and all(r["status"] == "complete" for r in rows)
    summary["status"] = "complete" if complete else "incomplete"
    summary["error"] = next((r["error"] for r in rows if r["error"]), None)
    for field in METRICS:
        values = [r[field] for r in rows if r[field] is not None]
        summary[field] = statistics.median(values) if complete and len(values) == expected else None
    return summary


def engine_class(version):
    from order_book import BaselineOrderBook, RevisedOrderBook
    return {"baseline": BaselineOrderBook, "revised": RevisedOrderBook}[version]


def replay(book, events):
    """Primary stream loop: no saved history, counters or canonical inspection."""
    for event in events:
        book.process_event(event)


def timed_once(factory, setup, task, single_sale):
    gc.collect()
    start = time.perf_counter()
    book = factory()
    initialization = time.perf_counter() - start
    construction = None
    if setup:
        start = time.perf_counter()
        replay(book, setup)
        construction = time.perf_counter() - start
    start = time.perf_counter()
    if single_sale:
        result = book.process_event(task[0])
    else:
        replay(book, task)
    elapsed = time.perf_counter() - start
    metrics = dict(initialization_seconds=initialization, construction_seconds=construction,
                   replay_seconds=elapsed,
                   total_compute_seconds=initialization + (construction or 0) + elapsed,
                   processed_events=len(task),
                   throughput_events_per_second=throughput(len(task), elapsed))
    if single_sale:
        metrics.update(fill_count=len(result["fills"]),
                       price_levels_visited=len({fill["price_ticks"] for fill in result["fills"]}),
                       unfilled_qty_units=result["unfilled_qty_units"])
    # Destruction is outside all timing, and cannot leak into the next constructor.
    del book
    return metrics


def storage_counts(book, version):
    if version == "baseline":
        active = len(book._orders)
        prices = len({(o["side"], o["price_ticks"]) for o in book._orders})
        retained, heaps = active, None
    else:
        active = len(book.orders_by_id)
        prices = len(book.bids_by_price) + len(book.asks_by_price)
        retained = sum(map(len, book.bids_by_price.values())) + sum(map(len, book.asks_by_price.values()))
        heaps = len(book.bid_price_heap) + len(book.ask_price_heap)
    return dict(active_orders=active, occupied_prices=prices,
                retained_queue_entries=retained, inactive_queue_entries=retained - active,
                heap_entries=heaps)


def diagnostics_once(factory, version, case, setup, task):
    book = factory()
    peaks = {key: 0 if value is not None else None
             for key, value in storage_counts(book, version).items()}
    digest = hashlib.sha256()
    fills = residual = cancelled = rejected = 0
    price_levels_visited = None
    extra = {}
    for index, event in enumerate(setup + task):
        result = book.process_event(event)
        digest.update((json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode())
        if index >= len(setup):
            fills += len(result.get("fills", []))
            if case.get("sale_percent") is not None:
                price_levels_visited = len({fill["price_ticks"] for fill in result["fills"]})
            residual += result.get("unfilled_qty_units", 0)
            cancelled += result.get("cancelled_qty_units", 0)
            rejected += result["status"] == "rejected"
        counts = storage_counts(book, version)
        for key, value in counts.items():
            if value is not None:
                peaks[key] = max(peaks[key], value)
        if case["experiment"] == "cancel-churn" and index == len(task) - 2:
            extra = dict(retained_queue_entries_before_final_cancel=counts["retained_queue_entries"],
                         inactive_entries_before_final_cancel=counts["inactive_queue_entries"],
                         active_orders_before_final_cancel=counts["active_orders"],
                         heap_entries_before_final_cancel=counts["heap_entries"])
    snapshot = book.inspect_book()
    metrics = {key + "_peak": value for key, value in peaks.items()}
    metrics.update({key + "_final": value for key, value in storage_counts(book, version).items()})
    metrics.update(fill_count=fills, price_levels_visited=price_levels_visited,
                   unfilled_qty_units=residual, cancelled_qty_units=cancelled,
                   rejected_event_count=rejected, processed_events=len(task),
                   result_digest=digest.hexdigest(),
                   snapshot_digest=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
                   **extra)
    return metrics


def warm_up(factory, setup, task):
    book = factory()
    replay(book, setup)
    replay(book, task)
    del book
    gc.collect()


def memory_once(factory, setup, task, case, allocation_limit):
    gc.collect()
    tracemalloc.start()
    try:
        book = factory()
        for event in setup:
            book.process_event(event)
            if tracemalloc.get_traced_memory()[1] > allocation_limit:
                raise MemoryError("Traced allocation limit exceeded during construction")
        gc.collect()
        construction = tracemalloc.get_traced_memory()[0]
        before_final = None
        for index, event in enumerate(task):
            book.process_event(event)
            if tracemalloc.get_traced_memory()[1] > allocation_limit:
                raise MemoryError("Traced allocation limit exceeded during replay")
            if case["experiment"] == "cancel-churn" and index == len(task) - 2:
                gc.collect()
                before_final = tracemalloc.get_traced_memory()[0]
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        metrics = dict(memory_peak_bytes=peak, memory_current_bytes=current,
                       memory_after_construction_bytes=construction,
                       memory_before_final_cancel_bytes=before_final,
                       memory_after_cancellation_bytes=current
                       if case["experiment"] == "cancel-churn" else None,
                       processed_events=len(task))
        del book
        return metrics
    finally:
        tracemalloc.stop()


def worker(job):
    """One isolated case/version/phase; checkpoint completed repetitions only."""
    checkpoint = Path(job["checkpoint"])
    rows = []
    try:
        case = job["case"]
        source = case["source"]
        if sha256(source["path"]) != source["sha256"]:
            raise ValueError("Workload changed after campaign preparation")
        events, _ = load_events(source["path"], job["payload_limit"], case["source_event_count"])
        setup, task, quantity = split_task(case, events)
        phase = job["phase"]
        if phase != "io":
            factory = engine_class(job["version"])
            warm_up(factory, setup, task)
        expected = REPETITIONS if phase in ("io", "timing", "memory") else 1
        for repetition in range(1, expected + 1):
            row = base_row(job, repetition)
            row["requested_sale_qty_units"] = quantity
            if phase == "io":
                gc.collect()
                loaded, metrics = load_events(source["path"], job["payload_limit"],
                                              case["source_event_count"])
                del loaded
                row.update(metrics)
            elif phase == "timing":
                row.update(timed_once(factory, setup, task, quantity is not None))
            elif phase == "memory":
                row.update(memory_once(factory, setup, task, case, job["allocation_limit"]))
            elif phase == "diagnostics":
                row.update(diagnostics_once(factory, job["version"], case, setup, task))
            else:
                samples = []
                sample_repetitions = REPETITIONS if quantity is not None else 1
                for sample_repetition in range(1, sample_repetitions + 1):
                    gc.collect()
                    book = factory()
                    replay(book, setup)
                    for event in task:
                        start = time.perf_counter()
                        if quantity is None:
                            book.process_event(event)
                        else:
                            result = book.process_event(event)
                        elapsed = time.perf_counter() - start
                        if quantity is not None:
                            del result
                        samples.append(dict(event_id=event["event_id"], seq=event["seq"],
                                            repetition=sample_repetition, seconds=elapsed))
                    del book
                samples_path = checkpoint.with_suffix(".latencies.json")
                write_json(samples_path, dict(case_id=case["case_id"], version=job["version"],
                                              phase="latency", samples=samples))
                row.update(latency_statistics([sample["seconds"] for sample in samples]))
                row.update(latency_samples_path=str(samples_path), processed_events=len(samples))
            rows.append(row)
            write_json(checkpoint, dict(status="complete" if len(rows) == expected else "running",
                                        rows=rows, error=None))
        return 0
    except Exception as error:
        write_json(checkpoint, dict(status="error", rows=rows,
                                    error=f"{type(error).__name__}: {error}"))
        return 2


def environment_metadata():
    def git(*arguments):
        try:
            result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True,
                                    text=True, check=True, timeout=10)
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    sources = ("benchmark.py", "generate_orders.py", "order_book.py", "dispatcher.py",
               "test_order_book.py", "test_price_heaps.py", "test_lazy_cancellation.py",
               "test_benchmark.py")
    status = git("status", "--porcelain")
    return dict(
        python=sys.version, python_executable=sys.executable,
        implementation=platform.python_implementation(),
        dependencies={"third_party_required": [], "stdlib": platform.python_version(),
                      "zlib_build": zlib.ZLIB_VERSION, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION},
        machine=dict(os=platform.platform(), system=platform.system(),
                     release=platform.release(), machine=platform.machine(),
                     processor=platform.processor(), logical_cpus=os.cpu_count()),
        clock=dict(name="perf_counter", resolution_seconds=time.get_clock_info("perf_counter").resolution),
        git_head=git("rev-parse", "HEAD"), git_dirty=bool(status) if status is not None else None,
        git_status=status,
        source_sha256={name: sha256(ROOT / name) for name in sources if (ROOT / name).is_file()},
        worker_environment={"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"},
        garbage_collection="enabled; explicit collection before each fresh-book repetition",
    )


def completed_rows(job, status, error):
    """Recover complete repetitions, then explicitly label every missing one."""
    expected = REPETITIONS if job["phase"] in ("io", "timing", "memory") else 1
    checkpoint = Path(job["checkpoint"])
    saved = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    rows = saved.get("rows", [])
    error = saved.get("error") or error
    if saved.get("status") == "error":
        status = "error"
    if len(rows) < expected:
        for repetition in range(len(rows) + 1, expected + 1):
            row = base_row(job, repetition)
            row.update(status=status if status != "complete" else "error",
                       error=error or "Worker did not finish this repetition")
            rows.append(row)
    return rows, summarize(rows, expected)


def run_job(job, seconds):
    path = Path(job["checkpoint"]).with_suffix(".job.json")
    write_json(path, job)
    if seconds <= 0:
        return completed_rows(job, "not_run", "Campaign wall deadline reached")
    environment = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                                 "_worker", str(path)], cwd=ROOT, env=environment,
                                capture_output=True, text=True, timeout=seconds)
        status = "complete" if result.returncode == 0 else "error"
        error = result.stderr.strip() or (None if result.returncode == 0
                                         else f"Worker exit code {result.returncode}")
    except subprocess.TimeoutExpired:
        status, error = "stopped", f"Worker wall limit reached ({seconds:.3f} seconds)"
    return completed_rows(job, status, error)


def write_jsonl(path, records):
    with Path(path).open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, allow_nan=False) + "\n")


def validate_diagnostics(summaries):
    pairs = {}
    for row in summaries:
        if row["phase"] == "diagnostics" and row["status"] == "complete":
            pairs.setdefault(row["case_id"], {})[row["version"]] = row
    checks = []
    for case_id, versions in pairs.items():
        if set(versions) == set(VERSIONS):
            left, right = (versions[v] for v in VERSIONS)
            equal = all(left[field] == right[field] for field in
                        ("result_digest", "snapshot_digest", "fill_count", "price_levels_visited",
                         "unfilled_qty_units", "cancelled_qty_units", "rejected_event_count"))
            checks.append(dict(case_id=case_id, status="passed" if equal else "failed"))
    return checks


def campaign(args, cases):
    output = args.out or ROOT / "results" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite a nonempty results directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    # All generation and provenance checks finish before the first measurement worker.
    for case in cases:
        case["source"] = ensure_workload(case, args.data_dir)
    manifest = dict(schema_version=1, started_utc=datetime.now(timezone.utc).isoformat(),
                    status="running", environment=environment_metadata(), boundaries=BOUNDARIES,
                    command=sys.argv, versions=args.versions, phases=PHASES,
                    repetitions=REPETITIONS, workloads=cases,
                    limits=dict(worker_wall_seconds=args.worker_seconds,
                                measurement_campaign_wall_seconds=args.campaign_seconds,
                                payload_bytes=args.payload_mib * 1024 ** 2,
                                traced_allocation_bytes=args.traced_mib * 1024 ** 2,
                                os_rss_hard_limit=None,
                                preparation="Generation precedes measurement deadline; no preparation timeout"),
                    run_kind=args.label)
    write_json(output / "manifest.json", manifest)
    rows, summaries = [], []
    deadline = time.perf_counter() + args.campaign_seconds
    jobs = []
    for case in cases:
        # Alternate version order across cases to reduce a fixed first-run bias.
        versions = args.versions if len(jobs) % 2 == 0 else list(reversed(args.versions))
        jobs.append((case, None, "io"))
        for phase in PHASES[1:]:
            for version in versions:
                jobs.append((case, version, phase))
    for index, (case, version, phase) in enumerate(jobs, 1):
        checkpoint = output / "workers" / f"{index:04d}_{case['case_id']}_{version or 'shared'}_{phase}.json"
        job = dict(case=case, version=version, phase=phase, checkpoint=str(checkpoint),
                   payload_limit=args.payload_mib * 1024 ** 2,
                   allocation_limit=args.traced_mib * 1024 ** 2)
        remaining = min(args.worker_seconds, deadline - time.perf_counter())
        raw, summary = run_job(job, remaining)
        rows.extend(raw)
        summaries.append(summary)
        write_jsonl(output / "raw.jsonl", rows)
        write_jsonl(output / "summaries.jsonl", summaries)
        print(f"[{index}/{len(jobs)}] {case['case_id']} {version or 'shared'} "
              f"{phase}: {summary['status']}", flush=True)
    checks = validate_diagnostics(summaries)
    manifest.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                    status="complete" if all(s["status"] == "complete" for s in summaries)
                    and all(c["status"] == "passed" for c in checks) else "incomplete",
                    raw_rows=len(rows), summary_rows=len(summaries),
                    diagnostic_comparisons=checks,
                    completed_jobs=sum(s["status"] == "complete" for s in summaries))
    write_json(output / "manifest.json", manifest)
    print(json.dumps(dict(results=str(output), status=manifest["status"],
                          raw_rows=len(rows), summary_rows=len(summaries))))
    return 0 if manifest["status"] == "complete" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    worker_parser = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("job", type=Path)
    for command in ("plan", "prepare", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--counts", nargs="+", type=int, default=[1000, 10000, 100000])
        sub.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
        sub.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
        sub.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
        sub.add_argument("--experiments", nargs="+", choices=EXPERIMENTS, default=["replay"])
        sub.add_argument("--levels", type=int, default=1000)
        sub.add_argument("--data-dir", type=Path, default=ROOT / "data")
        sub.add_argument("--out", type=Path, help="Plan JSON file, or new run results directory")
        if command == "run":
            sub.add_argument("--worker-seconds", type=float, default=60)
            sub.add_argument("--campaign-seconds", type=float, default=1800)
            sub.add_argument("--payload-mib", type=int, default=128)
            sub.add_argument("--traced-mib", type=int, default=512)
            sub.add_argument("--label", default="benchmark")
    args = parser.parse_args(argv)
    if args.command == "_worker":
        return worker(json.loads(args.job.read_text(encoding="utf-8")))
    if any(count <= 0 for count in args.counts) or not 1 <= args.levels < 6_000_000:
        parser.error("Counts must be positive; levels must be between 1 and 5999999")
    for name in ("counts", "seeds", "scenarios", "versions", "experiments"):
        if len(set(getattr(args, name))) != len(getattr(args, name)):
            parser.error(f"--{name} must not contain duplicates")
    if args.command == "run" and any(
        getattr(args, name) <= 0 for name in ("worker_seconds", "campaign_seconds", "payload_mib", "traced_mib")
    ):
        parser.error("Execution limits must be positive")
    cases = case_matrix(args)
    try:
        if args.command == "run":
            return campaign(args, cases)
        if args.command == "prepare":
            for case in cases:
                case["source"] = ensure_workload(case, args.data_dir)
        plan = dict(status="planned" if args.command == "plan" else "prepared",
                    measurement_executed=False, cases=cases, versions=args.versions,
                    repetitions=REPETITIONS, boundaries=BOUNDARIES)
        if args.out:
            if args.out.exists():
                raise ValueError(f"Refusing to overwrite existing plan: {args.out}")
            write_json(args.out, plan)
        print(json.dumps(dict(status=plan["status"], cases=len(cases),
                              version_cases=len(cases) * len(args.versions),
                              output=str(args.out) if args.out else None)))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

