"""Serial reproducible benchmarks, raw repeats, deadlines and RSS supervision."""
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from generate_orders import events, write_stream, SCENARIOS

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_job(config, output, rows, finished):
    job_id = config["job_id"]
    if job_id in finished:
        return
    folder = output / "jobs"
    folder.mkdir(exist_ok=True)
    log = folder / (job_id + ".jsonl")
    error_log = folder / (job_id + ".stderr.log")
    (folder / (job_id + ".config.json")).write_text(json.dumps(config, indent=2)+"\n")
    start = time.perf_counter()
    stopped = None
    limit = 210 if config["mode"] == "liquidation" else 100 if config["mode"] == "timing" else 60
    with log.open("w") as out, error_log.open("w") as err:
        process = subprocess.Popen([sys.executable, "-B", "-u", str(ROOT / "benchmark_worker.py"),
                                    json.dumps(config)], cwd=ROOT, stdout=out, stderr=err)
        while process.poll() is None:
            try:
                process.wait(timeout=.25)
            except subprocess.TimeoutExpired:
                if time.perf_counter() - start > limit:
                    stopped = "stopped_worker_watchdog"
                if stopped:
                    process.kill()
                    process.wait()
                    break
    collected = []
    for line in log.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        collected.append(row)
    if process.returncode == 93:
        stopped = "stopped_rss_limit"
    if process.returncode != 0 and stopped is None:
        raise RuntimeError(f"worker {job_id} failed ({process.returncode}): {error_log.read_text()[-3000:]}")
    if stopped:
        base = {k:config.get(k) for k in ("job_id", "version", "scenario", "seed", "event_count", "levels")}
        if not any(r["phase"] == "worker" for r in collected):
            collected.append(dict(base, phase="worker", repeat=1, status=stopped, elapsed_seconds=None))
        planned = ([("replay", i) for i in range(1, config["repeats"]+1)]
                   if config["mode"] == "timing" else [(config["mode"], 1)])
        for phase, repeat in planned:
            if not any(r["phase"]==phase and r.get("repeat")==repeat for r in collected):
                collected.append(dict(base, phase=phase, repeat=repeat, status="not_run_"+stopped,
                                      elapsed_seconds=None, events_processed=None))
    for row in collected:
        row["phase_limit_seconds"] = config["phase_limit_seconds"]
        row["rss_limit_bytes"] = config["rss_limit_bytes"]
    with (output / "raw_results.jsonl").open("a") as stream:
        for row in collected:
            stream.write(json.dumps(row, separators=(",", ":"))+"\n")
    rows.extend(collected)
    finished.add(job_id)
    with (output / "finished_jobs.jsonl").open("a") as stream:
        stream.write(json.dumps(dict(job_id=job_id, status=stopped or "finished"))+"\n")
    states = sorted({r["status"] for r in collected})
    print(f"{job_id}: {','.join(states)}", flush=True)


def summarize(output, rows):
    groups = {}
    group_fields = ("version", "scenario", "seed", "event_count", "levels", "phase", "sale_percent", "event_type", "position")
    for row in rows:
        if row["phase"] in ("workload_metadata", "operation_counts", "worker"):
            continue
        key = tuple(row.get(k) for k in group_fields)
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, items in groups.items():
        good = [r for r in items if r["status"]=="completed"]
        times = [r["elapsed_seconds"] for r in good if r.get("elapsed_seconds") is not None]
        summary = dict(zip(group_fields, key))
        summary.update(completed_repeats=len(good), recorded_repeats=len(items),
                       statuses=sorted({r["status"] for r in items}),
                       median_elapsed_seconds=statistics.median(times) if times else None,
                       median_is_censored_subset=bool(good) and len(good)!=len(items))
        # Do not silently treat a subset median as a complete five-repeat result.
        for name in ("throughput_events_per_second", "traced_peak_bytes", "traced_current_bytes",
                     "median_seconds", "p95_seconds", "p99_seconds"):
            values = [r[name] for r in good if r.get(name) is not None]
            if values:
                summary[name] = statistics.median(values)
        for name in ("fill_count", "requested_qty_units", "makers_touched", "price_levels_visited",
                     "unfilled_qty_units", "active_order_peak", "price_level_peak"):
            values = [r[name] for r in good if r.get(name) is not None]
            if values:
                summary[name] = values[0]
        summaries.append(summary)
    (output / "summary.json").write_text(json.dumps(summaries, indent=2)+"\n")
    scalar_fields = sorted({k for row in rows for k,v in row.items() if not isinstance(v,(list,dict))})
    with (output / "raw_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=scalar_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:v for k,v in row.items() if not isinstance(v,(list,dict))})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "benchmark")
    parser.add_argument("--phase-limit", type=float, default=5.0)
    parser.add_argument("--rss-mib", type=int, default=512)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--skip-million", action="store_true")
    args = parser.parse_args()
    if args.phase_limit <= 0 or args.rss_mib <= 0:
        parser.error("limits must be positive")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = ROOT / "work" / "benchmark_inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    hashes = {str(p.relative_to(ROOT)):sha256(p) for p in sorted(ROOT.glob("*.py"))}
    hashes.update({str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT / "lob").glob("*.py"))})
    settings = dict(python=sys.version, executable=sys.executable, operating_system=platform.platform(),
        machine=platform.machine(), processor=platform.processor(), logical_cpus=os.cpu_count(),
        dependencies="Python standard library only", code_sha256=hashes,
        phase_limit_seconds=args.phase_limit, rss_limit_bytes=args.rss_mib * 1024**2,
        repeats=5, sizes=[100] if args.smoke else [1000,10000,100000],
        seeds=[42] if args.smoke else [42,43,44], scenarios=list(SCENARIOS), levels=1000,
        warmup="up to first 1000 events on separate discarded book",
        primary_scope="empty book creation + replay + minimal loop/fill counters; excludes parsing/inspection/reporting",
        total_scope="same-repeat parse_seconds + replay_seconds, not measured CLI wall time",
        memory_scope="tracemalloc after preload; includes engine, latest output, small probes; excludes input allocations",
        rss_scope="whole child ru_maxrss, polled by daemon every ~100ms; process exits at first observed excess; small symmetric sampler overhead",
        percentile="nearest rank ceil(p*n) for p95/p99; arithmetic middle median",
        serial_execution=True, smoke=args.smoke, million_attempt=not (args.smoke or args.skip_million),
        command=[sys.executable,"-B",str(ROOT/"benchmark.py"),*sys.argv[1:]])
    git = subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],capture_output=True,text=True,check=True)
    settings["git_base_commit"] = git.stdout.strip()
    settings["code_version_note"] = "uncommitted work identified by exact SHA-256 source map; no commit created"
    if sys.platform == "darwin":
        specs = subprocess.run(["/usr/sbin/sysctl","hw.model","hw.memsize","machdep.cpu.brand_string"],capture_output=True,text=True)
        settings["hardware_details"] = specs.stdout.strip()
    old_settings = output / "settings.json"
    if old_settings.exists():
        previous = json.loads(old_settings.read_text())
        for key in ("code_sha256","phase_limit_seconds","rss_limit_bytes","sizes","seeds","smoke","million_attempt"):
            if settings[key] != previous[key]:
                raise RuntimeError(f"refusing to resume incompatible results: {key}")
    else:
        old_settings.write_text(json.dumps(settings, indent=2)+"\n")
    rows = [json.loads(s) for s in (output/"raw_results.jsonl").read_text().splitlines()] if (output/"raw_results.jsonl").exists() else []
    finished = {json.loads(s)["job_id"] for s in (output/"finished_jobs.jsonl").read_text().splitlines()} if (output/"finished_jobs.jsonl").exists() else set()
    manifest = []
    base = dict(repeats=5, phase_limit_seconds=args.phase_limit,
                rss_limit_bytes=args.rss_mib*1024**2, results_dir=str(output))
    for scenario, count, seed in itertools.product(SCENARIOS, settings["sizes"], settings["seeds"]):
        name = f"{scenario}_m{count}_s{seed}_p1000"
        path = inputs / (name+".jsonl.gz")
        if not path.exists():
            write_stream(path, events(scenario, count, seed, 1000))
        manifest.append(dict(file=str(path.relative_to(ROOT)), scenario=scenario,event_count=count,seed=seed,levels=1000,
                             sha256=sha256(path),compressed_bytes=path.stat().st_size,
                             command=f"python3 generate_orders.py --scenario {scenario} --events {count} --seed {seed} --levels 1000 --out {path.relative_to(ROOT)}"))
        config = dict(base,scenario=scenario,event_count=count,seed=seed,levels=1000,path=str(path))
        meta_id = name+"_metadata"
        run_job(dict(config,job_id=meta_id,version="shared",mode="metadata"),output,rows,finished)
        meta = next(r for r in rows if r["job_id"]==meta_id and r["phase"]=="workload_metadata")
        config["metadata"] = meta
        # Alternate version order across cases, while keeping all jobs serial.
        versions = ("A","B") if (seed+count)%2==0 else ("B","A")
        for mode in ("timing","latency","memory"):
            for version in versions:
                run_job(dict(config,job_id=f"{name}_{version}_{mode}",version=version,mode=mode),output,rows,finished)
        if count == settings["sizes"][0] and seed==42:
            for version in ("A","B"):
                run_job(dict(config,job_id=f"{name}_{version}_operations",version=version,mode="operations"),output,rows,finished)
        # Persist partial aggregates, so interrupted work is inspectable/resumable.
        summarize(output, rows)
        (output/"input_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    for count, levels, version in itertools.product([100] if args.smoke else [1000,10000,100000],(4,1000),("A","B")):
        name = f"liquidation_m{count}_s42_p{levels}_{version}"
        config = dict(base,job_id=name,version=version,mode="liquidation",scenario="liquidation",event_count=count,seed=42,levels=levels)
        run_job(config,output,rows,finished)
        summarize(output,rows)
    if settings["million_attempt"]:
        # Explicit larger-input attempt under identical preload/RSS/phase boundaries.
        path = inputs/"mixed_m1000000_s42_p1000.jsonl.gz"
        if not path.exists():
            write_stream(path,events("mixed",1000000,42,1000))
        manifest.append(dict(file=str(path.relative_to(ROOT)),scenario="mixed",event_count=1000000,seed=42,levels=1000,
                             sha256=sha256(path),compressed_bytes=path.stat().st_size,
                             command=f"python3 generate_orders.py --scenario mixed --events 1000000 --seed 42 --levels 1000 --out {path.relative_to(ROOT)}"))
        for version in ("A","B"):
            config=dict(base,job_id=f"mixed_m1000000_s42_p1000_{version}_timing",version=version,mode="timing",scenario="mixed",event_count=1000000,seed=42,levels=1000,path=str(path),metadata={})
            # Preloading is expected to hit the memory budget on this machine;
            # if it fits, calculate metadata in its own supervised job first.
            config["metadata"]={"final_digest":None,"active_order_peak":None,"price_level_peak":None}
            run_job(config,output,rows,finished)
        (output/"input_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    summarize(output,rows)
    print(f"Finished {len(finished)} jobs; raw rows={len(rows)}; results={output}",flush=True)


if __name__ == "__main__":
    main()
