"""Summarize these four completed command attempts; never launch benchmarks."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

RUNS = [
    ("replay_1000_seed43_batch1", 1000, 43),
    ("replay_1000_seed44_batch1", 1000, 44),
    ("replay_10000_seed43_batch1", 10000, 43),
    ("replay_10000_seed44_batch1", 10000, 44),
]
ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

audits = []
walls = []
summary_rows = []
batch_reports = []
previous_end = None
for name, count, seed in RUNS:
    directory = ROOT / "results" / name
    audit = read(directory / "audit.json")
    wall = read(directory / "command_wall_time.json")
    manifest = read(directory / "manifest.json")
    assert audit["audit_status"] == "passed"
    assert audit["event_count"] == count and audit["seed"] == seed
    assert not read(directory / "continuation_check.json")["actual_errors"]
    assert not read(directory / "continuation_check.json")["diagnostic_mismatches"]
    start, end = map(datetime.fromisoformat, (wall["started_utc"], wall["finished_utc"]))
    assert previous_end is None or previous_end <= start
    previous_end = end
    assert audit["job_counts"]["failed"] == 0
    assert all(c["status"] != "failed" for c in audit["diagnostic_comparisons"])
    audits.append(audit)
    walls.append(wall)
    summary_rows.append(dict(directory=name, event_count=count, seed=seed,
        campaign_status=audit["campaign_status"],
        wall_seconds=wall["total_command_wall_seconds"], job_counts=audit["job_counts"],
        raw_states=audit["raw_record_states"], diagnostics=audit["diagnostic_comparisons"],
        generated_workloads=audit["generated_workloads_verified"],
        source_sha256=audit["source_sha256"]))
    lines = [
        f"# Replay batch: {count} events, seed {seed}",
        "",
        f"Campaign status: {audit['campaign_status']}. Audit: {audit['audit_status']}.",
        f"Total command wall time: {wall['total_command_wall_seconds']:.6f} seconds.",
        "The wall time includes process startup and workload preparation; engine clocks use the original boundaries.",
        f"Jobs: {audit['job_counts']['complete']} complete, {audit['job_counts']['stopped']} stopped, "
        f"{audit['job_counts']['unattempted']} unattempted, {audit['job_counts']['failed']} failed.",
        "Limits: 60 seconds per worker, 900 seconds per measurement campaign, 128 MiB input payload and 512 MiB traced allocations.",
        "Workload preparation is outside the measurement campaign deadline. Limits apply equally to both versions.",
        "The existing warm-up, five repetitions, fresh books, and separate I/O, timing, latency, memory and diagnostics phases were retained.",
        "",
        "## Reproduce",
        "",
        "Use a new output directory to preserve this saved run.",
        "",
        "~~~console",
        f"python -B benchmark.py run --counts {count} --seeds {seed} --scenarios buildup crowded mixed sweep cancel_churn --experiments replay --versions baseline revised --levels 1000 --out results/{name}_repeat --worker-seconds 60 --campaign-seconds 900 --label remaining-small-replay",
        f"python -B results/{name}/audit.py",
        "~~~",
        "",
        "## Timing and diagnostics",
        "",
        "Primary medians below use only complete five-repetition groups with matching diagnostic pairs.",
        "Throughput is event count divided by replay seconds; initialization and total compute remain separately saved in raw.jsonl and summaries.jsonl.",
        "",
        "| Scenario | Baseline replay, ms | Revised replay, ms | Baseline events/s | Revised events/s | B/R ratio | Diagnostic pair |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for scenario in audit["scenario_results"]:
        left = scenario["versions"]["baseline"]["timing"]
        right = scenario["versions"]["revised"]["timing"]
        comp = next(c for c in audit["diagnostic_comparisons"] if c["scenario"] == scenario["scenario"])
        if scenario["timing_comparable"]:
            cells = [f"{left['replay_seconds']*1000:.6f}", f"{right['replay_seconds']*1000:.6f}",
                     f"{left['throughput_events_per_second']:.1f}", f"{right['throughput_events_per_second']:.1f}",
                     f"{scenario['baseline_over_revised_replay_ratio']:.3f}"]
        else:
            cells = ["not compared"] * 5
        lines.append("| " + scenario["scenario"] + " | " + " | ".join(cells) + " | " + comp["status"] + " |")
    missing = [c for c in audit["diagnostic_comparisons"] if c["status"] == "missing"]
    failed = [c for c in audit["diagnostic_comparisons"] if c["status"] == "failed"]
    lines += ["", f"Missing diagnostic comparisons: {len(missing)}. Failed comparisons: {len(failed)}.",
        "", "## Memory completion and separate instrumentation", "",
        "| Scenario | Version | Memory repetitions | Peak-byte median | Current-byte median |",
        "| --- | --- | ---: | ---: | ---: |"]
    for scenario in audit["scenario_results"]:
        for version in ("baseline", "revised"):
            memory = scenario["versions"][version]["memory"]
            peak = str(memory["memory_peak_bytes"]) if memory["status"] == "complete" else "unavailable"
            current = str(memory["memory_current_bytes"]) if memory["status"] == "complete" else "unavailable"
            lines.append(f"| {scenario['scenario']} | {version} | {memory['completed_repetitions']}/5 | {peak} | {current} |")
    stopped = [j for j in audit["jobs"] if j["state"] != "complete"]
    lines += ["", "Incomplete jobs:", ""]
    if stopped:
        for job in stopped:
            lines.append(f"- {job['case_id']} / {job['version']} / {job['phase']}: {job['state']}; "
                         f"{job['completed_repetitions']}/{job['expected_repetitions']} complete. {job['error']}")
    else:
        lines.append("- None.")
    lines += ["",
        "Finished repetitions are preserved. Incomplete groups have null summary measurements; no five-repeat median is invented.",
        "A worker timeout includes loading, warm-up and repetitions and is not a single-replay timing.",
        "Memory comparisons require complete groups on both versions; incomplete memory groups are excluded.",
        "Latency samples, P95/P99 nearest-rank statistics, I/O components, book initialization and active/occupied-price peaks remain available in their separate phase records.",
        "price_levels_visited is null for ordinary replay by definition.",
        "",
        "## Preservation and verification", "",
        "All source fingerprints match the unchanged checkout. Existing datasets and previous results passed the recorded pre-run SHA-256 checks.",
        f"{audit['generated_workloads_verified']} generated workloads were checked against the supplied generator and sidecar checksums.",
        "Input prices and quantities remain positive built-in integers in cents per BTC and 10^-8 BTC; sequences remain positive increasing built-in integers.",
        "audit.py validates the raw calculations, all summary medians, stopped/null fields, checkpoint recovery, latency samples, memory records, workload checksums and all available diagnostic pairs.",
        "See audit.json, before_checks.json, command_wall_time.json and command_output.txt.",
    ]
    (directory / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

assert len({json.dumps(a["source_sha256"], sort_keys=True) for a in audits}) == 1
job_totals = Counter()
raw_totals = Counter()
for audit in audits:
    job_totals.update(audit["job_counts"])
    raw_totals.update(audit["raw_record_states"])
comparisons = [c for a in audits for c in a["diagnostic_comparisons"]]
old_dir = ROOT / "results" / "replay_10000_seed42_batch1"
old_summaries = [json.loads(line) for line in (old_dir / "summaries.jsonl").read_text(encoding="utf-8").splitlines()]
old_memory = next(r for r in old_summaries if r["scenario"] == "sweep" and r["version"] == "baseline" and r["phase"] == "memory")
assert old_memory["status"] == "incomplete"
assert old_memory["completed_repetitions"] == 3 and old_memory["expected_repetitions"] == 5
assert old_memory["memory_peak_bytes"] is None and old_memory["memory_current_bytes"] is None
aggregate = dict(status="verified_all_four_attempts", batches=summary_rows,
    workload_cases=20, version_cases=40, sequential_nonoverlap_verified=True,
    total_command_wall_seconds=sum(w["total_command_wall_seconds"] for w in walls),
    wall_boundary="Sum of the four command wall times; excludes inter-batch gaps, tests and verification.",
    job_counts=dict(job_totals), raw_record_states=dict(raw_totals),
    diagnostic_comparisons=dict(Counter(c["status"] for c in comparisons)),
    source_files_unchanged=True, protected_files_per_audit=audits[0]["protected_files_verified"],
    generated_workloads_verified=sum(a["generated_workloads_verified"] for a in audits),
    seed42_sweep_memory_preserved=dict(status=old_memory["status"],
        completed_repetitions=3, expected_repetitions=5, memory_peak_bytes=None, memory_current_bytes=None),
    scenario_results=[dict(event_count=a["event_count"],seed=a["seed"],**s)
                      for a in audits for s in a["scenario_results"]])
(DEST / "all_batches.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Remaining small replay batches: seeds 43 and 44",
    "",
    "Only the four requested batches ran, in order, with no overlap. The required 89-test suite passed before the first batch.",
    "There were 20 workload cases across five scenarios, each processed by both implementations (40 version cases).",
    "Source revision: " + audits[0]["code_version"] + ". Source files and measurement methodology remained unchanged.",
    f"All {audits[0]['protected_files_verified']} previously existing project/data/result files passed preservation checks, including the seed-42 results.",
    "",
    "## Batch completion and wall time",
    "",
    "| Events | Seed | Command wall, s | Complete jobs | Stopped | Unattempted | Failed |",
    "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
]
for b in summary_rows:
    j = b["job_counts"]
    lines.append(f"| {b['event_count']} | {b['seed']} | {b['wall_seconds']:.6f} | {j['complete']} | {j['stopped']} | {j['unattempted']} | {j['failed']} |")
lines += [
    "",
    f"Sum of command wall times: {aggregate['total_command_wall_seconds']:.6f} seconds "
    f"({aggregate['total_command_wall_seconds']/60:.2f} minutes).",
    "Each external perf_counter wall time includes startup and workload generation, all five phases, warm-ups and repetitions.",
    "The sum excludes test execution, audits, documentation and gaps between batches. It is not an engine replay measurement.",
    "Limits stayed at 60 seconds per worker and 900 seconds per measurement campaign, with preparation outside the campaign deadline.",
    "The existing 128 MiB payload and 512 MiB tracemalloc caps were retained for both versions.",
    "",
    "## Results by scenario and seed",
    "",
    "Cells show Baseline / Revised median replay milliseconds. Every displayed pair has five complete repetitions per version and a matching diagnostic pair.",
    "Unavailable or incomplete groups are not compared.",
    "",
    "| Scenario | 1000, seed 43 | 1000, seed 44 | 10000, seed 43 | 10000, seed 44 |",
    "| --- | ---: | ---: | ---: | ---: |",
]
for scenario in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
    cells = []
    for a in audits:
        s = next(s for s in a["scenario_results"] if s["scenario"] == scenario)
        if s["timing_comparable"]:
            b = s["versions"]["baseline"]["timing"]["replay_seconds"] * 1000
            r = s["versions"]["revised"]["timing"]["replay_seconds"] * 1000
            cells.append(f"{b:.3f} / {r:.3f}")
        else:
            cells.append("not compared")
    lines.append("| " + scenario + " | " + " | ".join(cells) + " |")
lines += [
    "",
    "Per-batch REPORT.md files include throughput and memory completion tables. Raw and summary JSON Lines preserve initialization, total compute, latency, memory and diagnostic fields separately.",
    "Latency uses one separately instrumented pass and nearest-rank P95/P99. Tracemalloc runs in separate workers, excluding preloaded inputs and including book construction and transient results; no history is saved.",
    "",
    "## Diagnostics and incomplete measurements",
    "",
    f"Available matching diagnostic pairs: {sum(c['status']=='passed' for c in comparisons)}. "
    f"Missing pairs: {sum(c['status']=='missing' for c in comparisons)}. Failed pairs: {sum(c['status']=='failed' for c in comparisons)}.",
    "Diagnostic checks include ordered result and canonical-book digests, quantities/fills/rejections, and common active-order/occupied-price peaks and final counts.",
    "",
]
for a in audits:
    for j in a["jobs"]:
        if j["state"] != "complete":
            lines.append(f"- {a['event_count']} events, seed {a['seed']}, {j['case_id']} / {j['version']} / {j['phase']}: "
                         f"{j['state']}, {j['completed_repetitions']}/{j['expected_repetitions']} repetitions retained; {j['error']}.")
lines += [
    "",
    "Incomplete groups retain their complete raw repetitions and explicit stopped/unattempted records; summary measurements remain null.",
    "A 60-second worker timeout includes loading, warm-up and repetitions. It is not treated as a single replay, and no complete median is fabricated.",
    "The validated seed-42 Baseline/sweep memory group remains incomplete at 3/5 with null summary memory values; its saved files are unchanged.",
    "",
    "## Reproduce the audits",
    "",
    "Run from the Assignment1 directory. Audits read the recorded data and do not launch benchmarks.",
    "",
    "~~~console",
]
for name,_,_ in RUNS:
    lines.append(f"python -B results/{name}/audit.py")
lines += [
    "~~~",
    "",
    "before_checks.json records the pre-run checksums and passing test gate. Each audit verifies current source hashes, workload bytes, generator replay, strict integer inputs, timestamps before measurement, repetition counts, calculations, medians and checkpoint exports.",
    f"{aggregate['generated_workloads_verified']} newly generated datasets were saved under data/benchmark with checksum sidecars. Existing datasets were preserved.",
    "all_batches.json contains the combined machine-readable report. command_wall_time.json in each directory records the exact command and timing boundary.",
    "No 100000-event runs, complementary experiments, dashboard, commits or pushes were performed.",
]
(DEST / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(dict(total_command_wall_seconds=aggregate["total_command_wall_seconds"],
    job_counts=aggregate["job_counts"],diagnostic_comparisons=aggregate["diagnostic_comparisons"],
    generated_workloads_verified=aggregate["generated_workloads_verified"],
    report=str(DEST / "SUMMARY.md")), indent=2))

