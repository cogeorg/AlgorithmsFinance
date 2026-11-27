"""Check the ten-second per-search budget using saved data and fresh executions."""
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

from algorithms import HashIndex
from data import make_workload

HERE = Path(__file__).resolve().parent


def run(folder=HERE / "results", limit_seconds=10):
    data_path = folder / "measurements.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    saved = [sample["total_ms"] / 1000
             for row in data["rows"] for sample in row["raw_repeats"]]
    if not saved or not all(math.isfinite(t) and 0 <= t < limit_seconds for t in saved):
        raise RuntimeError("Saved per-batch measurements exceed the requested time budget")
    work = make_workload(100000, 100, 0.5, seed=721)
    present = set(work.items)
    expected = [query in present for query in work.queries]
    samples = []
    for _ in range(5):
        start = perf_counter()
        index = HashIndex(work.items)
        output = index.answer(work.queries)
        elapsed = perf_counter() - start
        if output != expected:
            raise AssertionError("Incorrect fresh search result")
        samples.append(elapsed)
        del index, output
    if not all(0 <= t < limit_seconds for t in samples):
        raise RuntimeError("Fresh optimized search exceeded the time budget")
    report = {
        "scope": "One complete search batch, including index construction. Not the duration of the benchmark suite.",
        "units": "seconds", "limit_seconds": limit_seconds,
        "saved_sample_count": len(saved), "saved_maximum_seconds": max(saved),
        "live": {"n": 100000, "q": 100, "hit_rate": 0.5, "seed": 721,
                 "includes_index_construction": True, "samples_seconds": samples,
                 "median_seconds": statistics.median(samples), "maximum_seconds": max(samples)},
        "python": sys.version, "platform": platform.platform(),
        "measurements_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("algorithms.py", "data.py", "check_speed.py")},
        "passed": True,
    }
    (folder / "speed_budget.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
