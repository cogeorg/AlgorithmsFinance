#!/usr/bin/env python3
"""Reading + gzip + JSON parsing time per input, separate from engine time.

Parsing is version-independent (both versions consume the same list of event dicts), so it
is measured once per input: 1 warmup + 5 timed repeats with time.perf_counter, every raw
repeat saved, median reported (results/parse.csv). The parsed list is dropped after each
repeat. The timing step additionally records one parse per configuration as a sanity value.
"""
import gc
import time
from statistics import median

from _util import MILLION, REPEATS, RESULTS, SCENARIOS, SEEDS, SIZES, input_path, write_csv
from lob.common import read_events


def main():
    rows = []
    configs = [(s, n, seed) for n in SIZES for s in SCENARIOS for seed in SEEDS] + MILLION
    for scenario, n, seed in configs:
        path = input_path(scenario, n, seed)
        times = []
        for rep in range(REPEATS + 1):  # repeat 0 = warmup
            gc.collect()
            t = time.perf_counter()
            events = read_events(path)
            el = time.perf_counter() - t
            del events
            rows.append({"run_kind": "parse", "version": "-", "scenario": scenario, "seed": seed, "events": n,
                         "levels": 1000, "phase": "parse", "repeat": rep, "elapsed_s": f"{el:.6f}",
                         "status": "warmup" if rep == 0 else "ok"})
            if rep:
                times.append(el)
        print(f"{scenario:12s} {n:>8d} s{seed}: parse median {median(times):.4f}s", flush=True)
    write_csv(RESULTS / "parse.csv", rows)


if __name__ == "__main__":
    main()
