"""cProfile of one replay per version (diagnostic only; profiling adds overhead, so these
numbers are never used as timings). Run:  python -m bench.profile_run

Writes results/profile_<version>_<scenario>_<events>.txt with the functions sorted by
own time (tottime) and cumulative time.
"""
import cProfile
import io
import pstats

from lob.events_io import read_events

from .common import RESULTS, VERSIONS, dataset, replay

RUNS = [("buildup", 10_000), ("sweep", 10_000), ("cancel_churn", 10_000)]


def main():
    RESULTS.mkdir(exist_ok=True)
    for scenario, m in RUNS:
        events = read_events(dataset(scenario, m, 42))
        for name, make in VERSIONS.items():
            book = make()
            prof = cProfile.Profile()
            prof.runcall(replay, book, events)
            out = io.StringIO()
            stats = pstats.Stats(prof, stream=out)
            out.write(f"cProfile, version {name}, {scenario}, {m} events, seed 42\n")
            out.write("Own time (tottime) excludes called functions; cumulative time includes them.\n\n")
            stats.sort_stats("tottime").print_stats(12)
            stats.sort_stats("cumulative").print_stats(12)
            path = RESULTS / f"profile_{name}_{scenario}_{m}.txt"
            path.write_text(out.getvalue())
            print(f"saved {path.name}")


if __name__ == "__main__":
    main()
