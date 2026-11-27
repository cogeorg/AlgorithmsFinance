"""Isolated, resumable benchmark pipeline. Default: M=1000 smoke ONLY.

Long runs require --allow-long and committed source. --session NAME resumes the
same run folder without duplicate cells, provided the measured source is unchanged.
"""
import argparse
from collections import defaultdict
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys

from bench.catalog import MANIFEST, ROOT, SCENARIOS, load
from bench.core import VERSIONS
from bench.protocol import BASELINE_PROTOCOL, timing_plan
from bench.harness import append_rows, new_run_dir, run_with_timeout

PARTS = ("official", "million", "queue", "liquidation", "adversarial", "churn", "post_attack")
MODES = ("timing", "latency", "memory", "counts")
COMMON = ("case_id", "experiment", "workload", "size", "events", "replayed_events", "seed", "levels",
          "own", "percent", "version", "mode", "input_sha256", "requested_sell_qty_units", "status", "timing_protocol",
          "registration", "prefill_events", "driver_n")
EXTRA = {
    "timing": ("phase", "repeat", "seconds", "warmup", "repeats_requested", "reason", "limit_s", "limit_bytes"),
    "latency": ("event_type", "segment", "n", "p50_ns", "p95_ns", "p99_ns", "max_ns", "convention", "label"),
    "latency_histogram": ("event_type", "segment", "bin_lo_ns", "bin_hi_ns", "count"),
    "memory": ("measure", "processed", "current_bytes", "peak_bytes", "live_orders", "price_levels",
               "heap_entries", "stale_heap_prices", "includes"),
    "counts": ("phase", "counter", "value", "applicable"),
    "checks": ("sample_events", "comparison", "counters_on"),
    "stops": ("phase", "repeat", "reason", "observed", "limit_s", "limit_bytes", "seconds", "repeats_requested"),
    "result": ("phase", "repeats_requested"),
}


def fingerprint():
    files = sorted([*Path("01_code").rglob("*.py"), *Path("02_tests").glob("*.py"),
                    Path("requirements.txt"), Path("pytest.ini")])
    return hashlib.sha256("\n".join(p.as_posix()+":"+hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in files).encode()).hexdigest()


class NoCommittedCheckout(ValueError):
    """Git or a committed HEAD is unavailable; source cannot be commit-verified."""


def source_dirty():
    try:
        subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True, check=True)
        # An ignored scratch copy can inherit HEAD without containing tracked source.
        subprocess.run(["git", "ls-files", "--error-unmatch", "--", "01_code/bench/run_all.py"],
                       cwd=ROOT, capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise NoCommittedCheckout("no git checkout (source not commit-verified)") from exc
    cp = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "--", "."],
                        cwd=ROOT, capture_output=True, text=True, check=True)
    allowed = ("03_results/", "05_evidence/", "06_data/generated/", "00_docs/DATA_MANIFEST.json")
    scope = "Submissions/BuehlerLaurin/Assignment1/"
    paths = [line[3:].removeprefix(scope) for line in cp.stdout.splitlines()]
    return [p for p in paths if not p.startswith(allowed)]


def cases_for(part, catalog):
    selected = []
    for original in catalog["entries"]:
        if part == "smoke":
            if original["part"] == "post_attack":
                continue  # keep the original registered smoke separate
            if original["size"] != 1000 or original["seed"] != 42:
                continue
        elif original["part"] != part:
            continue
        case = dict(original)
        case["label"] = case["workload"] + (f"_levels{case['levels']}" if case["part"] == "queue" else "")
        if case["part"] == "liquidation":
            for percent in (10, 100, 200):
                selected.append({**case, "id": case["id"]+f"_p{percent}", "percent": percent,
                                 "label": case["label"]+f"_{percent}pct"})
        else:
            selected.append(case)
    # Official cancellation churn is also an explicit memory experiment. Reuse
    # the data, but give it an independent case id/experiment for the growth curves.
    if part in ("churn", "smoke"):
        for e in catalog["entries"]:
            if e["part"] not in ("official", "million") or e["workload"] != "cancel_churn":
                continue
            if part == "smoke" and (e["size"] != 1000 or e["seed"] != 42):
                continue
            selected.append({**e, "id": "churn_"+e["id"], "part": "churn",
                             "label": "cancel_churn_memory"})
    return selected


def mode_applies(case, mode):
    return mode in case.get("modes", ("memory",) if case["part"] == "churn" else MODES)


def ordered_requests(cases, versions, modes, *, interleave=False, offset=0):
    """Default ordering is preserved; rematch alternates the two timing versions."""
    requested = [(c,v,m) for c in cases for v in versions for m in modes if mode_applies(c,m)]
    if not interleave:
        return sorted(requested, key=lambda item:(item[0]['id'],item[1],MODES.index(item[2])))
    if versions != ['B3r','B3r_fast'] or modes != ['timing'] or offset < 0:
        raise ValueError('interleave requires B3r,B3r_fast, timing only and a nonnegative offset')
    rank = {key:i+offset for i,key in enumerate(sorted({c['id'] for c,v,m in requested}))}
    return sorted(requested, key=lambda item:(item[0]['id'],
        versions.index(item[1]) if rank[item[0]['id']] % 2 == 0 else 1-versions.index(item[1])))


def rows_from(path):
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(newline="", encoding="utf-8")))


def normalize(kind, row):
    return {key: row.get(key, "") for key in (*COMMON, *EXTRA[kind])}


def save_records(directory, records):
    grouped = defaultdict(list)
    for record in records:
        grouped[record["kind"]].append(normalize(record["kind"], record["row"]))
    for kind, rows in grouped.items():
        unique = ("case_id", "version", "phase", "repeat") if kind == "timing" else None
        append_rows(directory / f"{kind}.csv", rows, unique_by=unique)


def summarize(directory):
    groups = defaultdict(list)
    cells = {(r["case_id"], r["version"]): r for r in rows_from(directory/"cells.csv") if r["mode"] == "timing"}
    for row in rows_from(directory/"timing.csv"):
        groups[(row["case_id"], row["version"], row["phase"])].append(row)
    summaries = []
    for (case, version, phase), raw in groups.items():
        measured = [r for r in raw if r["status"] == "ok" and r["warmup"] == "False" and r["seconds"]]
        first = raw[0]
        requested = 1 if phase == "parse" else int(first.get("repeats_requested") or 5)
        cell = cells.get((case, version), {})
        complete = len(measured) == requested and (phase == "parse" or cell.get("status") == "ok")
        seconds = statistics.median(float(r["seconds"]) for r in measured) if complete else ""
        summaries.append({**{k: first.get(k, "") for k in COMMON if k not in ("status", "mode")},
                          "phase": phase, "median_s": seconds,
                          "statistic": "single_trial" if requested == 1 else "median",
                          "completed_repeats": len(measured), "repeats_requested": requested,
                          "status": "ok" if complete else cell.get("status", "partial"),
                          "throughput_events_s": float(first["replayed_events"])/seconds
                          if complete and phase == "replay" and seconds > 0 else ""})
    path = directory/"summary.csv"
    if summaries:
        # Derived summary is rewritten from immutable raw observations on resume.
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
            writer.writeheader(); writer.writerows(summaries)
    return summaries


def get_run(args):
    # Check provenance even when resuming: a saved pointer is not a checkout.
    try:
        dirty = source_dirty()
    except NoCommittedCheckout as exc:
        if args.part != "smoke":
            raise ValueError("official runs require committed source in a git checkout") from exc
        dirty = None
    if args.part != "smoke" and dirty:
        raise ValueError("official runs require committed source; changed paths: " + ", ".join(dirty))
    provenance = ("no git checkout (source not commit-verified)" if dirty is None else
                  "git checkout (source modified)" if dirty else "git checkout (source commit-verified)")
    print("SOURCE_PROVENANCE=" + provenance, flush=True)
    code = fingerprint()
    pointer = Path("scratch") / f"bench_session_{args.session}.json" if args.session else None
    if pointer and pointer.exists():
        data = json.loads(pointer.read_text(encoding="utf-8"))
        if data["source_sha256"] != code:
            raise ValueError("source changed since this session; choose a NEW --session name")
        if (data["limit_s"], data["limit_bytes"]) != (args.limit_s, args.limit_bytes):
            raise ValueError("limits changed since this session; choose a NEW --session name")
        return Path(data["run_dir"])
    directory = new_run_dir(tag="smoke" if args.part == "smoke" else args.session or "official")
    env_path = directory/"env.json"
    env = json.loads(env_path.read_text(encoding="utf-8"))
    env.update(source_sha256=code, source_dirty_paths=dirty,
               source_provenance=provenance, source_commit_verified=(dirty == []),
               gc_policy="enabled for every version",
               per_replay_limit_s=args.limit_s, traced_peak_limit_bytes=args.limit_bytes,
               baseline_protocol=BASELINE_PROTOCOL,
               baseline_deviation="A: single trial without warm-up at 100k/1M; warm-up + 5 at 1k/10k",
               selection="SPEC.md Phase 4a: robustness then 15-cell geometric mean; 5% simplicity tie")
    if getattr(args, 'interleave', False):
        env['interleaving'] = 'B3r/fast then fast/B3r by global case; timing only'
    env_path.write_text(json.dumps(env, indent=2), encoding="utf-8")
    (directory/"spec_snapshot.md").write_text(Path("SPEC.md").read_text(encoding="utf-8"), encoding="utf-8")
    if pointer:
        pointer.parent.mkdir(exist_ok=True)
        pointer.write_text(json.dumps({"run_dir": str(directory), "source_sha256": code,
                                      "limit_s": args.limit_s, "limit_bytes": args.limit_bytes}), encoding="utf-8")
    return directory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--part", choices=("smoke", *PARTS), default="smoke")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--allow-long", action="store_true")
    ap.add_argument("--baseline-protocol", choices=(BASELINE_PROTOCOL,), default=BASELINE_PROTOCOL)
    ap.add_argument("--plan-only", action="store_true", help="list coverage only; never construct a book")
    ap.add_argument('--interleave', action='store_true', help='alternate B3r/fast version order by timing case')
    ap.add_argument('--interleave-offset', type=int, default=0, help='number of preceding timing cases across parts')
    ap.add_argument("--max-size", type=int, choices=(1000, 10000, 100000, 1000000), default=1000000)
    ap.add_argument("--session")
    ap.add_argument("--versions", default=",".join(VERSIONS))
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--skip-after-stop", action="store_true",
                    help="record other modes as not_run after this version/input timing stops")
    ap.add_argument("--limit-s", type=float, default=600)
    ap.add_argument("--limit-bytes", type=int, default=4*1024**3)
    args = ap.parse_args()
    if args.part != "smoke" and not args.allow_long and not args.plan_only:
        ap.error("long engine runs require explicit --allow-long; Phase 4a permits smoke only")
    if args.session and not re.fullmatch(r"[A-Za-z0-9_-]+", args.session):
        ap.error("session must contain only letters/digits/underscore/hyphen")
    versions, modes = args.versions.split(","), args.modes.split(",")
    if not versions or set(versions)-set(VERSIONS) or not modes or set(modes)-set(MODES):
        ap.error("unknown/empty versions or modes")
    if args.limit_s <= 0 or args.limit_bytes <= 0:
        ap.error("limits must be positive")
    cases = cases_for(args.part, load(args.manifest))
    cases = [case for case in cases if case["size"] <= args.max_size]
    if not cases:
        ap.error("no data entries match part")
    try:
        requested = ordered_requests(cases, versions, modes, interleave=args.interleave, offset=args.interleave_offset)
    except ValueError as exc:
        ap.error(str(exc))
    if args.plan_only:
        plan = {"part": args.part, "cases": len(cases), "versions": versions,
                "modes": modes, "cells": len(requested), "sizes": sorted({c["size"] for c in cases}),
                "engine_executed": False}
        if args.interleave:
            plan['interleave_offset'] = args.interleave_offset
            plan['timing_cases'] = len(requested)//2
            plan['timed_sizes'] = sorted({c['size'] for c,v,m in requested})
            plan['execution_order'] = [dict(case_id=c['id'], version=v, mode=m,
                case_number=args.interleave_offset+i//2+1) for i,(c,v,m) in enumerate(requested)]
        print(json.dumps(plan))
        return 0
    directory = get_run(args)
    jobs_dir = directory/"jobs"; jobs_dir.mkdir(exist_ok=True)
    done = {(r["case_id"], r["version"], r["mode"]): r for r in rows_from(directory/"cells.csv")}
    errors = 0
    for number, (case, version, mode) in enumerate(requested, 1):
        key = case["id"], version, mode
        if key in done:
            continue
        ident = f"{case['id']}__{version}__{mode}"
        journal = directory/"cells"/(ident+".jsonl")
        timing = done.get((case["id"], version, "timing"), {})
        base = {"case_id": case["id"], "experiment": case["part"], "workload": case["label"],
                "size": case["size"], "events": case["events"], "seed": case["seed"],
                "levels": case["levels"], "own": case["own"], "percent": case.get("percent", ""),
                "input_sha256": case["sha256"], "version": version, "mode": mode,
                "registration": case.get("registration", "pre-registered Phase 4"),
                "prefill_events": case.get("prefill_events", 0), "driver_n": case.get("driver_n", ""),
                "timing_protocol": timing_plan(version, case["size"])[2]}
        if args.skip_after_stop and mode != "timing" and timing.get("status") == "stopped":
            cell = {**base, "status": "not_run", "wall_s": 0.0, "stopped_phase": "",
                    "limit_s": args.limit_s, "limit_bytes": args.limit_bytes,
                    "reason": "not_run_after_timing_stop (not a measured limit hit)"}
        else:
            job = {"case": case, "version": version, "mode": mode, "journal": str(journal),
                   "limit_s": args.limit_s, "limit_bytes": args.limit_bytes}
            job_path = jobs_dir/(ident+".json")
            job_path.write_text(json.dumps(job), encoding="utf-8")
            command = [sys.executable, "run.py", "bench.worker", str(job_path)]
            guarded = run_with_timeout(command, args.limit_s, phase_protocol=True)
            records = []
            if journal.exists():
                for line in journal.read_text(encoding="utf-8").splitlines():
                    try:
                        records.append(json.loads(line))
                    except ValueError:
                        pass  # an interrupted final journal write is not an observation
            stops = [r["row"] for r in records if r["kind"] == "stops"]
            reason = stops[-1].get("reason", "") if stops else ("phase_time_limit" if guarded["status"] == "stopped" else "")
            stop_phase = stops[-1].get("phase", "") if stops else guarded.get("stopped_phase", "")
            cell = {**base, "status": guarded["status"], "wall_s": guarded["wall_s"],
                    "stopped_phase": stop_phase, "limit_s": args.limit_s,
                    "limit_bytes": args.limit_bytes, "reason": reason}
            if guarded["status"] != "ok":
                if not stops:
                    stop = {**base, "status": guarded["status"], "phase": stop_phase,
                            "repeat": "", "seconds": "", "limit_s": args.limit_s,
                            "limit_bytes": args.limit_bytes, "reason": reason, "observed": "",
                            "repeats_requested": timing_plan(version, case["size"])[1] if mode == "timing" else 1}
                    records.append({"kind": "stops", "row": stop}); stops = [stop]
                if mode == "timing":
                    records.append({"kind": "timing", "row": {**stops[-1], "warmup": False}})
                if guarded["status"].startswith("error"):
                    errors += 1
            save_records(directory, records)
            (directory/"cells"/(ident+".log")).write_text(guarded["log_tail"], encoding="utf-8")
        append_rows(directory/"cells.csv", [cell], unique_by=("case_id", "version", "mode"))
        done[key] = cell
        summarize(directory)
        print(f"[{number}/{len(requested)}] {ident}: {cell['status']} ({cell['wall_s']:.3f}s)", flush=True)
    summaries = summarize(directory)
    statuses = Counter(done[(c["id"], v, m)]["status"] for c, v, m in requested)
    errors = sum(n for status, n in statuses.items() if status.startswith("error"))
    print(f"RUN_DIR={directory}")
    print(f"CELL_STATUS={dict(statuses)}")
    print(f"RESULT: {'FAIL' if errors else 'PASS'} ({len(requested)} requested cells; {len(summaries)} phase summaries; part={args.part})")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
