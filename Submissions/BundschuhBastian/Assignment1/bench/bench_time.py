"""Phase 6a: primary timing runs of Version A and Version B (README: "Benchmark limits and run rules").

    .venv/bin/python -m bench.bench_time                       # all runs, resumable
    .venv/bin/python -m bench.bench_time --versions B --max-events 10000

Per (version, stream) = one run, in its own child process:
  1. parse the file ONCE (gzip + JSON), timed separately as `parse_seconds`;
  2. the first replay is timed. <= 60 s: it is the warm-up and 5 timed replays follow;
     > 60 s: it is the only measurement (`repeats=1`);
  3. every replay starts from a fresh empty book, results are discarded, `time.perf_counter`,
     the garbage collector is ENABLED (default Python behaviour); `gc.collect()` runs before each
     replay so that every replay starts from the same heap state, outside the timed region;
  4. a replay that reaches 600 s is stopped: `status=stopped`, remaining repeats skipped, nothing
     is estimated. The same limits apply to A and B.
Streams: 5 scenarios x M in {1,000; 10,000; 100,000} x seeds 42-44 for A and B; the 1,000,000-event
files (seed 42) for B, and for A only if its 100,000-event run on that scenario had a median below
60 s (otherwise `status=not_run` with the reason).
Writes results/time_raw.csv (one row per replay, with the run's median on every row) and, through
bench.common.write_environment(), results/env.json.
"""
from __future__ import annotations

import argparse
import datetime
import gc
import statistics
import time

from bench import common
from bench.common import RESULTS, append_csv, read_csv, run_result, stream_path
from bench.harness import run_limited
from lob import VERSIONS
from lob.common import load_events

TIME_RAW = RESULTS / "time_raw.csv"
CANARY_RAW = RESULTS / "canary_raw.csv"
CANARY_SPEC = dict(scenario="mixed", events=100000, seed=42, levels=1000)    # always run with B
FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "block", "canary_point",
          "version", "scenario", "seed", "events", "levels", "status", "reason", "phase", "repeat",
          "replay_status", "elapsed_seconds", "median_seconds", "repeats", "parse_seconds",
          "events_done", "limit_seconds"]


def _replay(cls, events) -> float:
    """One timed replay of `events` through a fresh book (name starts with _replay: see harness)."""
    book = cls()
    process = book.process
    gc.collect()                      # outside the timed region; gc stays enabled afterwards
    start = time.perf_counter()
    for e in events:
        process(e)
    return time.perf_counter() - start


def time_worker(conn, version: str, path: str, slow_first_s: float, repeats: int) -> None:
    start = time.perf_counter()
    events = load_events(path)                                  # parsed once, outside timing
    conn.send(("parsed", time.perf_counter() - start, len(events)))
    cls = VERSIONS[version]
    conn.send(("unit_start", "first"))
    first = _replay(cls, events)
    conn.send(("unit_done", "first", first))
    if first > slow_first_s:
        conn.send(("mode", "single"))
        return
    conn.send(("mode", "warmup"))
    for r in range(repeats):
        conn.send(("unit_start", f"timed{r}"))
        conn.send(("unit_done", f"timed{r}", _replay(cls, events)))


def run_one(version: str, spec: dict, limit_s: float, slow_first_s: float, repeats: int,
            out_path=None, extra: dict | None = None) -> dict:
    """Run one (version, stream) pair; append its rows to time_raw.csv (or `out_path`); return the
    run summary. `start_utc` and the power state are taken when the run starts."""
    out_path = out_path or TIME_RAW
    base = {"start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            **common.power_state(), **(extra or {}), "version": version, **{k: spec[k] for k in ("scenario", "seed", "events", "levels")},
            "limit_seconds": limit_s}
    result = run_limited(time_worker, (version, str(stream_path(**spec)), slow_first_s, repeats),
                         limit_s)
    parse_s, mode, done = None, None, {}
    for msg in result["messages"]:
        if msg[0] == "parsed":
            parse_s = msg[1]
        elif msg[0] == "mode":
            mode = msg[1]
        elif msg[0] == "unit_done":
            done[msg[1]] = msg[2]
    rows = []
    if "first" in done:
        rows.append({"phase": "single" if mode == "single" else "warmup", "repeat": 0,
                     "replay_status": "ok", "elapsed_seconds": done["first"]})
    for r in range(common.TIMED_REPEATS):
        if f"timed{r}" in done:
            rows.append({"phase": "timed", "repeat": r, "replay_status": "ok",
                         "elapsed_seconds": done[f"timed{r}"]})
    status, reason = "ok", ""
    if result["outcome"] == "stopped":
        status, tag = "stopped", result["stopped_tag"]
        reason = f"a replay reached the {limit_s:g} s limit; remaining repeats skipped"
        rows.append({"phase": "single" if tag == "first" else "timed",
                     "repeat": 0 if tag == "first" else int(tag[5:]), "replay_status": "stopped",
                     "elapsed_seconds": result["stopped_after_s"],
                     "events_done": result["events_done"]})
    elif result["outcome"] == "error":
        status, reason = "error", result["error"]
    measured = [r["elapsed_seconds"] for r in rows
                if r["replay_status"] == "ok" and r["phase"] in ("timed", "single")]
    median = statistics.median(measured) if measured else ""
    for row in rows or [{"phase": "none", "replay_status": "none"}]:
        append_csv(out_path, FIELDS, {**base, **row, "status": status, "reason": reason,
                                      "median_seconds": median, "repeats": len(measured),
                                      "parse_seconds": parse_s})
    return {"status": status, "median": median, "repeats": len(measured), "reason": reason}


def a_million_decision(spec: dict, rows: list[dict]) -> str | None:
    """Reason string if A must NOT run this 1,000,000-event stream (README rule 3), else None."""
    ref = run_result(rows, "A", spec["scenario"], 42, 100000, 1000)
    if ref is None:
        return "A at 100,000 events has no recorded result (run the 100,000-event streams first)"
    if ref["status"] != "ok" or ref["median_seconds"] == "":
        return f"A at 100,000 events on {spec['scenario']} did not finish (status {ref['status']})"
    median = float(ref["median_seconds"])
    if median >= common.A_MILLION_THRESHOLD:
        return (f"A at 100,000 events on {spec['scenario']} took {median:.1f} s "
                f"(>= {common.A_MILLION_THRESHOLD} s)")
    return None


def canary(block: str, point: str, args) -> None:
    """B on mixed 100,000 events (seed 42), 5 repeats, same rules as every run; rows go to
    results/canary_raw.csv. Same median before and after every block = the machine was stable."""
    out = run_one("B", CANARY_SPEC, args.limit_seconds, args.slow_first_seconds, args.repeats,
                  CANARY_RAW, {"block": block, "canary_point": point})
    power = common.power_state()
    print(f"    canary {point:6s} {block}: median {float(out['median']):.4f} s "
          f"(power {power['power_source']}, low power {power['low_power_mode']})", flush=True)


def planned_runs(args) -> list[tuple[str, dict]]:
    runs = []
    for spec in common.all_streams():
        if spec["events"] > args.max_events or spec["scenario"] not in args.scenarios:
            continue
        if spec["levels"] != 1000 and not args.concentration:
            continue
        runs += [(v, spec) for v in args.versions]
    return runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--versions", nargs="+", default=["A", "B"], choices=sorted(VERSIONS))
    parser.add_argument("--max-events", type=int, default=10**9)
    parser.add_argument("--scenarios", nargs="+", default=list(common.SCENARIOS))
    parser.add_argument("--concentration", action="store_true",
                        help="also the buildup streams with 4 ... 4000 price levels")
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    parser.add_argument("--slow-first-seconds", type=float, default=common.SLOW_FIRST_SECONDS)
    parser.add_argument("--repeats", type=int, default=common.TIMED_REPEATS)
    args = parser.parse_args(argv)
    common.write_environment()
    runs = planned_runs(args)
    started = time.monotonic()
    block, pending = "", False       # block = all runs of one (events, scenario)
    for i, (version, spec) in enumerate(runs, start=1):
        this_block = f"{spec['scenario']}_{spec['events']}"
        if this_block != block:
            if pending and block:
                canary(block, "after", args)
            block, pending = this_block, False
        label = (f"[{i}/{len(runs)} {time.monotonic() - started:7.0f}s] {version} "
                 f"{spec['scenario']:12s} M={spec['events']:>8d} L={spec['levels']:>4d} s{spec['seed']}")
        rows = read_csv(TIME_RAW)
        if run_result(rows, version, spec["scenario"], spec["seed"], spec["events"],
                      spec["levels"]) is not None:
            print(label, "-> already recorded, skipped", flush=True)
            continue
        if version == "A" and spec["events"] == 1_000_000:
            reason = a_million_decision(spec, rows)
            if reason:
                append_csv(TIME_RAW, FIELDS, {
                    "start_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
                        timespec="seconds"), **common.power_state(), "block": block,
                    "version": "A", **{k: spec[k] for k in ("scenario", "seed", "events", "levels")},
                    "status": "not_run", "reason": reason, "phase": "none", "replay_status": "none",
                    "repeats": 0, "limit_seconds": args.limit_seconds})
                print(label, "-> not_run:", reason, flush=True)
                continue
        if not pending:
            canary(block, "before", args)
            pending = True
        print(label, "-> running", flush=True)
        out = run_one(version, spec, args.limit_seconds, args.slow_first_seconds, args.repeats)
        print(label, f"-> {out['status']}",
              (f"median {float(out['median']):.4f} s, repeats={out['repeats']}"
               if out["median"] != "" else out["reason"]), flush=True)
    if pending and block:
        canary(block, "after", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
