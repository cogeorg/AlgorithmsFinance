"""Memory measurement with tracemalloc. Run with:  python memory.py

Run separately from timing (tracing slows Python down).
For each method: build the input first, start a fresh trace, run preparation AND the
query batch, keep the returned answers alive, read current/peak traced bytes, stop.

What the numbers include:
    INCLUDED : the prepared structure (sorted copy or hash set), the output list of
               Booleans, and temporary objects (e.g. list slices in binary_v1)
    EXCLUDED : the given input array and query list (built before tracing started)
tracemalloc sees Python allocations only, so this is NOT exactly auxiliary space.
"""
import csv
import gc
import json
import tracemalloc
from pathlib import Path

from data import make_ids, make_queries
from membership import METHODS
from benchmark import SEED, DUPLICATES, environment


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    rows = []
    for n in [1_000, 10_000, 100_000]:
        ids = make_ids(n, SEED, DUPLICATES)
        for q in [1, 100]:
            queries = make_queries(ids, q, 0.5, SEED)
            for method, (prepare, query, version) in METHODS.items():
                gc.collect()
                tracemalloc.start()
                prepared = prepare(ids)
                answers = query(prepared, queries)
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                assert len(answers) == q
                rows.append([method, version, n, q, 0.5, current, peak])
                print(f"n={n:>6} q={q:>3} {method:<9} peak {peak/1024:10.1f} KiB")
                del prepared, answers
    with open(out / "memory.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "version", "n", "q", "hit_rate",
                    "current_bytes", "peak_bytes"])
        w.writerows(rows)
    meta = {**environment("memory.py"), "seed": SEED, "hit_rate": 0.5,
            "units": "bytes (tracemalloc current and peak)",
            "includes": "prepared structure, temporary objects, output list",
            "excludes": "the given input array and query list",
            "runs": "one traced run per setting (deterministic allocations)"}
    (out / "memory_environment.json").write_text(json.dumps(meta, indent=2))
    print(f"saved {out/'memory.csv'}, {out/'memory_environment.json'}")


if __name__ == "__main__":
    main()
