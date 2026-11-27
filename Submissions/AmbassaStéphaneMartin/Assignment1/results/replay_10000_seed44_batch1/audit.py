"""Audit this recorded remaining-small replay batch; never run benchmarks."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

RUN = Path(__file__).resolve().parent
ROOT = RUN.parent.parent
sys.path.insert(0, str(ROOT))
import benchmark as bm


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    started = time.perf_counter()
    before = read_json(RUN / "before_checks.json")
    assert before["tests"]["exit_code"] == 0
    changed = [name for name, value in before["protected_sha256"].items()
               if not (ROOT / name).is_file() or digest(ROOT / name) != value]
    assert not changed, changed
    expected_count = before["batch"]["count"]
    expected_seed = before["batch"]["seed"]
    manifest = read_json(RUN / "manifest.json")
    wall = read_json(RUN / "command_wall_time.json")
    raw = read_jsonl(RUN / "raw.jsonl")
    summaries = read_jsonl(RUN / "summaries.jsonl")
    assert len(manifest["workloads"]) == 5
    assert set(manifest["versions"]) == {"baseline", "revised"}
    assert tuple(manifest["phases"]) == ("io", "timing", "latency", "memory", "diagnostics")
    assert manifest["repetitions"] == 5
    assert manifest["limits"] == dict(worker_wall_seconds=60.0,
        measurement_campaign_wall_seconds=900.0, payload_bytes=128 * 1024 ** 2,
        traced_allocation_bytes=512 * 1024 ** 2, os_rss_hard_limit=None,
        preparation="Generation precedes measurement deadline; no preparation timeout")
    assert manifest["environment"]["git_head"] == before["git_head"]
    for name, value in manifest["environment"]["source_sha256"].items():
        assert digest(ROOT / name) == value, name
    assert wall["exit_code"] in (0, 2)
    assert manifest["run_kind"] == "remaining-small-replay"
    assert wall["total_command_wall_seconds"] > 0
    assert len(wall["progress"]) == 45
    assert [p["job_index"] for p in wall["progress"]] == list(range(1, 46))
    assert close(sum(p["interval_since_previous_progress_seconds"] for p in wall["progress"]),
                 wall["progress"][-1]["elapsed_command_seconds"])
    assert wall["total_command_wall_seconds"] >= wall["progress"][-1]["elapsed_command_seconds"]
    workloads = {}
    for case in manifest["workloads"]:
        assert case["experiment"] == "replay"
        assert case["event_count"] == case["source_event_count"] == case["requested_count"] == expected_count
        assert case["seed"] == expected_seed and case["levels"] == 1000
        path = Path(case["source"]["path"])
        assert path.parent == ROOT / "data" / "benchmark"
        relative = str(path.relative_to(ROOT))
        if case["source"]["reused"]:
            assert before["protected_sha256"].get(relative) == digest(path)
        else:
            assert relative not in before["protected_sha256"]
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == case["source"]["sha256"]
        assert case["source"]["metadata"]["sha256"] == case["source"]["sha256"]
        decoded = gzip.decompress(data)
        events = [json.loads(line) for line in decoded.decode("utf-8").splitlines() if line.strip()]
        assert len(events) == expected_count
        assert events == list(bm.generate_orders.events(case["scenario"], expected_count, expected_seed, 1000))
        sidecar = read_json(path.with_suffix(path.suffix + ".metadata.json"))
        assert sidecar == case["source"]["metadata"]
        assert sidecar["generator_source_sha256"] == digest(ROOT / "generate_orders.py")
        assert sidecar["benchmark_source_sha256"] == digest(ROOT / "benchmark.py")
        assert path.stat().st_mtime <= datetime.fromisoformat(manifest["started_utc"]).timestamp() + 1
        last = 0
        identifiers = set()
        for event in events:
            assert type(event["seq"]) is int and event["seq"] > last
            last = event["seq"]
            assert type(event["event_id"]) is str and event["event_id"].strip()
            assert event["event_id"] not in identifiers
            identifiers.add(event["event_id"])
            for key in ("price_ticks", "qty_units"):
                if key in event:
                    assert type(event[key]) is int and event[key] > 0
        workloads[case["case_id"]] = dict(case=case, events=events,
            compressed_bytes=len(data), decoded_bytes=len(decoded))
    assert {w["case"]["scenario"] for w in workloads.values()} == set(bm.SCENARIOS)
    groups = {}
    raw_counts = Counter()
    for row in raw:
        key = (row["case_id"], row["version"], row["phase"])
        groups.setdefault(key, []).append(row)
        raw_counts[row["status"]] += 1
        workload = workloads[row["case_id"]]
        assert row["workload_sha256"] == workload["case"]["source"]["sha256"]
        assert row["event_count"] == expected_count and row["seed"] == expected_seed
        assert row["price_levels_visited"] is None
        assert all(field in row for field in bm.METRICS)
        if row["status"] != "complete":
            assert row["status"] in ("stopped", "not_run", "error")
            assert all(row[field] is None for field in bm.METRICS)
            continue
        phase = row["phase"]
        if phase == "io":
            assert row["version"] is None
            assert row["compressed_bytes"] == workload["compressed_bytes"]
            assert row["decoded_bytes"] == workload["decoded_bytes"]
            components = [row[field] for field in
                          ("read_seconds", "decompress_seconds", "parse_seconds")]
            assert all(math.isfinite(value) and value >= 0 for value in components)
            assert close(row["io_total_seconds"], sum(components))
        elif phase == "timing":
            assert row["processed_events"] == expected_count
            assert row["construction_seconds"] is None
            assert row["replay_seconds"] > 0
            assert close(row["total_compute_seconds"],
                         row["initialization_seconds"] + row["replay_seconds"])
            assert close(row["throughput_events_per_second"], expected_count / row["replay_seconds"])
            assert row["fill_count"] is None and row["memory_peak_bytes"] is None
            assert row["latency_p99_seconds"] is None
        elif phase == "latency":
            saved = read_json(row["latency_samples_path"])
            samples = saved["samples"]
            assert len(samples) == row["latency_sample_count"] == expected_count
            for sample, event in zip(samples, workload["events"]):
                assert sample["event_id"] == event["event_id"] and sample["seq"] == event["seq"]
                assert sample["repetition"] == 1
                assert math.isfinite(sample["seconds"]) and sample["seconds"] >= 0
            values = sorted(sample["seconds"] for sample in samples)
            assert row["latency_median_seconds"] == statistics.median(values)
            assert row["latency_p95_seconds"] == values[math.ceil(.95 * len(values)) - 1]
            assert row["latency_p99_seconds"] == values[math.ceil(.99 * len(values)) - 1]
        elif phase == "memory":
            assert row["memory_peak_bytes"] >= row["memory_current_bytes"] >= 0
            assert row["memory_peak_bytes"] >= row["memory_after_construction_bytes"] >= 0
            assert row["processed_events"] == expected_count and row["replay_seconds"] is None
        elif phase == "diagnostics":
            assert row["processed_events"] == expected_count
            for field in ("fill_count", "unfilled_qty_units", "cancelled_qty_units",
                          "rejected_event_count", "active_orders_final", "occupied_prices_final"):
                assert type(row[field]) is int and row[field] >= 0
            assert row["active_orders_final"] <= row["active_orders_peak"]
            assert row["occupied_prices_final"] <= row["occupied_prices_peak"]
            assert len(row["result_digest"]) == len(row["snapshot_digest"]) == 64
            assert row["replay_seconds"] is None
    assert len(groups) == len(summaries) == 45
    jobs = []
    summary_map = {}
    for index, summary in enumerate(summaries, 1):
        key = (summary["case_id"], summary["version"], summary["phase"])
        summary_map[key] = summary
        rows = groups[key]
        expected = 5 if summary["phase"] in ("io", "timing", "memory") else 1
        complete_count = sum(row["status"] == "complete" for row in rows)
        complete = complete_count == expected
        assert len(rows) == expected
        assert [row["repetition"] for row in rows] == list(range(1, expected + 1))
        assert summary["expected_repetitions"] == expected
        assert summary["completed_repetitions"] == complete_count
        assert summary["status"] == ("complete" if complete else "incomplete")
        for field in bm.METRICS:
            values = [row[field] for row in rows if row[field] is not None]
            expected_value = statistics.median(values) if complete and len(values) == expected else None
            assert summary[field] == expected_value, (key, field)
        states = {row["status"] for row in rows}
        state = ("complete" if complete else "stopped" if "stopped" in states
                 else "unattempted" if states == {"not_run"} else "failed")
        progress = wall["progress"][index - 1]
        assert (progress["case_id"], progress["version"], progress["phase"]) == key
        assert progress["status"] == summary["status"]
        jobs.append(dict(job_index=index, case_id=key[0], version=key[1], phase=key[2],
                         state=state, completed_repetitions=complete_count,
                         expected_repetitions=expected, error=summary["error"],
                         observed_progress_interval_seconds=progress["interval_since_previous_progress_seconds"]))
    # Completed checkpoint rows must survive byte-for-value in the export.
    checkpoint_rows = []
    for job_path in sorted((RUN / "workers").glob("*.job.json")):
        job = read_json(job_path)
        checkpoint_path = Path(job["checkpoint"])
        checkpoint = read_json(checkpoint_path) if checkpoint_path.exists() else {"rows": []}
        key = (job["case"]["case_id"], job["version"], job["phase"])
        complete_rows = [row for row in groups[key] if row["status"] == "complete"]
        assert checkpoint["rows"] == complete_rows
        checkpoint_rows.extend(complete_rows)
    comparisons = []
    compare_fields = ("result_digest", "snapshot_digest", "fill_count", "price_levels_visited",
                      "unfilled_qty_units", "cancelled_qty_units", "rejected_event_count",
                      "active_orders_peak", "occupied_prices_peak",
                      "active_orders_final", "occupied_prices_final")
    scenario_results = []
    for case_id, workload in workloads.items():
        versions = {version: {phase: summary_map[(case_id, version, phase)]
                    for phase in bm.PHASES[1:]} for version in bm.VERSIONS}
        left, right = (versions[version]["diagnostics"] for version in bm.VERSIONS)
        missing = [version for version in bm.VERSIONS
                   if versions[version]["diagnostics"]["status"] != "complete"]
        mismatches = [field for field in compare_fields if left[field] != right[field]] if not missing else []
        comparisons.append(dict(scenario=workload["case"]["scenario"], case_id=case_id,
            status="missing" if missing else "failed" if mismatches else "passed",
            missing_versions=missing, mismatched_fields=mismatches))
        timed = [versions[version]["timing"] for version in bm.VERSIONS]
        comparable = all(row["status"] == "complete" for row in timed) and not missing and not mismatches
        ratio = timed[0]["replay_seconds"] / timed[1]["replay_seconds"] if comparable else None
        scenario_results.append(dict(scenario=workload["case"]["scenario"],
            timing_comparable=comparable,baseline_over_revised_replay_ratio=ratio,
            versions={version: {phase: {field: row[field] for field in
                ("status","completed_repetitions","expected_repetitions","replay_seconds",
                 "throughput_events_per_second","initialization_seconds","total_compute_seconds",
                 "latency_median_seconds","latency_p95_seconds","latency_p99_seconds",
                 "memory_peak_bytes","memory_current_bytes","active_orders_peak","occupied_prices_peak",
                 "fill_count","unfilled_qty_units","cancelled_qty_units")}
                for phase,row in phases.items()} for version,phases in versions.items()}))
    saved_comparisons = {row["case_id"]: row["status"] for row in manifest["diagnostic_comparisons"]}
    available = {row["case_id"]: row["status"] for row in comparisons if row["status"] != "missing"}
    assert saved_comparisons == available
    counts = dict(Counter(job["state"] for job in jobs))
    for key in ("complete", "stopped", "unattempted", "failed"):
        counts.setdefault(key, 0)
    assert manifest["completed_jobs"] == counts["complete"]
    assert manifest["raw_rows"] == len(raw) and manifest["summary_rows"] == len(summaries)
    expected_status = "complete" if counts["complete"] == 45 and all(
        c["status"] == "passed" for c in comparisons) else "incomplete"
    assert manifest["status"] == expected_status
    assert wall["exit_code"] == (0 if expected_status == "complete" else 2)
    report = dict(audit_status="passed", campaign_status=manifest["status"],
        code_version=manifest["environment"]["git_head"],
        source_sha256=manifest["environment"]["source_sha256"],
        protected_files_verified=len(before["protected_sha256"]),test_result=before["tests"],
        total_command_wall_seconds=wall["total_command_wall_seconds"],
        wall_boundary=wall["boundary"],wall_exit_code=wall["exit_code"],
        measurement_span_utc_seconds=(datetime.fromisoformat(manifest["finished_utc"])-
                                      datetime.fromisoformat(manifest["started_utc"])).total_seconds(),
        job_counts=counts,raw_record_states=dict(raw_counts),jobs=jobs,
        diagnostic_comparisons=comparisons,scenario_results=scenario_results,
        completed_checkpoint_rows_verified=len(checkpoint_rows),
        audit_elapsed_seconds=time.perf_counter()-started,
        warnings=["A stopped worker includes loading, warm-up and repetitions; its 60-second limit "
                  "is not a single-replay duration.",
                  "Incomplete groups retain raw completed repetitions and have null summary medians."])
    report["event_count"] = expected_count
    report["seed"] = expected_seed
    report["generated_workloads_verified"] = sum(not w["case"]["source"]["reused"] for w in workloads.values())
    report["reused_workloads_verified"] = sum(w["case"]["source"]["reused"] for w in workloads.values())
    return report


if __name__ == "__main__":
    report = audit()
    destination = RUN / "audit.json"
    if destination.exists():
        previous = read_json(destination)
        left, right = dict(previous), dict(report)
        left.pop("audit_elapsed_seconds")
        right.pop("audit_elapsed_seconds")
        assert left == right
    else:
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key:report[key] for key in (
        "audit_status","campaign_status","total_command_wall_seconds","job_counts",
        "raw_record_states","diagnostic_comparisons")},indent=2))



