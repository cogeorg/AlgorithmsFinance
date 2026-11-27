"""cProfile both versions on two supplied sample streams and save the heaviest functions.

    python profile_run.py

Profiling is diagnostic only: the profiler slows Python-level calls far more than
C-level work, so these times are not comparable with the benchmark timings.
"""
import argparse
import cProfile
import json
from pathlib import Path
import pstats

from book_a import OrderBookA
from book_b import OrderBookB
from events import read_events

HERE = Path(__file__).resolve().parent
BOOKS = {"A": OrderBookA, "B": OrderBookB}
WORKLOADS = ("buildup_10000.jsonl.gz", "mixed_10000.jsonl.gz")


def profile(cls, events, top):
    book = cls()
    process = book.ProcessEvent
    profiler = cProfile.Profile()
    profiler.enable()
    for event in events:
        process(event)
    profiler.disable()
    stats = pstats.Stats(profiler)
    rows = []
    for (filename, line, name), (_, calls, own, cumulative, _) in stats.stats.items():
        where = name if filename == "~" else f"{Path(filename).name}:{line} {name}"
        rows.append({"function": where, "calls": calls, "own_seconds": own, "cumulative_seconds": cumulative})
    rows.sort(key=lambda r: r["own_seconds"], reverse=True)
    return {"total_seconds": stats.total_tt, "top": rows[:top]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "results" / "profile.json")
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    runs = []
    for name in WORKLOADS:
        events = read_events(HERE / "data" / name)
        for version, cls in BOOKS.items():
            runs.append({"version": version, "workload": name, **profile(cls, events, args.top)})
            best = runs[-1]["top"][0]
            print(f"{version} {name}: {runs[-1]['total_seconds']:.3f} s profiled; heaviest: {best['function']} "
                  f"({best['own_seconds'] / runs[-1]['total_seconds']:.0%} of own time)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"tool": "cProfile", "runs": runs}, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
