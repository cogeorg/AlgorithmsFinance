"""Verify saved evidence without running experiments or altering results."""
from collections import defaultdict
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(result_dir=None, dashboard=False):
    folder = Path(result_dir) if result_dir else ROOT / "results"
    meta = json.loads((folder / "environment.json").read_text())
    rows = [json.loads(line) for line in (folder / "measurements.jsonl").read_text().splitlines()]
    summary = json.loads((folder / "summary.json").read_text())
    assert sha(folder / "measurements.jsonl") == meta["measurements_sha256"], "raw result checksum"
    assert sha(folder / "latency_raw.csv.gz") == meta["latency_sha256"], "latency checksum"
    for name, expected in meta["source_sha256"].items():
        assert sha(ROOT / name) == expected, f"measured source changed: {name}"
    initial = json.loads((ROOT / "results/evidence/tests_before.json").read_text())
    assert initial["engine_python_files"] == [] and initial["returncode"] != 0
    for name, expected in initial["tests"].items():
        assert sha(ROOT / name) == expected, f"original test changed: {name}"
    manifest = json.loads((ROOT / "assignment/MANIFEST.json").read_text())
    for name, expected in manifest["files"].items():
        if name == ".DS_Store":
            continue
        path = ROOT / ("assignment/" + name if name in ("AlgorithmsFinance_Exercise1.pdf", "README.md") else name)
        assert path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"], name
    settings = meta["settings"]
    expected = set(itertools.product(("baseline", "revised"), settings["scenarios"],
                                      settings["seeds"], settings["sizes"]))
    actual = {(r["version"],r["scenario"],r["seed"],r["event_count"]) for r in rows
              if r["phase"]=="replay" and r["repeat"]==0}
    assert actual == expected, "incomplete primary matrix"
    keys = ("version","scenario","seed","event_count","levels","sale_percent","phase")
    timing_phases = {"replay","construction","parse","reset","liquidation","application","streaming_app"}
    groups = defaultdict(list)
    all_trials = defaultdict(list)
    for row in rows:
        assert row["status"] in ("ok","stopped"), row
        if "elapsed_seconds" in row:
            assert math.isfinite(row["elapsed_seconds"]) and row["elapsed_seconds"] >= 0
        if row["phase"] in timing_phases:
            key = tuple(row.get(k) for k in keys)
            all_trials[key].append(row)
            if row["repeat"] > 0 and row["status"]=="ok":
                groups[key].append(row)
        if row["phase"]=="memory":
            assert row["peak_traced_bytes"] >= row["current_traced_bytes"] >= 0
            assert row["stored_orders"] == row["active_orders"] and row["stale_entries"] == 0
        if row["phase"]=="sale_outcome" and row["status"]=="ok":
            assert row["fill_count"] == row["makers_touched"]
            assert row["prices_visited"] <= row["fill_count"]
            assert row["unfilled_qty_units"] >= 0 and row["proceeds_tick_units"] > 0
    for key, trials in all_trials.items():
        repetitions = [r["repeat"] for r in trials]
        assert len(repetitions)==len(set(repetitions)), ("duplicate trial",key)
        assert repetitions == list(range(len(repetitions))), ("noncontiguous trials",key)
        stopped = [r for r in trials if r["status"]=="stopped"]
        if stopped:
            assert stopped == [trials[-1]], ("continued after stop",key)
        else:
            partner = list(key)
            partner[-1] = "liquidation" if key[-1]=="reset" else "reset"
            paired_stop = key[-1] in ("reset","liquidation") and any(
                r["status"]=="stopped" for r in all_trials.get(tuple(partner),[]))
            assert repetitions == list(range(6)) or paired_stop, ("missing repeat without stop",key)
    summary_map = {tuple(r.get(k) for k in keys):r for r in summary}
    assert len(summary_map)==len(summary)==len(groups)
    for key, samples in groups.items():
        saved = summary_map[key]
        assert saved["repeats"] == len(samples)
        median = statistics.median(r["elapsed_seconds"] for r in samples)
        assert saved["elapsed_seconds"] == median, ("median",key)
        if "throughput_events_per_second" in saved:
            assert saved["throughput_events_per_second"] == saved["event_count"]/median
    latency = defaultdict(list)
    with gzip.open(folder / "latency_raw.csv.gz", "rt") as stream:
        for row in csv.DictReader(stream):
            key=(row["version"],row["scenario"],int(row["seed"]),int(row["event_count"]))
            value=float(row["elapsed_seconds"])
            assert math.isfinite(value) and value >= 0
            latency[key].append((int(row["seq"]),row["type"],value))
    for values in latency.values():
        assert [v[0] for v in values]==list(range(1,len(values)+1))
    for row in rows:
        if row["phase"]!="latency_summary":
            continue
        key=(row["version"],row["scenario"],row["seed"],row["event_count"])
        values = latency[key]
        cohort=row["cohort"]
        if cohort=="early": values=values[:max(1,row["event_count"]//10)]
        elif cohort=="late":
            assert len(values)==row["event_count"]
            values=values[-max(1,row["event_count"]//10):]
        elif cohort!="all": values=[v for v in values if v[1]==cohort]
        times=sorted(v[2] for v in values)
        assert row["samples"]==len(times)
        for name,p in (("p50_seconds",.5),("p95_seconds",.95),("p99_seconds",.99)):
            assert row[name]==times[max(0,math.ceil(p*len(times))-1)], ("percentile",key,cohort)
    for entry in json.loads((folder / "inputs.json").read_text()):
        path=ROOT / entry["path"]
        if path.exists():
            assert sha(path)==entry["sha256"], f"generated input changed: {path}"
    if dashboard:
        html=(ROOT/"dashboard.html").read_text()
        marker='<script id="saved-data" type="application/json">'
        payload=json.loads(html.split(marker,1)[1].split("</script>",1)[0])
        assert payload["measurements"]==rows and payload["summary"]==summary
        assert payload["metadata"]==meta
    result=dict(primary_configurations=len(expected),raw_rows=len(rows),timing_summaries=len(summary),
                stopped_trials=sum(r["status"]=="stopped" for r in rows if "elapsed_seconds" in r),
                latency_samples=sum(len(v) for v in latency.values()),
                source_files=len(meta["source_sha256"]),original_tests_unchanged=True)
    return result


if __name__=="__main__":
    print(json.dumps(verify(dashboard=(ROOT/"dashboard.html").exists()),indent=2))
