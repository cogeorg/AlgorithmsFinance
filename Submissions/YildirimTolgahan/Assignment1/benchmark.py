"""Benchmark both order-book versions and save raw results. See README.md for definitions.

    python benchmark.py                 full run (about 1.5 to 2 hours; resumable with --resume)
    python benchmark.py --quick --output results/smoke

Every measurement cell runs in a fresh child process. Inside a cell the passes
are strictly separated: timed replays first, then per-event latency
instrumentation, then operation counters (small cells), then tracemalloc.
Event files are generated before anything is timed.
"""
import argparse
from array import array
import csv
from datetime import datetime, timezone
import gc
import hashlib
from itertools import islice
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import traceback
import tracemalloc

from book_a import OrderBookA
from book_b import OrderBookB
from events import format_usd, gross_value, iter_events, read_events
from instrumented import COUNTING
import workloads

HERE = Path(__file__).resolve().parent
BOOKS = {"A": OrderBookA, "B": OrderBookB}
VERSION_NAMES = {"A": "A: unsorted lists, full scans", "B": "B: price levels, heaps, order index"}
SOURCE_FILES = ("events.py", "book_a.py", "book_b.py", "instrumented.py", "workloads.py", "generate_orders.py",
                "benchmark.py", "replay.py")
SCHEMA_VERSION = 1
PRELOAD_MAX = 100_000          # larger streams are parsed block by block instead of preloaded
WARMUP_EVENTS = 10_000
CHECKPOINTS = 20               # cumulative readings at every 5% of a stream
BLOCK_MAX = 1_000              # events between two clock readings / limit checks
COUNTER_MAX_EVENTS = 10_000    # operation counters only for small diagnostic replays
HIST_PER_DECADE = 5
HIST_MIN_LOG10_NS, HIST_MAX_LOG10_NS = 2, 11      # 100 ns .. 100 s
EVENT_TYPES = ("LIMIT", "MARKET_SELL", "CANCEL")
IDLE_TIMEOUT = 1800            # seconds without any message before a child is considered hung


# ------------------------------------------------------------- statistics
def percentile(sorted_values, p):
    """Nearest-rank percentile: the smallest value with at least p% of the sample at or below it."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def latency_summary(values_ns):
    ordered = sorted(values_ns)
    if not ordered:
        return {"count": 0}
    return {"count": len(ordered), "p50_ns": percentile(ordered, 50), "p95_ns": percentile(ordered, 95),
            "p99_ns": percentile(ordered, 99), "max_ns": ordered[-1], "mean_ns": sum(ordered) / len(ordered)}


def histogram(values_ns):
    """Counts in logarithmic bins, HIST_PER_DECADE per decade from 100 ns; out-of-range values are clamped."""
    bins = [0] * ((HIST_MAX_LOG10_NS - HIST_MIN_LOG10_NS) * HIST_PER_DECADE)
    for value in values_ns:
        index = int((math.log10(value) - HIST_MIN_LOG10_NS) * HIST_PER_DECADE) if value > 0 else 0
        bins[min(len(bins) - 1, max(0, index))] += 1
    return bins


def block_bounds(count):
    """(end index, is 5% checkpoint) pairs; blocks never exceed BLOCK_MAX events."""
    bounds, done = [], 0
    for i in range(1, CHECKPOINTS + 1):
        mark = count * i // CHECKPOINTS
        while done < mark:
            done = min(mark, done + BLOCK_MAX)
            bounds.append((done, done == mark))
    return [b for b in bounds if b[0] > 0]


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------- child: read/parse
def parse_worker(conn, spec):
    """gzip reading plus JSON parsing of a whole file, without retaining the events."""
    path = HERE / spec["file"]
    for _ in iter_events(path):          # warm-up: file cache and code paths
        pass
    for repeat in range(1, spec["repeats"] + 1):
        gc.collect()
        started = time.perf_counter()
        count = 0
        for _ in iter_events(path):
            count += 1
        conn.send(("repeat", {"repeat": repeat, "elapsed_seconds": time.perf_counter() - started, "events": count}))
    conn.send(("done", {}))


# ------------------------------------------------------------ child: replay
def replay_worker(conn, spec):
    cls = BOOKS[spec["version"]]
    path, count = HERE / spec["file"], spec["events"]
    preloaded = read_events(path) if count <= PRELOAD_MAX else None

    def source():
        return iter(preloaded) if preloaded is not None else iter_events(path)

    bounds = block_bounds(count)
    conn.send(("info", {"input_mode": "preloaded" if preloaded is not None else "streamed"}))

    # Warm-up on a prefix, not timed.
    book = cls()
    for event in islice(source(), WARMUP_EVENTS):
        book.ProcessEvent(event)

    # Pass 1: timed replays. Only the loop over a block of already parsed events is inside the clock.
    stopped = False
    for repeat in range(1, spec["repeats"] + 1):
        del book
        gc.collect()
        book = cls()
        process = book.ProcessEvent
        stream, done, elapsed, marks, status = source(), 0, 0.0, [], "ok"
        for end, is_mark in bounds:
            block = list(islice(stream, end - done))
            started = time.perf_counter()
            for event in block:
                process(event)
            elapsed += time.perf_counter() - started
            done = end
            if is_mark:
                marks.append(elapsed)
            if elapsed > spec["replay_limit_seconds"] and done < count:
                status = "stopped"
                break
        conn.send(("repeat", {"repeat": repeat, "status": status, "elapsed_seconds": elapsed,
                              "events_completed": done, "checkpoint_seconds": marks}))
        if status == "stopped":
            stopped = True
            break
    if stopped:
        conn.send(("done", {}))
        return

    # Pass 2: per-event latency, result digest and book-size peaks.
    del book
    gc.collect()
    book = cls()
    process, clock = book.ProcessEvent, time.perf_counter_ns
    track_levels = spec["version"] == "B"                 # O(1) there; an O(B) scan in version A
    latencies, kinds = array("q"), bytearray()
    results_digest = hashlib.sha256()
    statuses, fills_total, filled_qty, value = {}, 0, 0, 0
    peak_active = peak_levels = 0
    type_code = {name: i for i, name in enumerate(EVENT_TYPES)}
    for event in source():
        started = clock()
        result = process(event)
        latencies.append(clock() - started)
        kinds.append(type_code.get(event.get("type"), 3))
        results_digest.update(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
        fills = result.get("fills")
        if fills:
            fills_total += len(fills)
            filled_qty += sum(fill["qty_units"] for fill in fills)
            value += gross_value(fills)
        active = book.active_orders()
        if active > peak_active:
            peak_active = active
        if track_levels:
            levels = book.price_levels()
            if levels > peak_levels:
                peak_levels = levels
    by_type = {name: [] for name in EVENT_TYPES}
    for value_ns, code in zip(latencies, kinds):
        if code < 3:
            by_type[EVENT_TYPES[code]].append(value_ns)
    tenth = max(1, len(latencies) // 10)
    conn.send(("latency", {
        "overall": latency_summary(latencies),
        "by_type": {name: latency_summary(values) for name, values in by_type.items()},
        "histogram_by_type": {name: histogram(values) for name, values in by_type.items()},
        "deciles": [latency_summary(latencies[i * len(latencies) // 10:(i + 1) * len(latencies) // 10])
                    for i in range(10)],
        "first_10pct": latency_summary(latencies[:tenth]), "last_10pct": latency_summary(latencies[-tenth:]),
        "instrumented_seconds": sum(latencies) / 1e9}))
    conn.send(("outcome", {
        "results_sha256": results_digest.hexdigest(), "book_sha256": digest_json(book.InspectBook()),
        "statuses": dict(sorted(statuses.items())), "fill_count": fills_total, "filled_qty_units": filled_qty,
        "gross_value_tick_units": value, "gross_value_usd": format_usd(value),
        "peak_active_orders": peak_active, "peak_price_levels": peak_levels if track_levels else None,
        "final_active_orders": book.active_orders(), "final_price_levels": book.price_levels(),
        "final_storage": book.storage_stats()}))
    del latencies, kinds, by_type

    # Pass 3: operation counters on small streams.
    if count <= COUNTER_MAX_EVENTS:
        counting = COUNTING[spec["version"]]()
        for event in source():
            counting.ProcessEvent(event)
        conn.send(("counters", dict(sorted(counting.counters.items()))))
        del counting

    # Pass 4: tracemalloc. Preloaded input exists before tracing starts and is not counted;
    # a streamed input contributes at most one parsed block (BLOCK_MAX events) to the readings.
    del book
    gc.collect()
    tracemalloc.start()
    book = cls()
    process = book.ProcessEvent
    stream, done, result, checkpoints, status = source(), 0, None, [], "ok"
    for end, is_mark in bounds:
        for event in islice(stream, end - done):
            result = process(event)                      # the latest returned result stays alive
        done = end
        if is_mark:
            current, peak = tracemalloc.get_traced_memory()
            checkpoints.append({"events": done, "active_orders": book.active_orders(), "current_bytes": current})
            if peak > spec["memory_limit_bytes"]:
                status = "stopped"
                break
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    conn.send(("memory", {"status": status, "peak_bytes": peak, "final_current_bytes": current,
                          "events_completed": done, "final_active_orders": book.active_orders(),
                          "checkpoints": checkpoints, "input_inside_trace": preloaded is None}))
    conn.send(("done", {}))


# -------------------------------------------------------- child: fixed book
def fixed_book_worker(conn, spec):
    """Fresh one-sided bid book per trial, then one market sell of a share of its quantity."""
    cls = BOOKS[spec["version"]]
    events = list(workloads.bid_book_events(spec["book_orders"], spec["levels"], spec["seed"]))
    total = sum(event["qty_units"] for event in events)
    requested = workloads.sale_quantity(total, spec["sale_pct"])
    expected_fills, expected_unfilled = workloads.plan_market_sell(events, requested, "sale")
    conn.send(("info", {"available_bid_qty_units": total, "requested_qty_units": requested,
                        "expected_fill_count": len(expected_fills)}))

    def build(book_class):
        book = book_class()
        process = book.ProcessEvent
        started = time.perf_counter()
        for event in events:
            process(event)
        return book, time.perf_counter() - started

    small = list(workloads.bid_book_events(min(spec["book_orders"], 2_000), spec["levels"], spec["seed"]))
    warm = cls()
    for event in small:
        warm.ProcessEvent(event)
    warm.FillMarketSell("sale", workloads.sale_quantity(sum(e["qty_units"] for e in small), spec["sale_pct"]))
    del warm

    result = book = None
    for repeat in range(1, spec["repeats"] + 1):
        del result, book
        gc.collect()
        book, construction = build(cls)
        conn.send(("built", {"repeat": repeat, "construction_seconds": construction,
                             "next_within": spec["sale_limit_seconds"]}))
        sell = book.FillMarketSell
        started = time.perf_counter()
        result = sell("sale", requested)                 # matching, state updates and fill list
        elapsed = time.perf_counter() - started
        conn.send(("sold", {"repeat": repeat, "sell_seconds": elapsed}))

    fills = result["fills"]
    conn.send(("outcome", {
        "status": result["status"], "fill_count": len(fills),
        "makers_touched": len({fill["maker_id"] for fill in fills}),
        "price_levels_visited": len({fill["price_ticks"] for fill in fills}),
        "unfilled_qty_units": result["unfilled_qty_units"],
        "filled_qty_units": sum(fill["qty_units"] for fill in fills),
        "gross_value_tick_units": gross_value(fills), "gross_value_usd": format_usd(gross_value(fills)),
        "fills_sha256": digest_json(fills), "book_sha256": digest_json(book.InspectBook()),
        "remaining_orders": book.active_orders(),
        "matches_sorted_fill_plan": fills == expected_fills and result["unfilled_qty_units"] == expected_unfilled,
        "peak_active_orders": spec["book_orders"],
        "peak_price_levels": len({event["price_ticks"] for event in events})}))
    del result, book, fills

    counting, _ = build(COUNTING[spec["version"]])
    counting.counters.clear()                            # count the sale only
    conn.send(("counting", {"next_within": 3 * spec["sale_limit_seconds"]}))
    counting.FillMarketSell("sale", requested)
    conn.send(("counters", dict(sorted(counting.counters.items()))))
    del counting

    gc.collect()
    book, _ = build(cls)
    conn.send(("tracing", {"next_within": 3 * spec["sale_limit_seconds"]}))
    tracemalloc.start()
    result = book.FillMarketSell("sale", requested)
    current, peak = tracemalloc.get_traced_memory()      # the returned fill list is still alive
    tracemalloc.stop()
    conn.send(("memory", {"sell_peak_bytes": peak, "sell_current_bytes": current}))
    conn.send(("done", {}))


WORKERS = {"read_parse": parse_worker, "replay": replay_worker, "fixed_book": fixed_book_worker}


def child_main(conn, kind, spec):
    try:
        WORKERS[kind](conn, spec)
    except BaseException:
        conn.send(("error", traceback.format_exc()))
    finally:
        conn.close()


# ----------------------------------------------------------------- parent
class ListConnection:
    """In-process stand-in for a pipe end (used by tests and --in-process)."""

    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)

    def close(self):
        pass


def run_child(kind, spec, in_process=False):
    """Run one cell; return (messages, stop note). A child that exceeds a declared limit is terminated."""
    if in_process:
        conn = ListConnection()
        child_main(conn, kind, spec)
        return conn.messages, None
    parent, child = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=child_main, args=(child, kind, spec), daemon=True)
    process.start()
    child.close()
    messages, note, wait = [], None, IDLE_TIMEOUT
    while True:
        waited = time.perf_counter()
        try:
            ready = False
            while not ready and time.perf_counter() - waited < wait + 5:     # 5 s grace for scheduling
                ready = parent.poll(1.0)
                if not ready and not process.is_alive() and not parent.poll(0):
                    raise EOFError
            if not ready:
                note = {"reason": "time limit", "limit_seconds": wait,
                        "waited_seconds": time.perf_counter() - waited}
                break
            message = parent.recv()
        except (EOFError, OSError):
            note = {"reason": "child ended without finishing"}
            break
        messages.append(message)
        if message[0] in ("done", "error"):
            break
        wait = message[1].get("next_within", IDLE_TIMEOUT) if isinstance(message[1], dict) else IDLE_TIMEOUT
    if process.is_alive():
        process.terminate()
    process.join(30)
    parent.close()
    return messages, note


def first(messages, tag, default=None):
    return next((body for name, body in messages if name == tag), default)


def errors(messages):
    return [body for name, body in messages if name == "error"]


def collect_replay(spec, messages, note):
    repeats = [body for name, body in messages if name == "repeat"]
    row = {k: spec[k] for k in ("experiment", "version", "scenario", "seed", "events", "levels", "file")}
    row.update(input_mode=(first(messages, "info") or {}).get("input_mode"),
               replay_limit_seconds=spec["replay_limit_seconds"], repeats=repeats)
    failure = errors(messages)
    stopped = [r for r in repeats if r["status"] == "stopped"]
    complete = [r for r in repeats if r["status"] == "ok"]
    if failure or note:
        row.update(status="error", error=(failure or [json.dumps(note)])[0])
    elif stopped:
        row.update(status="stopped", stopped_after_seconds=stopped[0]["elapsed_seconds"],
                   events_completed=stopped[0]["events_completed"], stopped_in_repeat=stopped[0]["repeat"])
    else:
        row["status"] = "ok"
    if row["status"] == "ok" and len(complete) == spec["repeats"]:
        median = statistics.median(r["elapsed_seconds"] for r in complete)
        row.update(replay_seconds_median=median, throughput_events_per_second=spec["events"] / median,
                   checkpoint_seconds_median=[statistics.median(r["checkpoint_seconds"][i] for r in complete)
                                              for i in range(CHECKPOINTS)])
        boundary = workloads.build_boundary(spec["scenario"], spec["events"])
        if boundary is not None:
            index = boundary * CHECKPOINTS // spec["events"] - 1
            build = [r["checkpoint_seconds"][index] for r in complete]
            row.update(build_events=boundary, build_seconds_median=statistics.median(build),
                       tail_seconds_median=statistics.median(r["elapsed_seconds"] - b
                                                             for r, b in zip(complete, build)))
    for tag in ("latency", "outcome", "counters", "memory"):
        row[tag] = first(messages, tag)
    return row


def collect_fixed(spec, messages, note):
    built = {body["repeat"]: body for name, body in messages if name == "built"}
    sold = {body["repeat"]: body for name, body in messages if name == "sold"}
    row = {k: spec[k] for k in ("experiment", "version", "scenario", "seed", "book_orders", "levels", "sale_pct")}
    row.update(first(messages, "info") or {})
    row.update(events=spec["book_orders"] + 1, sale_limit_seconds=spec["sale_limit_seconds"],
               repeats=[{"repeat": r, "construction_seconds": built[r]["construction_seconds"],
                         "sell_seconds": sold.get(r, {}).get("sell_seconds")} for r in sorted(built)])
    failure = errors(messages)
    timed_out = len(sold) < spec["repeats"]
    if failure:
        row.update(status="error", error=failure[0])
    elif timed_out:
        row.update(status="stopped", stopped_in_repeat=len(sold) + 1, stopped_phase="sell",
                   stopped_after_seconds=(note or {}).get("waited_seconds"))
    else:
        row["status"] = "ok"
        row["sell_seconds_median"] = statistics.median(s["sell_seconds"] for s in sold.values())
    if built:
        row["construction_seconds_median"] = statistics.median(b["construction_seconds"] for b in built.values())
    for tag in ("outcome", "counters", "memory"):
        row[tag] = first(messages, tag)
    if not failure and not timed_out and note:
        row["later_pass_note"] = note                    # timing is complete; counters or tracing were cut
    return row


def collect_parse(spec, messages, note):
    repeats = [body for name, body in messages if name == "repeat"]
    row = {k: spec[k] for k in ("experiment", "scenario", "seed", "events", "levels", "file")}
    row.update(repeats=repeats, status="ok" if len(repeats) == spec["repeats"] and not errors(messages) else "error")
    if row["status"] == "ok":
        row["read_parse_seconds_median"] = statistics.median(r["elapsed_seconds"] for r in repeats)
    else:
        row["error"] = (errors(messages) or [json.dumps(note)])[0]
    return row


COLLECTORS = {"read_parse": collect_parse, "replay": collect_replay, "fixed_book": collect_fixed}


def cell_key(kind, spec):
    return "|".join(str(spec.get(k, "")) for k in ("experiment", "version", "scenario", "seed", "events",
                                                   "levels", "book_orders", "sale_pct")) + "|" + kind


# ------------------------------------------------------------------- plan
def build_plan(settings):
    """Datasets first (outside timing), then the ordered list of cells."""
    datasets, cells = [], []
    stream_cells = [(scenario, count, seed) for scenario in workloads.SCENARIOS
                    for count in settings["sizes"] for seed in settings["seeds"]]
    stream_cells += [(scenario, count, settings["seeds"][0]) for scenario in workloads.SCENARIOS
                     for count in settings["single_seed_sizes"]]
    order = random.Random(settings["order_seed"])
    for scenario, count, seed in sorted(stream_cells, key=lambda c: (c[1], c[0], c[2])):
        data = workloads.ensure_dataset(scenario, count, seed, settings["levels"])
        datasets.append(data)
        base = {"scenario": scenario, "seed": seed, "events": count, "levels": settings["levels"],
                "file": data["file"], "repeats": settings["repeats"]}
        cells.append(("read_parse", dict(base, experiment="read_parse")))
        versions = ["A", "B"]
        order.shuffle(versions)                           # which version runs first varies by cell
        for position, version in enumerate(versions, 1):
            cells.append(("replay", dict(base, experiment="replay", version=version, version_position=position,
                                         replay_limit_seconds=settings["replay_limit_seconds"],
                                         memory_limit_bytes=settings["memory_limit_bytes"])))
    books = [(n, settings["levels"], seed) for n in settings["sizes"] for seed in settings["seeds"]]
    books += [(n, settings["levels"], settings["seeds"][0]) for n in settings["fixed_single_seed_sizes"]]
    books += [(settings["concentration_orders"], levels, seed) for levels in settings["concentration_levels"]
              for seed in settings["concentration_seeds"]]
    for orders, levels, seed in sorted(set(books)):
        for pct in settings["sale_percents"]:
            versions = ["A", "B"]
            order.shuffle(versions)
            for position, version in enumerate(versions, 1):
                cells.append(("fixed_book", {
                    "experiment": "fixed_book", "scenario": "bid_book", "version": version, "seed": seed,
                    "book_orders": orders, "levels": levels, "sale_pct": pct, "repeats": settings["repeats"],
                    "version_position": position, "sale_limit_seconds": settings["sale_limit_seconds"]}))
    return datasets, cells


def git_output(*args):
    try:
        result = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def source_hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def worked_example_check():
    expected = json.loads((HERE / "data" / "worked_expected.json").read_text(encoding="utf-8"))
    events = read_events(HERE / "data" / "worked_example.jsonl")
    rows = []
    for name, cls in BOOKS.items():
        book = cls()
        results = [book.ProcessEvent(event) for event in events]
        value = gross_value(results[-1]["fills"])
        rows.append({"version": name, "gross_proceeds_usd": format_usd(value),
                     "matches_expected": (results[-1] == expected["market_sell_result"]
                                          and book.InspectBook() == expected["remaining_orders"]
                                          and value == expected["gross_proceeds_tick_units"])})
    return rows


def on_mains_power():
    """True on mains, False on battery, None if unknown (only Windows is queried)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        class PowerStatus(ctypes.Structure):
            _fields_ = [("ac_line", ctypes.c_ubyte), ("battery_flag", ctypes.c_ubyte),
                        ("battery_percent", ctypes.c_ubyte), ("system_status", ctypes.c_ubyte),
                        ("lifetime", ctypes.c_ulong), ("full_lifetime", ctypes.c_ulong)]
        status = PowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None
        return {0: False, 1: True}.get(status.ac_line)
    except Exception:
        return None


def keep_awake(active):
    """Ask Windows not to suspend while measuring (a suspended child looks like a run over its
    limit). Affects only this process and ends with it; no system setting is changed."""
    if sys.platform == "win32":
        try:
            import ctypes
            continuous, system_required = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(continuous | (system_required if active else 0))
        except Exception:
            pass


def metadata(settings):
    clock = time.get_clock_info("perf_counter")
    return {
        "mains_power_at_start": on_mains_power(),
        "schema_version": SCHEMA_VERSION, "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "implementation": platform.python_implementation(),
        "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
        "logical_cpus": os.cpu_count(), "dependencies": "Python standard library only",
        "perf_counter": {"implementation": clock.implementation, "resolution_seconds": clock.resolution},
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_status_at_measurement": git_output("status", "--short", "."),
        "source_sha256": source_hashes(), "settings": settings, "versions": VERSION_NAMES,
        "units": {"elapsed": "seconds", "latency": "nanoseconds per event", "memory": "bytes traced by tracemalloc",
                  "throughput": "events per second of engine replay", "price_ticks": "0.01 USD per BTC",
                  "qty_units": "0.00000001 BTC"},
        "limits": {"replay_seconds": settings["replay_limit_seconds"], "single_sale_seconds": settings["sale_limit_seconds"],
                   "traced_memory_bytes": settings["memory_limit_bytes"],
                   "policy": "A replay is stopped at the first block boundary after its limit and its remaining "
                             "repeats and passes are skipped. A single sale that exceeds its limit is ended by "
                             "terminating the child process. Stopped cells are saved with status 'stopped'."},
        "timing_protocol": "Fresh child process per cell. Untimed warm-up on the first 10,000 events (or a 2,000-order "
                           "book), then five repeats, each on a fresh empty book after gc.collect(). The clock "
                           "(time.perf_counter) encloses only loops over already parsed events, in blocks of at most "
                           "1,000 events; block times are summed. The cyclic garbage collector stays enabled. "
                           "Generation, reading, parsing, digests, printing and dashboard work are outside the clock. "
                           "Which version runs first is shuffled per cell with a recorded seed.",
        "latency_protocol": "Separate pass: time.perf_counter_ns around each ProcessEvent call. Percentiles use the "
                            "nearest-rank convention: the smallest observation with at least p percent of the sample "
                            "at or below it. Processing latency only; no queueing or network delay.",
        "memory_protocol": "Separate pass under tracemalloc. Preloaded input (streams up to 100,000 events) is "
                           "allocated before tracing and excluded. Larger streams are parsed block by block inside "
                           "the trace, so up to 1,000 parsed events are included. Included: the book and its indexes "
                           "and the most recent returned result with its fills. No trade history is kept. Values are "
                           "bytes of Python allocations, not auxiliary space and not process memory.",
    }


def write_outputs(output, meta, datasets, rows, complete):
    output.mkdir(parents=True, exist_ok=True)
    data = {"metadata": meta, "complete": complete, "datasets": datasets, "worked_example": worked_example_check(),
            "read_parse": [r for r in rows if r["experiment"] == "read_parse"],
            "replay": [r for r in rows if r["experiment"] == "replay"],
            "fixed_book": [r for r in rows if r["experiment"] == "fixed_book"]}
    fill_shared_peaks(data["replay"])
    (output / "measurements.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    raw, summary = raw_rows(data), summary_rows(data)
    for name, table, columns in (("raw_repeats.csv", raw, RAW_COLUMNS), ("summary.csv", summary, SUMMARY_COLUMNS)):
        with (output / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows({c: ("" if row.get(c) is None else row.get(c)) for c in columns} for row in table)
    return data


def fill_shared_peaks(replay):
    """Occupied-price peaks are counted in version B's pass (O(1) there). The same workload gives the
    same book in version A whenever both result digests agree, so the value is copied and labelled."""
    by_workload = {(r["scenario"], r["seed"], r["events"]): r for r in replay if r["version"] == "B" and r.get("outcome")}
    for row in replay:
        twin = by_workload.get((row["scenario"], row["seed"], row["events"]))
        if row["version"] == "A" and row.get("outcome") and twin:
            same = row["outcome"]["results_sha256"] == twin["outcome"]["results_sha256"]
            row["outcome"]["peak_price_levels"] = twin["outcome"]["peak_price_levels"] if same else None
            row["outcome"]["peak_price_levels_source"] = "version B pass, identical result stream" if same else None


RAW_COLUMNS = ("experiment", "run_kind", "version", "scenario", "seed", "events", "levels", "book_orders",
               "sale_pct", "requested_qty_units", "phase", "repeat", "status", "elapsed_seconds", "events_completed",
               "peak_active_orders", "peak_price_levels", "fill_count", "unfilled_qty_units", "traced_peak_bytes",
               "traced_current_bytes")
SUMMARY_COLUMNS = ("experiment", "version", "scenario", "seed", "events", "levels", "book_orders", "sale_pct",
                   "requested_qty_units", "status", "events_completed", "stopped_after_seconds",
                   "replay_seconds_median", "build_seconds_median", "tail_seconds_median",
                   "throughput_events_per_second", "read_parse_seconds_median", "construction_seconds_median",
                   "sell_seconds_median", "latency_p50_ns", "latency_p95_ns", "latency_p99_ns",
                   "peak_active_orders", "peak_price_levels", "final_active_orders", "fill_count", "makers_touched",
                   "price_levels_visited", "unfilled_qty_units", "traced_peak_bytes", "traced_final_bytes",
                   "results_sha256")


def raw_rows(data):
    rows = []
    for cell in data["read_parse"]:
        base = {k: cell.get(k) for k in ("experiment", "scenario", "seed", "events", "levels")}
        rows += [dict(base, run_kind="timing", phase="read_parse", repeat=r["repeat"], status="ok",
                      elapsed_seconds=r["elapsed_seconds"], events_completed=r["events"]) for r in cell["repeats"]]
    for cell in data["replay"]:
        outcome, memory = cell.get("outcome") or {}, cell.get("memory") or {}
        base = {k: cell.get(k) for k in ("experiment", "version", "scenario", "seed", "events", "levels")}
        base.update(peak_active_orders=outcome.get("peak_active_orders"),
                    peak_price_levels=outcome.get("peak_price_levels"), fill_count=outcome.get("fill_count"))
        boundary = workloads.build_boundary(cell["scenario"], cell["events"])
        for r in cell["repeats"]:
            rows.append(dict(base, run_kind="timing", phase="replay", repeat=r["repeat"], status=r["status"],
                             elapsed_seconds=r["elapsed_seconds"], events_completed=r["events_completed"]))
            if boundary is not None and r["status"] == "ok":
                build = r["checkpoint_seconds"][boundary * CHECKPOINTS // cell["events"] - 1]
                rows.append(dict(base, run_kind="timing", phase="build", repeat=r["repeat"], status="ok",
                                 elapsed_seconds=build, events_completed=boundary))
                rows.append(dict(base, run_kind="timing", phase="after_build", repeat=r["repeat"], status="ok",
                                 elapsed_seconds=r["elapsed_seconds"] - build,
                                 events_completed=cell["events"] - boundary))
        if memory:
            rows.append(dict(base, run_kind="memory", phase="replay", repeat=1, status=memory["status"],
                             events_completed=memory["events_completed"], traced_peak_bytes=memory["peak_bytes"],
                             traced_current_bytes=memory["final_current_bytes"]))
    for cell in data["fixed_book"]:
        outcome, memory = cell.get("outcome") or {}, cell.get("memory") or {}
        base = {k: cell.get(k) for k in ("experiment", "version", "scenario", "seed", "events", "levels",
                                         "book_orders", "sale_pct", "requested_qty_units")}
        base.update(peak_active_orders=outcome.get("peak_active_orders"),
                    peak_price_levels=outcome.get("peak_price_levels"), fill_count=outcome.get("fill_count"),
                    unfilled_qty_units=outcome.get("unfilled_qty_units"))
        for r in cell["repeats"]:
            rows.append(dict(base, run_kind="timing", phase="construction", repeat=r["repeat"], status="ok",
                             elapsed_seconds=r["construction_seconds"], events_completed=cell["book_orders"]))
            rows.append(dict(base, run_kind="timing", phase="sell", repeat=r["repeat"],
                             status="ok" if r["sell_seconds"] is not None else "stopped",
                             elapsed_seconds=r["sell_seconds"]))
        if memory:
            rows.append(dict(base, run_kind="memory", phase="sell", repeat=1, status="ok",
                             traced_peak_bytes=memory["sell_peak_bytes"],
                             traced_current_bytes=memory["sell_current_bytes"]))
    return rows


def summary_rows(data):
    parse = {(r["scenario"], r["seed"], r["events"]): r.get("read_parse_seconds_median") for r in data["read_parse"]}
    rows = []
    for cell in data["replay"] + data["fixed_book"]:
        outcome, memory, latency = cell.get("outcome") or {}, cell.get("memory") or {}, cell.get("latency") or {}
        row = {k: cell.get(k) for k in SUMMARY_COLUMNS}
        row.update({k: outcome.get(k) for k in ("peak_active_orders", "peak_price_levels", "final_active_orders",
                                                "fill_count", "makers_touched", "price_levels_visited",
                                                "unfilled_qty_units", "results_sha256") if k in outcome})
        overall = latency.get("overall") or {}
        row.update(latency_p50_ns=overall.get("p50_ns"), latency_p95_ns=overall.get("p95_ns"),
                   latency_p99_ns=overall.get("p99_ns"),
                   traced_peak_bytes=memory.get("peak_bytes", memory.get("sell_peak_bytes")),
                   traced_final_bytes=memory.get("final_current_bytes", memory.get("sell_current_bytes")),
                   read_parse_seconds_median=parse.get((cell["scenario"], cell["seed"], cell["events"])))
        if cell["experiment"] == "fixed_book":
            row["results_sha256"] = outcome.get("fills_sha256")
        rows.append(row)
    return rows


def run(output, settings, resume=False, in_process=False):
    partial = output / "measurements.partial.json"
    done = {}
    if resume and partial.exists():
        saved = json.loads(partial.read_text(encoding="utf-8"))
        if saved.get("settings") == settings and saved.get("source_sha256") == source_hashes():
            done = saved["cells"]
            print(f"Resuming: {len(done)} cells already measured", flush=True)
        else:
            print("Not resuming: settings or sources changed since the partial run", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    if on_mains_power() is False:
        print("WARNING: running on battery; timings are throttled and less stable", flush=True)
    keep_awake(True)
    print("Generating event files (outside timing)...", flush=True)
    datasets, cells = build_plan(settings)
    meta = metadata(settings)
    started = time.perf_counter()
    rows = []
    for index, (kind, spec) in enumerate(cells, 1):
        key = cell_key(kind, spec)
        if key not in done:
            messages, note = run_child(kind, spec, in_process)
            done[key] = COLLECTORS[kind](spec, messages, note)
            done[key]["version_position"] = spec.get("version_position")
            partial.write_text(json.dumps({"settings": settings, "source_sha256": meta["source_sha256"],
                                           "cells": done}), encoding="utf-8")
        row = done[key]
        rows.append(row)
        label = " ".join(str(spec[k]) for k in ("experiment", "version", "scenario", "events", "book_orders",
                                                "levels", "sale_pct", "seed") if k in spec)
        print(f"[{index}/{len(cells)} {time.perf_counter() - started:6.0f}s] {label}: {row['status']}", flush=True)
    meta["finished_utc"] = datetime.now(timezone.utc).isoformat()
    meta["mains_power_at_finish"] = on_mains_power()
    keep_awake(False)
    data = write_outputs(output, meta, datasets, rows, complete=True)
    partial.unlink(missing_ok=True)
    problems = [r for r in rows if r["status"] == "error"]
    print(f"Saved {len(rows)} cells to {output} ({len(problems)} with errors)", flush=True)
    for row in problems:
        print(row.get("error"), flush=True)
    return data


def default_settings(quick=False):
    if quick:
        return {"sizes": [400, 2000], "single_seed_sizes": [], "seeds": [42], "levels": 1000, "repeats": 5,
                "replay_limit_seconds": 5.0, "sale_limit_seconds": 5.0, "memory_limit_bytes": 256 << 20,
                "fixed_single_seed_sizes": [], "concentration_orders": 2000, "concentration_levels": [4],
                "concentration_seeds": [42],
                "sale_percents": [10, 100, 200], "order_seed": 2026}
    return {"sizes": [1_000, 10_000, 100_000], "single_seed_sizes": [30_000, 1_000_000], "seeds": [42, 43, 44],
            "levels": 1000, "repeats": 5, "replay_limit_seconds": 60.0, "sale_limit_seconds": 30.0,
            "memory_limit_bytes": 1 << 30, "fixed_single_seed_sizes": [3_000, 30_000],
            "concentration_orders": 10_000, "concentration_levels": [1, 4, 32], "concentration_seeds": [42],
            "sale_percents": [10, 100, 200], "order_seed": 2026}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "results")
    parser.add_argument("--quick", action="store_true", help="small sizes, one seed, 5 s limits (smoke run)")
    parser.add_argument("--resume", action="store_true", help="continue from measurements.partial.json")
    parser.add_argument("--in-process", action="store_true", help="no child processes (debugging; limits not enforced)")
    parser.add_argument("--replay-limit", type=float, help="seconds per replay before it is stopped")
    parser.add_argument("--sale-limit", type=float, help="seconds per single market sell before it is stopped")
    args = parser.parse_args()
    settings = default_settings(args.quick)
    if args.replay_limit:
        settings["replay_limit_seconds"] = args.replay_limit
    if args.sale_limit:
        settings["sale_limit_seconds"] = args.sale_limit
    if tracemalloc.is_tracing():
        parser.error("stop external memory tracing before benchmarking")
    run(args.output, settings, args.resume, args.in_process)


if __name__ == "__main__":
    main()
