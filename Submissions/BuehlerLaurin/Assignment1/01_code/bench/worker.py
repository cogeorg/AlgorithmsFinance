"""One isolated measurement mode/cell; journals completed observations immediately."""
import argparse
from collections import Counter
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback
import tracemalloc

from bench import core
from bench.protocol import timing_plan
from bench.harness import peak_traced_bytes, percentiles, time_repeats, traced_curve
from lob.replay import read_events


class ResourceStop(Exception):
    def __init__(self, reason, observed=0, phase=None):
        super().__init__(reason)
        self.reason, self.observed = reason, observed
        self.phase = phase


def measure(phase, function, limit_s):
    """Shared harness measures ONLY function; protocol I/O/checks are outside it."""
    print(json.dumps({"bench_phase": phase, "action": "start"}), flush=True)
    captured = []
    result = time_repeats(lambda: None, lambda _: function(), warmup=0, repeats=1,
                          check=captured.append, disable_gc=False)
    seconds = result["run_s"][0]
    print(json.dumps({"bench_phase": phase, "action": "end", "elapsed_s": seconds}), flush=True)
    if seconds > limit_s:
        raise ResourceStop("time_limit:" + phase, seconds, phase)
    return seconds, captured[0]


def run_job(job):
    case, version, mode = job["case"], job["version"], job["mode"]
    limit_s, limit_bytes = job["limit_s"], job["limit_bytes"]
    warmups, repeats, label = timing_plan(version, case["size"])
    journal = Path(job["journal"])
    journal.parent.mkdir(parents=True, exist_ok=True)
    base = {"case_id": case["id"], "experiment": case["part"], "workload": case["label"],
            "size": case["size"], "events": case["events"], "seed": case["seed"],
            "levels": case["levels"], "own": case["own"], "percent": case.get("percent", ""),
            "version": version, "mode": mode, "input_sha256": case["sha256"],
            "registration": case.get("registration", "pre-registered Phase 4"),
            "prefill_events": case.get("prefill_events", 0), "driver_n": case.get("driver_n", ""),
            "timing_protocol": label}
    def emit(kind, **fields):
        row = {**base, "status": "ok", **fields}
        with journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"kind": kind, "row": row}) + "\n")
    gc.enable()
    phase, repeat = "parse", -1
    try:
        def verify_input():
            digest = hashlib.sha256()
            with Path(case["path"]).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(chunk)
            assert digest.hexdigest() == case["sha256"], "input differs from generation manifest"
        measure("input_hash", verify_input, limit_s)
        parse_s, events = measure("parse", lambda: list(read_events(case["path"])), limit_s)
        assert len(events) == case["events"], case["id"]
        _, sample_n = measure("sample_check", lambda: core.check_case(case, events, version, mode == "counts"), limit_s)
        work = core.workload_events(case, events)
        construction = core.construction_events(case, events)  # input slices outside tracing
        base["replayed_events"] = len(work)
        requested = work[0]["qty_units"] if case["part"] == "liquidation" else ""
        base["requested_sell_qty_units"] = requested
        emit("checks", sample_events=sample_n, comparison="every sampled result/book vs A", counters_on=mode == "counts")
        if mode == "timing":
            emit("timing", phase="parse", repeat=0, seconds=parse_s, warmup=False, repeats_requested=1)
            for repeat in range(-warmups, repeats):
                phase = "construction"
                construction_s, book = measure(phase, lambda: core.prepare_book(case, events, version), limit_s)
                emit("timing", phase=phase, repeat=repeat, seconds=construction_s,
                     warmup=repeat < 0, repeats_requested=repeats)
                phase = "replay"
                replay_s, result = measure(phase, lambda: core.replay(book, work), limit_s)
                emit("timing", phase=phase, repeat=repeat, seconds=replay_s, warmup=repeat < 0, repeats_requested=repeats)
                emit("timing", phase="total", repeat=repeat, seconds=parse_s + construction_s + replay_s,
                     warmup=repeat < 0, repeats_requested=repeats)
                del book, result
        elif mode == "latency":
            _, book = measure("construction", lambda: core.prepare_book(case, events, version), limit_s)
            def instrument():
                values = []
                for event in work:
                    start = time.perf_counter_ns()
                    book.process(event)
                    values.append(time.perf_counter_ns() - start)
                return values
            phase = "latency"
            _, values = measure(phase, instrument, limit_s)
            edge = max(1, len(work) // 10)
            for segment, indexes in (("all", range(len(work))), ("early", range(edge)),
                                     ("late", range(max(0, len(work)-edge), len(work)))):
                by_type = {"ALL": []}
                for i in indexes:
                    by_type.setdefault(work[i]["type"], []).append(values[i])
                    by_type["ALL"].append(values[i])
                for kind, samples in by_type.items():
                    p = percentiles(samples)
                    emit("latency", event_type=kind, segment=segment, n=p["n"],
                         p50_ns=p["p50"], p95_ns=p["p95"], p99_ns=p["p99"], max_ns=p["max"],
                         convention="nearest-rank", label="closed-loop service time")
                    for exponent, count in sorted(Counter(max(1, v).bit_length()-1 for v in samples).items()):
                        emit("latency_histogram", event_type=kind, segment=segment,
                             bin_lo_ns=2**exponent, bin_hi_ns=2**(exponent+1), count=count)
        elif mode == "memory":
            def guarded(book, event):
                result = book.process(event)
                peak = tracemalloc.get_traced_memory()[1]
                if peak > limit_bytes:
                    raise ResourceStop("traced_peak_bytes", peak)
                return result
            def setup():
                book = core.make_book(version)
                for event in construction:
                    guarded(book, event)
                return book
            def sell_or_replay(book):
                last = None
                for event in work:
                    last = guarded(book, event)
                return last
            phase = "memory_peak"
            _, peak = measure(phase, lambda: peak_traced_bytes(setup, sell_or_replay, include_setup=True), limit_s)
            emit("memory", measure="peak", processed=len(work), current_bytes=peak["current_bytes"],
                 peak_bytes=peak["peak_bytes"], live_orders="", price_levels="", heap_entries="", stale_heap_prices="",
                 includes="book construction + current result; input excluded; no history")
            curve_events = construction + work
            phase = "memory_curve"
            _, curve = measure(phase, lambda: traced_curve(guarded, None, curve_events,
                setup=lambda: core.make_book(version), every=max(1, len(curve_events)//50), observe=core.live_stats), limit_s)
            for sample in curve:
                emit("memory", measure="curve", **{k: sample[k] for k in
                     ("processed", "current_bytes", "peak_bytes", "live_orders", "price_levels", "heap_entries", "stale_heap_prices")},
                     includes="book incl initial state; input/results/sample buffers excluded")
        elif mode == "counts":
            _, book = measure("construction", lambda: core.prepare_book(case, events, version, True), limit_s)
            before = book.counters.as_dict()
            if case["part"] == "liquidation" or case.get("prefill_events", 0):
                for name, value in before.items():
                    emit("counts", phase="construction", counter=name, value=value, applicable=True)
            phase = "counts"
            measure(phase, lambda: core.replay(book, work), limit_s)
            after = book.counters.as_dict()
            for name, value in after.items():
                delta = value if name.endswith("_peak") else value - before[name]
                if case["part"] != "liquidation" and not case.get("prefill_events", 0):
                    delta = value
                applicable = not (version == "A" and (name.startswith("stale_") or name in
                                  ("levels_visited", "compactions", "compaction_records_scanned", "price_list_shifts")))
                emit("counts", phase="replay", counter=name, value=delta if applicable else "", applicable=applicable)
            active, levels, heap, stale = core.live_stats(book)
            for name, value in zip(("active_orders_final", "occupied_levels_final", "heap_entries_final", "stale_heap_prices_final"),
                                   (active, levels, heap, stale)):
                emit("counts", phase="replay", counter=name, value=value, applicable=value >= 0)
        else:
            raise ValueError("unknown measurement mode: " + mode)
        emit("result", phase=mode, status="ok", repeats_requested=repeats if mode == "timing" else 1)
        return 0
    except ResourceStop as exc:
        emit("stops", phase=exc.phase or phase, repeat=repeat, status="stopped", reason=exc.reason,
             observed=exc.observed, limit_s=limit_s, limit_bytes=limit_bytes, seconds="",
             repeats_requested=repeats if mode == "timing" else 1)
        return 124
    except MemoryError:
        emit("stops", phase=phase, repeat=repeat, status="stopped", reason="allocation_failed",
             observed="", limit_s=limit_s, limit_bytes=limit_bytes, seconds="",
             repeats_requested=repeats if mode == "timing" else 1)
        return 124
    except Exception as exc:
        emit("stops", phase=phase, repeat=repeat, status="error", reason=repr(exc), seconds="")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    args = parser.parse_args()
    raise SystemExit(run_job(json.loads(args.job.read_text(encoding="utf-8"))))
