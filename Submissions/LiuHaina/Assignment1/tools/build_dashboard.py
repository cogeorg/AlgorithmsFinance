"""Build an offline dashboard exclusively from saved results; never run engines."""
import argparse
import bisect
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load_data(folder):
    rows = [json.loads(s) for s in (folder/"raw_results.jsonl").read_text().splitlines()]
    histograms = {}
    edges = [0.0]+[10**(-1+i/10) for i in range(81)]
    for row in rows:
        if row["phase"]!="latency" or not row.get("raw_file"):
            continue
        counts = [0]*(len(edges)-1)
        with gzip.open(folder/row["raw_file"],"rt",newline="") as stream:
            for sample in csv.DictReader(stream):
                us = float(sample["elapsed_seconds"])*1e6
                index = min(len(counts)-1,max(0,bisect.bisect_right(edges,us)-1))
                counts[index] += 1
        if sum(counts)!=row["samples"]:
            raise ValueError("saved latency count differs from measurement summary")
        histograms[row["job_id"]] = dict(counts=counts,samples=sum(counts))
    test_log = (ROOT/"evidence/benchmark_tests.log").read_text()
    matches = re.findall(r"Ran (\d+) tests",test_log)
    tests = dict(count=int(matches[-1]),passed="\nOK\n" in test_log) if matches else dict(count=0,passed=False)
    names = ("settings.json","validation.json","summary.json")
    content = {name.removesuffix(".json"):json.loads((folder/name).read_text()) for name in names}
    content.update(raw=rows,histograms=histograms,histogram_edges_us=edges,tests=tests,
        parity=json.loads((ROOT/"evidence/parity_supplied.json").read_text()),
        benchmark_tests_sha256=hashlib.sha256(test_log.encode()).hexdigest(),
        raw_source_sha256=hashlib.sha256((folder/"raw_results.jsonl").read_bytes()).hexdigest())
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,default=ROOT/"results/benchmark")
    parser.add_argument("--out",type=Path,default=ROOT/"dashboard.html")
    args = parser.parse_args()
    data = load_data(args.results)
    payload = json.dumps(data,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    template = (ROOT/"dashboard/template.html").read_text()
    for marker in ("/*__STYLE__*/","/*__DATA__*/","/*__SCRIPT__*/"):
        if template.count(marker)!=1:
            raise ValueError(f"template marker missing or duplicated: {marker}")
    html = template.replace("/*__STYLE__*/",(ROOT/"dashboard/style.css").read_text())
    html = html.replace("/*__DATA__*/",payload).replace("/*__SCRIPT__*/",(ROOT/"dashboard/app.js").read_text())
    args.out.write_text(html)
    print(json.dumps(dict(output=str(args.out),bytes=len(html.encode()),raw_records=len(data["raw"]),
                         latency_samples=sum(h["samples"] for h in data["histograms"].values())),indent=2))


if __name__=="__main__":
    main()
