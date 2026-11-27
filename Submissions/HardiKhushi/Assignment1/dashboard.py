"""Build an offline dashboard and findings strictly from saved measurements."""
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import re
import statistics
from verify_results import verify

ROOT=Path(__file__).resolve().parent


def payload():
    verification=verify()
    folder=ROOT/"results"
    rows=[json.loads(line) for line in (folder/"measurements.jsonl").read_text().splitlines()]
    summary=json.loads((folder/"summary.json").read_text())
    metadata=json.loads((folder/"environment.json").read_text())
    hist=defaultdict(Counter)
    with gzip.open(folder/"latency_raw.csv.gz","rt") as stream:
        for row in csv.DictReader(stream):
            key=(row["version"],row["scenario"],int(row["seed"]),int(row["event_count"]))
            bucket=2**math.floor(math.log2(max(.001,float(row["elapsed_seconds"])*1e6)))
            hist[key][bucket]+=1
    histograms=[dict(version=k[0],scenario=k[1],seed=k[2],event_count=k[3],
                     bins=sorted(v.items()),samples=sum(v.values())) for k,v in hist.items()]
    tests=[]
    for name,label in (("tests_before.txt","Before implementation"),("tests_baseline.txt","Baseline"),
                       ("tests_revised.txt","Both versions"),("tests_final.txt","Final suite")):
        path=folder/"evidence"/name
        if path.exists():
            text=path.read_text()
            count=re.search(r"Ran (\d+) tests",text)
            tests.append(dict(stage=label,count=int(count.group(1)) if count else None,
                              outcome="Expected missing-module errors" if name=="tests_before.txt" else
                              "Pass (one explicit skip)" if "skipped=1" in text else "Pass" if "\nOK" in text else "Review log",
                              file=f"results/evidence/{name}"))
    return dict(metadata=metadata,measurements=rows,summary=summary,histograms=histograms,
                correctness=tests,verification=verification)


def findings(data):
    rows,summary=data["measurements"],data["summary"]
    complete=[r for r in summary if r["phase"]=="replay" and r["repeats"]==5]
    groups=defaultdict(dict)
    for r in complete:
        groups[r["scenario"],r["seed"],r["event_count"]][r["version"]]=r["elapsed_seconds"]
    paired=[(k,v["baseline"]/v["revised"]) for k,v in groups.items() if set(v)=={"baseline","revised"}]
    lines=["# Findings from executed measurements","",
           f"Verified {data['verification']['primary_configurations']} primary version/workload configurations.",
           f"Saved {len(rows):,} raw/diagnostic rows and {data['verification']['latency_samples']:,} individual latency samples.",
           f"{data['verification']['stopped_trials']} timed trials stopped at the declared deadline (across all phases).","",
           "Only completed five-repeat replay medians are compared below. Stopped trials are not zeros.",""]
    if paired:
        lines += [f"The revised version was faster in {sum(r>1 for _,r in paired)}/{len(paired)} paired configurations.",
                  f"Baseline/revised ratios range from {min(r for _,r in paired):.2f} to {max(r for _,r in paired):.2f};",
                  f"the median paired ratio is {statistics.median(r for _,r in paired):.2f}. Ratios describe this run only.",""]
    lines += ["| Scenario | Seed | Events | Baseline/revised replay ratio |","| --- | --- | --- | --- |"]
    for (scenario,seed,count),ratio in sorted(paired):
        lines.append(f"| {scenario} | {seed} | {count:,} | {ratio:.2f} |")
    lines += ["","## Largest seed-42 replay cases","","| Scenario | Version | Seconds (median) | Repeats |","| --- | --- | --- | --- |"]
    largest=max(data["metadata"]["settings"]["sizes"])
    for scenario in data["metadata"]["settings"]["scenarios"]:
        for version in ("baseline","revised"):
            r=next((r for r in summary if r["phase"]=="replay" and r["seed"]==42 and
                    r["event_count"]==largest and r["scenario"]==scenario and r["version"]==version),None)
            lines.append(f"| {scenario} | {version} | {r['elapsed_seconds']:.6f} | {r['repeats']} |" if r else
                         f"| {scenario} | {version} | stopped / no completed timed repeats | 0 |")
    lines += ["","## Measured scan bottleneck","",
              "Small counter runs are separate from timing. For 1,000-event buildup seed 42:",""]
    for r in rows:
        if r["phase"]=="counters" and r["scenario"]=="buildup" and r["seed"]==42:
            lines.append(f"- {r['version']}: `{json.dumps(r['operations'],sort_keys=True)}`")
    lines += ["","These counts expose the baseline's repeated scans of a growing book even when no maker fills.",
              "The revision uses indexed validation and checks the best occupied price. Sorted price insertion still shifts entries.",
              "","## Post-cancellation allocation","","| Events | Version | Current traced bytes | Peak bytes | Active/stored/stale |","| --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["phase"]=="memory" and r["scenario"]=="cancel_churn" and r["seed"]==42:
            lines.append(f"| {r['event_count']:,} | {r['version']} | {r['current_traced_bytes']:,} | {r['peak_traced_bytes']:,} | {r['active_orders']}/{r['stored_orders']}/{r['stale_entries']} |")
    lines += ["","This is traced engine allocation with preloaded events excluded, not total process memory.",
              "Checkpoint records and the current output are included; allocator capacity need not shrink after every deletion.",
              "","## Million-event feasibility","",
              "Only cancel_churn, seed 42, was attempted at one million events. Streaming application time includes parsing.",""]
    for r in rows:
        if r["event_count"]==1000000 and r["phase"] in ("parse","streaming_app") and r["repeat"]==0:
            lines.append(f"- {r['version']} {r['phase']} warmup: {r['status']}, {r['elapsed_seconds']:.3f} s.")
    for r in summary:
        if r["event_count"]==1000000:
            lines.append(f"- {r['version']} {r['phase']}: {r['elapsed_seconds']:.6f} s median of {r['repeats']} repeats.")
    lines += ["","## Interpretation limits","",
              "Sequential run order, OS activity, Python version and allocator effects influence these measurements.",
              "No network/queueing latency, overload capacity, confidence intervals or exchange calibration are claimed.",
              "See docs/REPORT.md for measurement boundaries, full complexity qualifications and unattempted work."]
    return "\n".join(lines)+"\n"


def main():
    data=payload()
    embedded=json.dumps(data,separators=(",", ":")).replace("</","<\\/")
    html=(ROOT/"dashboard_template.html").read_text().replace("@@DATA@@",embedded)
    (ROOT/"dashboard.html").write_text(html)
    (ROOT/"results/FINDINGS.md").write_text(findings(data))
    print(json.dumps(data["verification"],indent=2))


if __name__=="__main__":
    main()
