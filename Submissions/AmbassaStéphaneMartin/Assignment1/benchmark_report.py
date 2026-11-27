"""Build an audited replay dashboard from saved records; never run an engine."""
import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import statistics
import zlib

ROOT = Path(__file__).resolve().parent
PHASES = ("io", "timing", "latency", "memory", "diagnostics")
VERSIONS = ("baseline", "revised")
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
COUNTS = (1000, 10000, 100000)
SEEDS = (42, 43, 44)
METRICS = (
    "read_seconds", "decompress_seconds", "parse_seconds", "io_total_seconds",
    "initialization_seconds", "construction_seconds", "replay_seconds", "total_compute_seconds",
    "throughput_events_per_second", "latency_median_seconds", "latency_p95_seconds",
    "latency_p99_seconds", "latency_sample_count", "memory_peak_bytes", "memory_current_bytes",
    "memory_after_construction_bytes", "memory_before_final_cancel_bytes",
    "memory_after_cancellation_bytes", "active_orders_peak", "occupied_prices_peak",
    "retained_queue_entries_peak", "inactive_queue_entries_peak", "heap_entries_peak",
    "active_orders_final", "occupied_prices_final", "retained_queue_entries_final",
    "inactive_queue_entries_final", "heap_entries_final", "retained_queue_entries_before_final_cancel",
    "inactive_entries_before_final_cancel", "heap_entries_before_final_cancel",
    "active_orders_before_final_cancel", "fill_count", "price_levels_visited",
    "unfilled_qty_units", "cancelled_qty_units", "rejected_event_count", "processed_events",
    "compressed_bytes", "decoded_bytes",
)


def saved_path(path):
    text = str(path).replace("\\", "/")
    for anchor in ("/data/", "/results/"):
        if anchor in text:
            return ROOT / anchor.strip("/") / text.rsplit(anchor, 1)[1]
    value = Path(text)
    return value if value.is_absolute() else ROOT / value


def read_json(path):
    return json.loads(saved_path(path).read_text(encoding="utf-8"))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def protocol(manifest):
    """Compare recorded execution conditions; Git revisions alone are not code identity."""
    env = manifest["environment"]
    return dict(source={k: env["source_sha256"].get(k) for k in
                        ("order_book.py", "benchmark.py", "generate_orders.py")},
                python=env["python"], implementation=env["implementation"],
                executable=env["python_executable"], dependencies=env["dependencies"],
                machine=env["machine"], clock=env["clock"],
                worker_environment=env["worker_environment"],
                garbage_collection=env["garbage_collection"],
                limits=manifest["limits"], boundaries=manifest["boundaries"],
                repetitions=manifest["repetitions"])


def classify(summary, raw, elapsed):
    """Accept a full group or an explicitly documented limit; never fill missing values."""
    expected = 5 if summary["phase"] in ("io", "timing", "memory") else 1
    assert summary["expected_repetitions"] == expected
    assert len(raw) == expected
    assert [r["repetition"] for r in raw] == list(range(1, expected + 1))
    completed = sum(r["status"] == "complete" for r in raw)
    assert summary["completed_repetitions"] == completed
    finished = completed == expected
    assert summary["status"] == ("complete" if finished else "incomplete")
    for field in METRICS:
        values = [r.get(field) for r in raw if r.get(field) is not None]
        expected_value = statistics.median(values) if finished and len(values) == expected else None
        assert summary.get(field) == expected_value, (field, summary.get(field), expected_value)
    unfinished = [r for r in raw if r["status"] != "complete"]
    for row in unfinished:
        assert all(row.get(field) is None for field in METRICS)
        assert row["error"]
    if finished:
        return "completed"
    if any(r["status"] == "error" for r in unfinished):
        return "failed"
    if all(r["status"] == "not_run" for r in unfinished):
        return "unattempted"
    assert all(r["status"] in ("stopped", "not_run") for r in unfinished)
    assert any("wall limit" in r["error"] for r in unfinished)
    assert elapsed is not None and elapsed >= 0, "Stopped record has no elapsed wall evidence"
    return "stopped"


def compare_pair(left, right, diag_left=None, diag_right=None):
    """Only completed, protocol-identical, validated timing groups yield a speedup."""
    if left is None or right is None:
        return dict(speedup=None, status="unavailable", reason="measurement missing")
    if any(r["summary"].get("phase") != "timing" for r in (left, right)):
        return dict(speedup=None, status="unavailable", reason="primary timing groups required")
    if any(left["summary"].get(f) != right["summary"].get(f) for f in
           ("experiment", "scenario", "requested_count", "event_count", "source_event_count",
            "construction_event_count", "seed", "levels", "sale_percent")):
        return dict(speedup=None, status="incomparable", reason="case identity differs")
    if left["state"] != "completed" or right["state"] != "completed":
        return dict(speedup=None, status="unavailable", reason="completed groups required")
    if left["workload_sha256"] != right["workload_sha256"]:
        return dict(speedup=None, status="incomparable", reason="workload checksum differs")
    if left["protocol"] != right["protocol"]:
        return dict(speedup=None, status="incomparable", reason="recorded protocol or environment differs")
    if not diag_left or not diag_right or any(d["state"] != "completed" for d in (diag_left, diag_right)):
        return dict(speedup=None, status="unavailable", reason="completed diagnostic pair required")
    for timing, diag in ((left, diag_left), (right, diag_right)):
        if timing["protocol"] != diag["protocol"] or timing["workload_sha256"] != diag["workload_sha256"]:
            return dict(speedup=None, status="incomparable", reason="diagnostic provenance differs")
    if any(not d["summary"].get("result_digest") or not d["summary"].get("snapshot_digest") for d in (diag_left, diag_right)):
        return dict(speedup=None, status="unavailable", reason="diagnostic digests missing")
    fields = ("result_digest", "snapshot_digest", "fill_count", "price_levels_visited", "unfilled_qty_units",
              "cancelled_qty_units", "rejected_event_count", "active_orders_peak",
              "occupied_prices_peak", "active_orders_final", "occupied_prices_final")
    if any(diag_left["summary"].get(f) != diag_right["summary"].get(f) for f in fields):
        return dict(speedup=None, status="mismatch", reason="diagnostic results differ")
    left_time, right_time = left["summary"]["replay_seconds"], right["summary"]["replay_seconds"]
    assert left_time > 0 and right_time > 0
    return dict(speedup=left_time / right_time, status="comparable",
                reason="same inputs, code, Python, machine, limits and protocol; diagnostics match")


def load_catalog(results):
    candidates = defaultdict(list)
    invalid = []
    runs = []
    dataset_cache = {}
    for path in sorted(results.glob("*/manifest.json")):
        manifest = read_json(path)
        raw_path, summary_path = path.parent / "raw.jsonl", path.parent / "summaries.jsonl"
        if not raw_path.exists() or not summary_path.exists():
            invalid.append(dict(path=str(path), reason="missing exported records"))
            continue
        raw_groups = defaultdict(list)
        for row in read_rows(raw_path):
            raw_groups[(row["case_id"], row["version"], row["phase"])].append(row)
        wall_path = path.parent / "command_wall_time.json"
        wall = read_json(wall_path) if wall_path.exists() else None
        observations = {}
        for point in wall.get("progress", []) if wall else []:
            if "case_id" in point:
                observations[(point["case_id"], point["version"], point["phase"])] = point["interval_since_previous_progress_seconds"]
            else:
                match = re.match(r"^\[\d+/\d+\]\s+(\S+)\s+(shared|baseline|revised)\s+(\w+):", point["line"])
                if match:
                    case_id, version, phase = match.groups()
                    observations[(case_id, None if version == "shared" else version, phase)] = point["interval_seconds"]
        run_record = dict(path=str(path.parent.relative_to(ROOT)), status=manifest["status"],
                          command_wall_seconds=wall["total_command_wall_seconds"] if wall else None,
                          code_version=manifest["environment"]["git_head"], versions=manifest["versions"])
        runs.append(run_record)
        cases = {c["case_id"]: c for c in manifest["workloads"]}
        for summary in read_rows(summary_path):
            if summary["experiment"] != "replay":
                continue
            key = (summary["case_id"], summary["version"], summary["phase"])
            group = raw_groups[key]
            case = cases[summary["case_id"]]
            source = saved_path(case["source"]["path"])
            try:
                if source not in dataset_cache:
                    if len(dataset_cache) >= 2:
                        dataset_cache.pop(next(iter(dataset_cache)))
                    data_hash = sha(source)
                    decoded = zlib.decompress(source.read_bytes(), wbits=31) if source.suffix == ".gz" else source.read_bytes()
                    events = [json.loads(line) for line in decoded.decode("utf-8").splitlines() if line.strip()]
                    previous = 0
                    identifiers = set()
                    for event in events:
                        assert type(event["seq"]) is int and event["seq"] > previous
                        previous = event["seq"]
                        assert isinstance(event["event_id"], str) and event["event_id"].strip()
                        assert event["event_id"] not in identifiers
                        identifiers.add(event["event_id"])
                        for field in ("price_ticks", "qty_units"):
                            if field in event:
                                assert type(event[field]) is int and event[field] > 0
                    dataset_cache[source] = dict(sha256=data_hash, events=events,
                                                compressed_bytes=source.stat().st_size, decoded_bytes=len(decoded))
                dataset = dataset_cache[source]
                assert dataset["sha256"] == case["source"]["sha256"] == summary["workload_sha256"]
                assert len(dataset["events"]) == case["source_event_count"]
                assert case["event_count"] == len(dataset["events"])
                state = classify(summary, group, observations.get(key))
                for row in group:
                    if row["status"] != "complete":
                        continue
                    for f in METRICS:
                        value = row.get(f)
                        assert value is None or (type(value) in (int, float) and math.isfinite(value)), f
                    phase = row["phase"]
                    assert row.get("price_levels_visited") is None
                    if phase == "timing":
                        assert row["processed_events"] == case["event_count"]
                        assert row["construction_seconds"] is None
                        assert row["replay_seconds"] > 0
                        assert close(row["total_compute_seconds"], row["initialization_seconds"] + row["replay_seconds"])
                        assert close(row["throughput_events_per_second"], case["event_count"] / row["replay_seconds"])
                    elif phase == "io":
                        assert close(row["io_total_seconds"], sum(row[f] or 0 for f in
                                     ("read_seconds", "decompress_seconds", "parse_seconds")))
                        for f in ("compressed_bytes", "decoded_bytes"):
                            assert row[f] == dataset[f]
                    elif phase == "latency":
                        samples = read_json(row["latency_samples_path"])["samples"]
                        assert len(samples) == row["latency_sample_count"] == case["event_count"]
                        values = []
                        for sample, event in zip(samples, dataset["events"]):
                            assert (sample["seq"], sample["event_id"]) == (event["seq"], event["event_id"])
                            assert math.isfinite(sample["seconds"]) and sample["seconds"] >= 0
                            values.append(sample["seconds"])
                        values.sort()
                        assert row["latency_median_seconds"] == statistics.median(values)
                        assert row["latency_p95_seconds"] == values[math.ceil(.95 * len(values)) - 1]
                        assert row["latency_p99_seconds"] == values[math.ceil(.99 * len(values)) - 1]
                    elif phase == "memory":
                        assert row["memory_peak_bytes"] >= row["memory_current_bytes"] >= 0
                        assert row["memory_peak_bytes"] >= row["memory_after_construction_bytes"] >= 0
                    else:
                        assert row["processed_events"] == case["event_count"]
                        assert row["rejected_event_count"] == 0, "unexpected rejected events"
                        assert isinstance(row["result_digest"], str) and len(row["result_digest"]) == 64
                        assert isinstance(row["snapshot_digest"], str) and len(row["snapshot_digest"]) == 64
                        assert 0 <= row["active_orders_final"] <= row["active_orders_peak"]
                        assert 0 <= row["occupied_prices_final"] <= row["occupied_prices_peak"]
                record = dict(state=state, summary=summary, raw=group,
                    workload_sha256=dataset["sha256"], protocol=protocol(manifest),
                    manifest=str(path.relative_to(ROOT)),
                    path=str(summary_path.relative_to(ROOT)), finished_utc=manifest.get("finished_utc", ""),
                    elapsed_wall_seconds=observations.get(key),
                    elapsed_boundary="stdout completion interval including parent overhead; first includes preparation",
                    command_wall_seconds=wall["total_command_wall_seconds"] if wall else None)
                versions = manifest["versions"] if summary["version"] is None else [summary["version"]]
                for version in versions:
                    case_key = (summary["event_count"], summary["seed"], summary["scenario"], version, summary["phase"])
                    candidates[case_key].append(record)
            except (AssertionError, OSError, ValueError, KeyError) as error:
                invalid.append(dict(path=str(summary_path.relative_to(ROOT)), key=list(key),
                                    reason=f"{type(error).__name__}: {error}"))
        for job_path in (path.parent / "workers").glob("*.job.json"):
            job = read_json(job_path)
            checkpoint_path = saved_path(job["checkpoint"])
            completed = [r for r in raw_groups[(job["case"]["case_id"], job["version"], job["phase"])]
                         if r["status"] == "complete"]
            checkpoint_rows = read_json(checkpoint_path)["rows"] if checkpoint_path.exists() else []
            if checkpoint_rows != completed:
                invalid.append(dict(path=str(job_path), reason="checkpoint/export disagreement"))
    rank = {"completed": 0, "stopped": 1, "unattempted": 2, "failed": 3}
    selected = {}
    for key, values in candidates.items():
        # A valid completion wins over a stop; newest source is chosen within a status.
        values.sort(key=lambda v: v["finished_utc"], reverse=True)
        values.sort(key=lambda v: rank[v["state"]])
        selected[key] = values[0]
    return selected, candidates, invalid, runs


def make_index(selected, invalid, runs):
    records = []
    for count in COUNTS:
        for seed in SEEDS:
            for scenario in SCENARIOS:
                view = dict(event_count=count, seed=seed, scenario=scenario, phases={})
                for phase in PHASES:
                    view["phases"][phase] = {
                        version: selected.get((count, seed, scenario, version, phase))
                        for version in VERSIONS}
                view["comparison"] = compare_pair(
                    view["phases"]["timing"]["baseline"], view["phases"]["timing"]["revised"],
                    view["phases"]["diagnostics"]["baseline"], view["phases"]["diagnostics"]["revised"])
                records.append(view)
    return dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                generator_sha256=sha(__file__), records=records, invalid_records=invalid,
                runs=runs, units=dict(price_ticks="USD cents per BTC", qty_units="10^-8 BTC",
                                     engine_timing="seconds", memory="incremental traced bytes"))


def verify_preservation(plan):
    protected = plan["preservation"]
    paths = json.loads(zlib.decompress(base64.b64decode(protected["paths_zlib_base64"])))
    hashes = {name: sha(ROOT / name) for name in paths}
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=False).encode("utf-8")).hexdigest()
    assert fingerprint == protected["tree_sha256"], "A pre-existing protected file changed"
    for name, expected in protected["source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    return dict(files=len(paths), tree_sha256=fingerprint, source_sha256=protected["source_sha256"])


def coverage(index, count):
    result = []
    for case in index["records"]:
        if case["event_count"] != count:
            continue
        for version in VERSIONS:
            phases = {p: case["phases"][p][version] for p in PHASES}
            states = [r["state"] if r else "missing" for p, r in phases.items() if p != "io"]
            status = ("completed" if all(s == "completed" for s in states) else
                      "failed" if "failed" in states else "missing" if "missing" in states else
                      "unattempted" if "unattempted" in states else "stopped")
            result.append(dict(seed=case["seed"], scenario=case["scenario"], version=version,
                               state=status, phase_states={p: r["state"] if r else "missing"
                                                          for p, r in phases.items()}))
    return result


def report(index, group, preserved, execution):
    large = [r for r in index["records"] if r["event_count"] == 100000]
    phase_jobs = []
    for case in large:
        for phase in PHASES:
            r = case["phases"][phase]["baseline"]
            if not r:
                continue
            if Path(r["manifest"]).parent.name in {o["name"] for o in execution["outcomes"]}:
                phase_jobs.append(dict(seed=case["seed"], scenario=case["scenario"], phase=phase,
                    state=r["state"], completed=r["summary"]["completed_repetitions"],
                    expected=r["summary"]["expected_repetitions"],
                    elapsed_wall_seconds=r["elapsed_wall_seconds"],
                    reason=r["summary"].get("error"), source=r["manifest"]))
    counts = Counter(j["state"] for j in phase_jobs)
    for state in ("completed", "stopped", "unattempted", "failed"):
        counts.setdefault(state, 0)
    states = coverage(index, 100000)
    aggregate = dict(status="audited", preservation=preserved,
        total_command_wall_seconds=execution["total_command_wall_seconds"],
        added_commands=len(execution["outcomes"]), added_phase_jobs=phase_jobs,
        phase_job_counts=dict(counts), coverage=states,
        comparable_completed_pairs=[dict(seed=c["seed"], scenario=c["scenario"], **c["comparison"])
                                    for c in large if c["comparison"]["status"] == "comparable"],
        invalid_records=index["invalid_records"],
        limitations=["A worker cap covers loading, warm-up and repetitions, not one replay.",
                     "Stopped or missing records never contribute a median or speedup.",
                     "Recorded machine/Python/protocol fingerprints match for reused comparisons; background load was not controlled.",
                     "Revised seeds 43 and 44 are outside this Baseline-only scope and remain missing."])
    write_json(group / "audit.json", aggregate)
    lines = [
        "# Baseline 100,000-event completion",
        "",
        "The starting audit found no Baseline measurements at this size for any required seed.",
        "Revised seed 42 already had five valid completed workloads; its saved audit passed and these results were reused.",
        "Revised seeds 43 and 44 have no saved 100,000-event runs and remain explicitly missing.",
        "The three documented Baseline/sweep memory stops at 10,000 events remain unchanged.",
        "",
        "No dashboard previously existed in this checkout. dashboard.html and this report are generated from validated saved records.",
        "The original implementations, runner, generator and test expectations remain unchanged.",
        f"All {preserved['files']} protected pre-existing files passed SHA-256 preservation checks.",
        "",
        "## Protocol and limits",
        "",
        "The original 89-test correctness command passed before measurements. Existing tests were not edited.",
        "Final validation passed 99 tests, including ten new reporting/comparability regressions; see report_tests.txt.",
        "All new commands use the unchanged benchmark.py runner with 100000 events, one seed/scenario, Baseline only, and 1000 configured levels.",
        "The existing warm-up, five repetitions, fresh books and separate I/O, timing, latency, memory and diagnostic processes are preserved.",
        "Limits are unchanged: 60 seconds per worker; 900 seconds per command's measurement campaign; 128 MiB input payload and 512 MiB traced allocations.",
        "Preparation is outside the measurement campaign deadline, and memory is measured separately with tracemalloc.",
        "The traced-allocation cap is not an OS RSS cap; loading and warm-up are outside tracing, and the allocation cap is checked between traced events.",
        "Each scenario runs in its own command so the campaign deadline cannot starve later scenarios. Worker conditions match the saved Revised protocol.",
        "Command wall clocks include preparation and every phase. Phase elapsed values are observed stdout completion intervals including parent/checkpoint work; the first also includes preparation.",
        "The worker time limit is never substituted for replay seconds. Null is retained when no complete repetition group exists.",
        "",
        "## Actual added outcomes",
        "",
        f"{len(execution['outcomes'])} Baseline commands were attempted sequentially.",
        f"Sum of command wall times: {execution['total_command_wall_seconds']:.3f} seconds.",
        "",
        "| Seed | Scenario | Command outcome | Command wall, s |",
        "| ---: | --- | --- | ---: |",
    ]
    for outcome in execution["outcomes"]:
        lines.append(f"| {outcome['seed']} | {outcome['scenario']} | {outcome['status']} | "
                     f"{outcome['total_command_wall_seconds']:.3f} |")
    lines += ["", "Phase-job totals: " + ", ".join(f"{k}={v}" for k,v in sorted(counts.items())) + ".",
              "", "| Seed | Scenario | Phase | Outcome | Repetitions | Observed elapsed, s | Reason |",
              "| ---: | --- | --- | --- | ---: | ---: | --- |"]
    for job in phase_jobs:
        elapsed = "unavailable" if job["elapsed_wall_seconds"] is None else f"{job['elapsed_wall_seconds']:.3f}"
        lines.append(f"| {job['seed']} | {job['scenario']} | {job['phase']} | {job['state']} | "
                     f"{job['completed']}/{job['expected']} | {elapsed} | {job['reason'] or ''} |")
    lines += ["", "Completed raw repetitions remain in their original run folders. Properly documented stops count as attempted coverage, not completed evidence.",
              "", "## Comparable results and remaining gaps", "",
              "| Seed | Scenario | Baseline timing | Revised timing | Speedup B/R | Comparison |",
              "| ---: | --- | --- | --- | ---: | --- |"]
    for case in large:
        cells = []
        for version in VERSIONS:
            r = case["phases"]["timing"][version]
            cells.append("missing" if r is None else f"{r['summary']['replay_seconds']:.9f} s"
                         if r["state"] == "completed" else
                         f"{r['state']} ({r['summary']['completed_repetitions']}/{r['summary']['expected_repetitions']})")
        comp = case["comparison"]
        ratio = f"{comp['speedup']:.3f}" if comp["speedup"] is not None else "unavailable"
        lines.append(f"| {case['seed']} | {case['scenario']} | {cells[0]} | {cells[1]} | {ratio} | {comp['reason']} |")
    lines += [
        "",
        "A speedup requires identical event count/seed/scenario and workload SHA-256; matching engine/runner/generator hashes; Python, dependencies, machine, clock, GC and limits; complete timing groups; and a complete matching diagnostic pair.",
        "Git revision labels alone are not compared: subsequent data/report commits do not change engine code. Reused Revised source and environment fingerprints are checked directly.",
        "No Baseline result from another event count supplies a large-case speedup. Physical queue/heap storage may differ; common logical diagnostics must agree.",
        "Existing valid completions and documented stops were preserved instead of rerun. Dataset settings and checksums are in every manifest and sidecar.",
        "",
        "## Reproduce",
        "",
        "The exact executed commands, timestamps, limits and elapsed times are in each new command_wall_time.json and command_output.txt; plan.json identifies the requested missing cases.",
        "Use new output directories for new measurements. The aggregate execution.json records every actual outcome.",
        "",
        "~~~console",
        "python -B benchmark_report.py",
        "python -B -m unittest -v test_order_book test_price_heaps test_lazy_cancellation test_benchmark test_benchmark_report",
        "~~~",
        "",
        "Open dashboard.html locally. It embeds the audited index, works without a server, and filters counts, seeds, scenarios and phases.",
        "index.json preserves source paths, raw repetitions, summary values, environment/protocol fingerprints, states and reasons.",
        "Remaining limitations are stopped phase groups without complete estimates, missing Revised seeds 43/44, and uncontrolled background machine load.",
        "No implementation, prior result, fixture or existing expected result was changed. Commits and pushes remain under user control.",
    ]
    (group / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return aggregate


def dashboard(index, destination):
    data = json.dumps(index, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    html = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Order book benchmarks</title>
<style>
:root{font-family:Segoe UI,Arial,sans-serif;color:#152638;background:#f4f6f8;font-size:15px}
*{box-sizing:border-box}body{margin:0}header{background:#142d42;color:#fff;padding:30px max(24px,5vw)}
header small{letter-spacing:.12em;text-transform:uppercase;color:#a9ccdf}h1{margin:9px 0;font-weight:650;font-size:32px}
header p{color:#c7d8e3;margin:0;max-width:900px;line-height:1.6}main{max-width:1500px;margin:auto;padding:24px}
.filters{display:flex;gap:18px;flex-wrap:wrap;background:white;border:1px solid #dce3e9;border-radius:10px;padding:18px}
label{font-size:12px;font-weight:650;display:grid;gap:7px;color:#506273}select{font:inherit;font-size:14px;padding:9px 30px 9px 10px;border:1px solid #bac8d3;border-radius:5px;background:white;color:#152638}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}.card{background:white;border:1px solid #dce3e9;border-radius:9px;padding:17px}.card b{display:block;font-size:28px;margin-bottom:6px}.card span{font-size:12px;color:#5c6e7d}
.notice{padding:14px 17px;background:#eaf0f5;border-left:3px solid #547b98;line-height:1.6;margin:15px 0;font-size:13px}
.table-wrap{overflow:auto;background:white;border:1px solid #dce3e9;border-radius:9px}table{width:100%;border-collapse:collapse;min-width:980px}th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#4d6273;background:#edf2f6;padding:15px 13px;text-align:left}td{padding:15px 13px;border-top:1px solid #e5eaf0;vertical-align:top;font-size:13px}
.badge{display:inline-block;border-radius:20px;padding:4px 9px;font-size:11px;font-weight:650;background:#e8edf1;color:#576876}.completed{background:#dff1e8;color:#18583c}.stopped{background:#fff0ce;color:#805800}.failed,.invalid{background:#ffe3e1;color:#8d312b}.metric{font-size:19px;font-variant-numeric:tabular-nums;display:block;margin-top:8px}.sub{display:block;color:#677b8b;font-size:11px;margin-top:5px;line-height:1.5;max-width:310px}details{margin-top:8px;font-size:11px}pre{max-width:340px;max-height:300px;overflow:auto;white-space:pre-wrap;background:#f5f7f9;padding:9px}a{color:#176395}footer{font-size:12px;color:#617586;margin:18px 0;line-height:1.7}
@media(max-width:750px){.cards{grid-template-columns:repeat(2,1fr)}header{padding:24px}h1{font-size:27px}main{padding:14px}}
</style></head><body>
<header><small>Assignment 1 / Saved replay measurements</small><h1>Order book benchmarks</h1>
<p>Baseline and Revised results, documented worker limits, and remaining gaps. Missing values stay missing; only comparable completed timing groups produce a speedup.</p></header>
<main><div class="filters">
<label>Event count<select id="count"><option value="100000">100,000</option><option value="10000">10,000</option><option value="1000">1,000</option><option value="">All counts</option></select></label>
<label>Seed<select id="seed"><option value="">All seeds</option><option>42</option><option>43</option><option>44</option></select></label>
<label>Scenario<select id="scenario"><option value="">All scenarios</option><option>buildup</option><option>crowded</option><option>mixed</option><option>sweep</option><option>cancel_churn</option></select></label>
<label>Measurement phase<select id="phase"><option value="timing">Engine replay</option><option value="latency">Event latency P95</option><option value="memory">Traced memory peak</option><option value="diagnostics">Active-order peak</option><option value="io">File I/O total</option></select></label>
</div><div class="cards"><div class="card"><b id="complete">0</b><span>Completed groups in view</span></div><div class="card"><b id="stopped">0</b><span>Documented stopped groups</span></div><div class="card"><b id="missing">0</b><span>Missing groups</span></div><div class="card"><b id="pairs">0</b><span>Comparable timing pairs</span></div></div>
<div class="notice" id="note"></div>
<div class="table-wrap"><table><thead><tr><th>Scenario</th><th>Seed / events</th><th>Baseline</th><th>Revised</th><th>Timing speedup B/R</th></tr></thead><tbody id="body"></tbody></table></div>
<footer id="footer"></footer></main>
<script id="data" type="application/json">__BENCHMARK_DATA__</script>
<script>
"use strict";
const data=JSON.parse(document.getElementById("data").textContent);
const el=id=>document.getElementById(id);
const formats={
timing:["replay_seconds",1000,"ms"],latency:["latency_p95_seconds",1000000,"us P95"],
memory:["memory_peak_bytes",1/1048576,"MiB traced"],diagnostics:["active_orders_peak",1,"active orders"],
io:["io_total_seconds",1000,"ms I/O"]};
function element(tag,text,klass){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(klass)e.className=klass;return e;}
function cellRecord(record,phase){
const cell=element("td");const state=record?record.state:"missing";
cell.append(element("span",state,"badge "+state));
if(record){
const s=record.summary;const spec=formats[phase];const value=s[spec[0]];
cell.append(element("strong",state==="completed"&&value!==null&&value!==undefined
?(value*spec[1]).toLocaleString(undefined,{maximumFractionDigits:3})+" "+spec[2]:"unavailable","metric"));
cell.append(element("span",s.completed_repetitions+"/"+s.expected_repetitions+" complete repetitions","sub"));
if(s.error)cell.append(element("span",s.error,"sub"));
if(record.elapsed_wall_seconds!==null)cell.append(element("span","Observed job completion interval: "+record.elapsed_wall_seconds.toFixed(2)+" s; includes overhead","sub"));
const details=element("details");details.append(element("summary","Source and recorded conditions"));
const link=element("a","Open saved summaries");link.href=record.path.replaceAll("\\","/");link.target="_blank";link.rel="noopener";
details.append(link);details.append(element("pre",JSON.stringify({manifest:record.manifest,workload_sha256:record.workload_sha256,protocol:record.protocol},null,2)));
cell.append(details);
}else cell.append(element("span","No saved measurement","sub"));
return cell;
}
function render(){
const phase=el("phase").value;
const selected=data.records.filter(r=>(!el("count").value||r.event_count===Number(el("count").value))&&(!el("seed").value||r.seed===Number(el("seed").value))&&(!el("scenario").value||r.scenario===el("scenario").value));
el("body").replaceChildren();let complete=0,stopped=0,missing=0,pairs=0;
for(const record of selected){
const row=element("tr");row.append(element("td",record.scenario));row.append(element("td",record.seed+" / "+record.event_count.toLocaleString()));
for(const version of ["baseline","revised"]){const r=record.phases[phase][version];const state=r?r.state:"missing";complete+=state==="completed";stopped+=state==="stopped";missing+=state==="missing";row.append(cellRecord(r,phase));}
const comparison=record.comparison;const c=element("td");
if(comparison.status==="comparable"){pairs++;c.append(element("strong",comparison.speedup.toFixed(3)+"x","metric"));}else c.append(element("span","unavailable","badge"));
c.append(element("span",comparison.reason,"sub"));row.append(c);el("body").append(row);
}
el("complete").textContent=complete;el("stopped").textContent=stopped;el("missing").textContent=missing;el("pairs").textContent=pairs;
el("note").textContent=phase==="timing"?"Replay timing excludes loading, warm-up, inspection, tracing and diagnostic counters. A 60-second worker timeout covers loading, warm-up and repetitions; it is not a replay duration.":"This is a separate "+phase+" phase. Speedups shown at right always refer to complete primary timing groups and matching diagnostics. Stopped and missing groups retain null summaries.";
el("footer").textContent="Generated "+data.generated_utc+". Strict integer market units are unchanged. Price ticks: USD cents per BTC; quantity units: 10^-8 BTC. Each missing or stopped measurement is explicit. Source, environment and workload checks guard every displayed timing speedup. Invalid records: "+data.invalid_records.length+".";
}
for(const id of ["count","seed","scenario","phase"])el(id).addEventListener("change",render);
render();
</script></body></html>"""
    destination.write_text(html.replace("__BENCHMARK_DATA__", data), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--group", type=Path, default=ROOT / "results" / "baseline_100000_completion")
    parser.add_argument("--dashboard", type=Path, default=ROOT / "dashboard.html")
    args = parser.parse_args(argv)
    selected, candidates, invalid, runs = load_catalog(args.results)
    index = make_index(selected, invalid, runs)
    execution = read_json(args.group / "execution.json")
    assert execution["status"] == "finished", "Measurement queue is not finished"
    plan = read_json(args.group / "plan.json")
    preserved = verify_preservation(plan)
    assert not invalid, f"Invalid saved records need review: {invalid}"
    assert len(execution["outcomes"]) == len(plan["jobs"])
    for job in plan["jobs"]:
        for phase in PHASES:
            record = selected.get((100000, job["seed"], job["scenario"], "baseline", phase))
            assert record is not None, (job, phase)
            assert record["state"] in ("completed", "stopped"), (job, phase, record["state"])
    write_json(args.group / "index.json", index)
    aggregate = report(index, args.group, preserved, execution)
    dashboard(index, args.dashboard)
    print(json.dumps(dict(audited_runs=len(runs), invalid_records=len(invalid),
        added_phase_jobs=len(aggregate["added_phase_jobs"]),
        outcomes=aggregate["phase_job_counts"], comparable_large_pairs=aggregate["comparable_completed_pairs"],
        dashboard=str(args.dashboard)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

