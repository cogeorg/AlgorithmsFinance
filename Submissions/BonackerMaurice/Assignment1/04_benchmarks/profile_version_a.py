"""First profile of Version A (exploration only, not the benchmark).

Usage (from Assignment1/):
    python 04_benchmarks/profile_version_a.py

For each supplied 10,000-event file: preload the events (not profiled),
then run one plain replay on a fresh book under cProfile, and write the
top 10 functions by cumulative time to 05_results/profile_version_a.txt.
cProfile adds per-call overhead, so absolute times are inflated; use the
relative shares and the call counts.
"""

import cProfile
import io
import platform
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_code"))

import lob_a  # noqa: E402
from replay import load_events  # noqa: E402

DATA = ROOT / "00_instructions" / "data"
OUT = ROOT / "05_results" / "profile_version_a.txt"
SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]


def profile_one(events):
    book = lob_a.OrderBook()
    profiler = cProfile.Profile()
    profiler.enable()
    for event in events:
        book.process_event(event)
    profiler.disable()
    buf = io.StringIO()
    stats = pstats.Stats(profiler, stream=buf)
    stats.strip_dirs().sort_stats("cumulative").print_stats(10)
    return buf.getvalue()


def main():
    parts = [
        "Version A profile: cProfile, one replay per file, events preloaded.",
        f"Python {platform.python_version()} on {platform.platform()}",
        "Exploration only; cProfile overhead inflates absolute times.",
        "",
    ]
    for name in SCENARIOS:
        events = load_events(DATA / f"{name}_10000.jsonl.gz")
        parts.append("=" * 78)
        parts.append(f"scenario: {name}  ({len(events)} events)")
        parts.append("=" * 78)
        parts.append(profile_one(events))
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
