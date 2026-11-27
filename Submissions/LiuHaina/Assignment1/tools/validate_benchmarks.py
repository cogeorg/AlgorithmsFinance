"""Audit experiment coverage, raw repeats, hashes and saved latency quantiles."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT/"results/benchmark")
    parser.add_argument("--skip-input-check", action="store_true",
                        help="audit saved evidence without locally generated streams; requires --out")
    parser.add_argument("--out", type=Path,
                        help="write a separate audit instead of replacing saved validation.json")
    args = parser.parse_args()
    if args.skip_input_check and args.out is None:
        parser.error("--skip-input-check requires --out to preserve the original full validation record")
    folder = args.results.resolve()
    if args.skip_input_check and args.out.resolve()==(folder/"validation.json").resolve():
        parser.error("--skip-input-check --out must not target the original validation.json")
    settings = json.loads((folder/"settings.json").read_text())
    rows = [json.loads(s) for s in (folder/"raw_results.jsonl").read_text().splitlines()]
    manifest = json.loads((folder/"input_manifest.json").read_text())
    for name, expected in settings["code_sha256"].items():
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,f"code changed: {name}")
    if not args.skip_input_check:
        for entry in manifest:
            require(hashlib.sha256((ROOT/entry["file"]).read_bytes()).hexdigest()==entry["sha256"],
                    f"input changed: {entry['file']}")
    required_cases = set(itertools.product(("A","B"),settings["scenarios"],settings["sizes"],settings["seeds"]))
    repeat_rows = [r for r in rows if r["phase"]=="replay" and r["event_count"] in settings["sizes"]]
    observed = Counter((r["version"],r["scenario"],r["event_count"],r["seed"]) for r in repeat_rows)
    require(set(observed)==required_cases,"missing or extra primary cases")
    require(all(n==5 for n in observed.values()),"every case must retain five attempted repeats")
    for key in required_cases:
        matches = [r for r in repeat_rows if (r["version"],r["scenario"],r["event_count"],r["seed"])==key]
        require({r["repeat"] for r in matches}==set(range(1,6)),f"repeat indices: {key}")
        for row in matches:
            if row["status"]=="completed":
                require(row["events_processed"]==row["event_count"],"partial run marked completed")
                require(row["correctness"]=="final_digest_matches","missing final-state check")
            else:
                require(row.get("throughput_events_per_second") is None,"partial run has full throughput")
    index = {(r["job_id"],r["phase"],r.get("repeat")):r for r in rows}
    for row in rows:
        require(row["phase_limit_seconds"]==settings["phase_limit_seconds"],"time boundary changed")
        require(row["rss_limit_bytes"]==settings["rss_limit_bytes"],"RSS boundary changed")
        if row["phase"]=="parse_plus_replay" and row["status"]=="completed":
            parsed = index[(row["job_id"],"input_parse",row["repeat"])]
            replay = index[(row["job_id"],"replay",row["repeat"])]
            require(math.isclose(row["elapsed_seconds"],parsed["elapsed_seconds"]+replay["elapsed_seconds"],rel_tol=1e-12),"parse/replay sum mismatch")
        if row["phase"]=="construction" and row["status"]=="completed":
            replay = index[(row["job_id"],"replay",row["repeat"])]
            require(row["elapsed_seconds"]<=replay["elapsed_seconds"],"construction exceeds replay")
    latency_files = latency_samples = 0
    for row in rows:
        if row["phase"]!="latency" or not row.get("raw_file"):
            continue
        with gzip.open(folder/row["raw_file"],"rt",newline="") as stream:
            samples = list(csv.DictReader(stream))
        require(len(samples)==row["samples"],"raw latency count mismatch")
        values = sorted(float(r["elapsed_seconds"]) for r in samples)
        if values:
            require(math.isclose(statistics.median(values),row["median_seconds"],rel_tol=1e-9),"median mismatch")
            for name,p in (("p95_seconds",.95),("p99_seconds",.99)):
                require(math.isclose(values[math.ceil(p*len(values))-1],row[name],rel_tol=1e-9),f"{name} mismatch")
        latency_files += 1
        latency_samples += len(samples)
    summary = json.loads((folder/"summary.json").read_text())
    for aggregate in summary:
        if aggregate["phase"]!="replay" or aggregate["event_count"] not in settings["sizes"]:
            continue
        selected = [r for r in repeat_rows if all(r.get(k)==aggregate.get(k) for k in ("version","scenario","event_count","seed"))]
        complete = [r["elapsed_seconds"] for r in selected if r["status"]=="completed"]
        require(aggregate["median_elapsed_seconds"]==(statistics.median(complete) if complete else None),"repeat median mismatch")
    sale_rows = [r for r in rows if r["phase"]=="individual_sale"]
    expected_sales = 2 * (1 if settings["smoke"] else 3) * 2 * 3 * 5
    require(len(sale_rows)==expected_sales,"missing planned liquidation attempts")
    for row in sale_rows:
        if row["status"]=="completed":
            require(row["correctness"]=="independent_price_fifo_prefix_matches","sale oracle absent")
            require(row["unfilled_qty_units"]==max(0,row["requested_qty_units"]-row["available_bid_qty_units"]),"sale residual mismatch")
    result = dict(status="passed",primary_cases=len(required_cases),primary_repeat_rows=len(repeat_rows),
        primary_statuses=dict(Counter(r["status"] for r in repeat_rows)),
        liquidation_attempts=len(sale_rows),latency_files=latency_files,latency_samples=latency_samples,
        all_recorded_source_hashes_match=True,
        all_generated_input_hashes_match=None if args.skip_input_check else True,
        same_resource_limits=True,all_saved_medians_and_quantiles_match_raw=True)
    if args.skip_input_check:
        result["input_hash_check"]="not_checked_generated_streams_intentionally_omitted"
    destination=args.out or folder/"validation.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
