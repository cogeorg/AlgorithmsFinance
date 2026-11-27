"""Reproducible POSIX benchmark. Every measurement is executed, never estimated."""
import argparse
from collections import defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import random
import signal
import statistics
import subprocess
import sys
import time
import tracemalloc

from generate_orders import SCENARIOS, events, write_stream
from orderbook.io import read_events

ROOT = Path(__file__).resolve().parent
VERSIONS = ("baseline", "revised")


class LimitReached(Exception):
    pass


@contextmanager
def deadline(seconds):
    def alarm(signum, frame):
        raise LimitReached(f"wall-clock limit {seconds}s")
    old = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    paths = [ROOT / "benchmark.py", ROOT / "generate_orders.py", ROOT / "replay.py"]
    paths += sorted((ROOT / "orderbook").glob("*.py"))
    paths += sorted((ROOT / "tests").glob("test_*.py"))
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def percentile(values, fraction):
    """Nearest rank: sorted samples[ceil(fraction*n)-1], no interpolation."""
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(fraction * len(values)) - 1)]


class Observer:
    """Independent active-depth accounting, used outside primary timing."""
    def __init__(self):
        self.orders, self.prices = {}, defaultdict(int)
        self.active_peak = self.price_peak = self.fills = 0
        self.unfilled_market = 0

    def remove(self, ident):
        side, price, qty = self.orders.pop(ident)
        self.prices[side, price] -= 1
        if not self.prices[side, price]:
            del self.prices[side, price]

    def update(self, event, result):
        if result["status"] == "rejected":
            raise AssertionError(f"valid generator event rejected: {result}")
        if event["type"] == "CANCEL":
            if result["status"] == "cancelled":
                assert result["cancelled_qty_units"] == self.orders[event["target_order_id"]][2]
                self.remove(event["target_order_id"])
        else:
            self.fills += len(result["fills"])
            assert event["qty_units"] == result["unfilled_qty_units"] + sum(
                f["qty_units"] for f in result["fills"])
            for fill in result["fills"]:
                side, price, qty = self.orders[fill["maker_id"]]
                assert price == fill["price_ticks"] and 0 < fill["qty_units"] <= qty
                if qty == fill["qty_units"]:
                    self.remove(fill["maker_id"])
                else:
                    self.orders[fill["maker_id"]] = (side, price, qty - fill["qty_units"])
            if event["type"] == "LIMIT" and result["unfilled_qty_units"]:
                self.orders[event["order_id"]] = (event["side"], event["price_ticks"],
                                                    result["unfilled_qty_units"])
                self.prices[event["side"], event["price_ticks"]] += 1
            if event["type"] == "MARKET_SELL":
                self.unfilled_market += result["unfilled_qty_units"]
        self.active_peak = max(self.active_peak, len(self.orders))
        self.price_peak = max(self.price_peak, len(self.prices))

    def summary(self):
        return dict(active_order_peak=self.active_peak, price_level_peak=self.price_peak,
                    active_orders_final=len(self.orders), occupied_prices_final=len(self.prices),
                    fill_count=self.fills, discarded_market_qty=self.unfilled_market)


def engine(version, instrument=False):
    return importlib.import_module(f"orderbook.{version}").OrderBook(instrument=instrument)


def replay(version, rows):
    book, last = engine(version), None
    for event in rows:
        last = book.process(event)
    return book, last


def observe(version, rows, instrument=False):
    book, observer, fingerprint = engine(version, instrument), Observer(), hashlib.sha256()
    for event in rows:
        result = book.process(event)
        observer.update(event, result)
        fingerprint.update(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())
        fingerprint.update(b"\n")
    snapshot = book.inspect()
    fingerprint.update(json.dumps(snapshot, sort_keys=True).encode())
    assert len(snapshot) == len(observer.orders)
    return dict(**observer.summary(), result_sha256=fingerprint.hexdigest(),
                storage=book.storage(), operations=book.metrics)


def fixed_bids(count, levels, seed):
    rng = random.Random(seed)
    return [dict(seq=i, event_id=f"b{i}", type="LIMIT", order_id=f"b{i}", side="BUY",
                 price_ticks=6000000-rng.randrange(levels), qty_units=rng.randrange(1, 101)*1000000)
            for i in range(1, count+1)]


def median_summaries(rows):
    groups = defaultdict(list)
    keys = ("version", "scenario", "seed", "event_count", "levels", "sale_percent", "phase")
    for row in rows:
        if row.get("repeat", 0) > 0 and row["status"] == "ok" and row["phase"] in (
                "replay", "construction", "parse", "liquidation", "reset", "streaming_app", "application"):
            groups[tuple(row.get(k) for k in keys)].append(row)
    output = []
    for group, samples in groups.items():
        result = dict(zip(keys, group))
        result.update(repeats=len(samples), elapsed_seconds=statistics.median(
            r["elapsed_seconds"] for r in samples))
        if result["phase"] in ("replay", "streaming_app", "application"):
            result["throughput_events_per_second"] = result["event_count"] / result["elapsed_seconds"]
        output.append(result)
    return output


class Experiment:
    def __init__(self, args):
        self.args, self.rows = args, []
        self.out = ROOT / args.out
        self.out.mkdir(parents=True, exist_ok=True)
        if (self.out / "measurements.jsonl").exists():
            raise SystemExit("Refusing to overwrite saved results; choose a new --out directory")
        self.raw = (self.out / "measurements.jsonl").open("w")
        self.latency = gzip.open(self.out / "latency_raw.csv.gz", "wt", newline="")
        self.writer = csv.writer(self.latency)
        self.writer.writerow(("version", "scenario", "seed", "event_count", "seq", "type", "elapsed_seconds"))
        self.inputs = []

    def save(self, row):
        self.rows.append(row)
        self.raw.write(json.dumps(row, sort_keys=True) + "\n")
        self.raw.flush()
        return row

    def trial(self, case, phase, repeat, fn):
        started = time.perf_counter()
        try:
            with deadline(self.args.limit_seconds):
                started = time.perf_counter()
                value = fn()
                elapsed = time.perf_counter() - started
            return self.save(dict(case, phase=phase, repeat=repeat, status="ok",
                                  elapsed_seconds=elapsed)), value
        except LimitReached as exc:
            row = self.save(dict(case, phase=phase, repeat=repeat, status="stopped",
                                 elapsed_seconds=time.perf_counter()-started, reason=str(exc)))
            return row, None

    def repeated(self, case, phase, fn):
        warmup, _ = self.trial(case, phase, 0, fn)
        if warmup["status"] != "ok":
            return False
        for repeat in range(1, 6):
            row, _ = self.trial(case, phase, repeat, fn)
            if row["status"] != "ok":
                return False
        return True

    def input(self, scenario, count, seed, levels=1000):
        folder = ROOT / "data/generated"
        folder.mkdir(exist_ok=True)
        path = folder / f"{scenario}_{count}_s{seed}_p{levels}.jsonl.gz"
        if not path.exists():
            write_stream(path, events(scenario, count, seed, levels))
        self.inputs.append(dict(path=str(path.relative_to(ROOT)), scenario=scenario,
                                event_count=count, seed=seed, levels=levels, sha256=digest(path),
                                command=f"python3 generate_orders.py --scenario {scenario} --events {count} --seed {seed} --levels {levels} --out {path.relative_to(ROOT)}"))
        return path

    def latency_run(self, case, rows):
        samples = []
        def run():
            book = engine(case["version"])
            for event in rows:
                start = time.perf_counter()
                result = book.process(event)
                samples.append(time.perf_counter()-start)
            return book, result
        row, _ = self.trial(case, "latency_instrumentation", 1, run)
        # A stopped run retains its actual prefix and is labelled stopped.
        for event, elapsed in zip(rows, samples):
            self.writer.writerow((case["version"], case["scenario"], case["seed"],
                                  len(rows), event["seq"], event["type"], repr(elapsed)))
        self.latency.flush()
        cohorts = {"all": samples, "early": samples[:max(1,len(rows)//10)],
                   "late": samples[-max(1,len(rows)//10):] if len(samples)==len(rows) else []}
        for kind in ("LIMIT", "CANCEL", "MARKET_SELL"):
            cohorts[kind] = [dt for event, dt in zip(rows, samples) if event["type"]==kind]
        for cohort, values in cohorts.items():
            if values:
                self.save(dict(case, phase="latency_summary", repeat=1, status=row["status"],
                               cohort=cohort, samples=len(values), p50_seconds=percentile(values,.5),
                               p95_seconds=percentile(values,.95), p99_seconds=percentile(values,.99)))

    def memory_run(self, case, rows):
        checkpoints = []
        def run():
            tracemalloc.start()
            book, result = engine(case["version"]), None
            sample_at = {1, max(1,len(rows)//10), max(1,len(rows)//2), len(rows)}
            try:
                for index, event in enumerate(rows, 1):
                    result = book.process(event)
                    if index in sample_at or index % 1000 == 0:
                        current, peak = tracemalloc.get_traced_memory()
                        if peak > self.args.memory_limit_bytes:
                            raise LimitReached("traced allocation budget exceeded")
                        if index in sample_at:
                            checkpoints.append(dict(events_processed=index, current_bytes=current,
                                                    peak_bytes=peak, **book.storage()))
                current, peak = tracemalloc.get_traced_memory()
                # Result remains alive while these allocation values are read.
                return dict(current_traced_bytes=current, peak_traced_bytes=peak,
                            checkpoints=checkpoints, **book.storage())
            finally:
                tracemalloc.stop()
        row, value = self.trial(case, "memory_run", 1, run)
        if value is not None:
            self.save(dict(case, phase="memory", repeat=1, status="ok", **value))

    def stream_case(self, scenario, count, seed):
        path = self.input(scenario, count, seed)
        parse = dict(version="input", scenario=scenario, seed=seed, event_count=count, levels=1000)
        self.repeated(parse, "parse", lambda: list(read_events(path)))
        rows = list(read_events(path))
        reference_case = dict(parse, version="revised")
        row, reference = self.trial(reference_case, "depth_and_correctness", 1,
                                    lambda: observe("revised", rows))
        if reference:
            self.save(dict(reference_case, phase="depth", repeat=1, status="ok", **reference))
        for version in VERSIONS:
            case = dict(parse, version=version)
            success = self.repeated(case, "replay", lambda: replay(version, rows))
            if seed == self.args.seeds[0]:
                self.repeated(case, "application", lambda: replay(version, read_events(path)))
            if version == "baseline" and success:
                checked, observed = self.trial(case, "depth_and_correctness", 1,
                                                lambda: observe(version, rows))
                if observed:
                    assert reference and observed["result_sha256"] == reference["result_sha256"]
                    self.save(dict(case, phase="correctness", repeat=1, status="ok",
                                   result_sha256=observed["result_sha256"], compared_to="revised"))
            if scenario in ("buildup", "crowded", "sweep"):
                prefix = rows[:max(1,len(rows)*4//5)] if scenario=="sweep" else rows
                # If full replay failed, construction is still independently attempted.
                self.repeated(case, "construction", lambda: replay(version, prefix))
            self.memory_run(case, rows)
            if count <= 10000 or (count==100000 and seed==42 and scenario in ("buildup", "cancel_churn")):
                self.latency_run(case, rows)
            if count==1000:
                row, counted = self.trial(case, "counter_run", 1, lambda: observe(version, rows, True))
                if counted:
                    self.save(dict(case, phase="counters", repeat=1, status="ok", **counted))
        print(f"stream {scenario} M={count} seed={seed}", flush=True)

    def sell_cases(self):
        for count in self.args.sizes:
            for levels in (4, 1000):
                rows = fixed_bids(count, levels, 42)
                total = sum(r["qty_units"] for r in rows)
                for version in VERSIONS:
                    for percent in (10,100,200):
                        requested = max(1,(total*percent+99)//100)
                        case = dict(version=version, scenario="liquidation", event_count=count,
                                    levels=levels, seed=42, sale_percent=percent, requested_qty_units=requested)
                        event = dict(seq=count+1,event_id="sell",order_id="sell",type="MARKET_SELL",
                                     qty_units=requested)
                        completed = True
                        for repeat in range(6):
                            # A fresh book is constructed and its reset time retained on every trial.
                            reset, prepared = self.trial(case,"reset",repeat,lambda: replay(version,rows))
                            if not prepared:
                                completed = False
                                break
                            book, _ = prepared
                            sale, result = self.trial(case,"liquidation",repeat,lambda: book.FillMarketSell(event))
                            if not result:
                                completed = False
                                break
                            if repeat:
                                fills = result["fills"]
                                self.save(dict(case,phase="sale_outcome",repeat=repeat,status="ok",
                                               fill_count=len(fills),makers_touched=len(fills),
                                               prices_visited=len({f["price_ticks"] for f in fills}),
                                               unfilled_qty_units=result["unfilled_qty_units"],
                                               proceeds_tick_units=sum(f["price_ticks"]*f["qty_units"] for f in fills)))
                                assert sum(f["qty_units"] for f in fills)==min(total,requested)
                                assert result["unfilled_qty_units"]==max(0,requested-total)
                        if not completed:
                            self.save(dict(case,phase="sale_outcome",repeat=0,status="stopped",
                                           reason="construction/reset or matching trial exceeded limit"))
                print(f"liquidations B={count} levels={levels}",flush=True)

    def million(self):
        # Streaming avoids the declared 200,000-event preload cap. This is a
        # separate end-to-end experiment, never relabelled as engine-only time.
        count, seed, scenario = 1000000, 42, "cancel_churn"
        path = self.input(scenario,count,seed)
        case = dict(version="input",scenario=scenario,event_count=count,seed=seed,levels=1000)
        def parse_stream():
            return sum(1 for _ in read_events(path))
        self.repeated(case,"parse",parse_stream)
        for version in VERSIONS:
            self.repeated(dict(case,version=version),"streaming_app",lambda: replay(version,read_events(path)))
        print("million-event streaming feasibility trial recorded",flush=True)

    def finish(self):
        self.raw.close()
        self.latency.close()
        (self.out/"summary.json").write_text(json.dumps(median_summaries(self.rows),indent=2)+"\n")
        (self.out/"inputs.json").write_text(json.dumps(self.inputs,indent=2)+"\n")
        try:
            commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        except (OSError,subprocess.CalledProcessError):
            commit=None
        meta=dict(created_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,
                  executable=sys.executable,platform=platform.platform(),machine=platform.machine(),
                  processor=platform.processor(),cpu_count=os.cpu_count(),code_commit=commit,source_sha256=source_hashes(),
                  settings=vars(self.args),percentile="nearest rank ceil(p*n)-1; no interpolation",
                  timing="perf_counter; one full warmup (repeat 0), five repeats; fresh empty book; replay excludes parsing; application includes streamed parsing (first seed); destruction of returned book after call excluded",
                  memory="one separate tracemalloc run; preloaded events excluded; book, transient Python allocations and latest returned result included; no trade history; not RSS",
                  limits="wall deadline per individual warmup/repeat/diagnostic; traced allocation budget checked every 1000 events in memory runs only; preload cap 200000 events; no process RSS cap",
                  latency="separate minimal per-event timers, engine instrumentation off; values buffered until replay ends; all <=10000 configurations plus 100000 buildup/churn seed42; stopped prefixes labelled",
                  diagnostic="active/price peaks and result fingerprints from separate revised replay; baseline compared when its diagnostic completed; operation counts only at M=1000",
                  million="cancel_churn seed42, streaming end-to-end including parsing, to honor preload cap; both versions same input/limit; other million scenarios not attempted",
                  dependencies="Python standard library only; POSIX signal timers required for benchmark",
                  measurements_sha256=digest(self.out/"measurements.jsonl"),latency_sha256=digest(self.out/"latency_raw.csv.gz"))
        (self.out/"environment.json").write_text(json.dumps(meta,indent=2)+"\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes",nargs="+",type=int,default=[1000,10000,100000])
    parser.add_argument("--seeds",nargs="+",type=int,default=[42,43,44])
    parser.add_argument("--scenarios",nargs="+",choices=SCENARIOS,default=list(SCENARIOS))
    parser.add_argument("--limit-seconds",type=float,default=4.0)
    parser.add_argument("--memory-limit-bytes",type=int,default=268435456)
    parser.add_argument("--out",default="results")
    parser.add_argument("--skip-million",action="store_true")
    args=parser.parse_args()
    if min(args.sizes)<1 or max(args.sizes)>200000 or args.limit_seconds<=0:
        parser.error("sizes must be 1..200000; limit must be positive")
    experiment=Experiment(args)
    try:
        for count in args.sizes:
            for scenario in args.scenarios:
                for seed in args.seeds:
                    experiment.stream_case(scenario,count,seed)
        experiment.sell_cases()
        if not args.skip_million:
            experiment.million()
    finally:
        experiment.finish()


if __name__=="__main__":
    main()
