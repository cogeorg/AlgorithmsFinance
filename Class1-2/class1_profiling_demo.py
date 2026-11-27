1
"""Class 1: three specified algorithms, unprofiled scaling, separate profiles.

Run from the course root:
    python3 50_code/Class1-2/class1_profiling_demo.py
When this repository is linked as 50_code/, figures are written to
10_overleaf/figures/Class1_Performance/. Only figure export requires Matplotlib.
All other work uses the standard library.
Python positions start at zero; returned duplicate pairs use the slides' one-based
positions. Input generation and correctness checks are outside timed regions.
"""
import cProfile
import csv
import io
import json
import platform
import pstats
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns


def contains(items, query):
    """Membership by linear scan; input is unchanged."""
    i = 0
    n = len(items)
    while i < n:
        if items[i] == query:
            return True
        i += 1
    return False


def max_loss(losses):
    """Maximum of a nonempty array of integer losses; input is unchanged."""
    if not losses:
        raise ValueError("max_loss requires a nonempty loss array")
    maximum = losses[0]
    i = 1
    n = len(losses)
    while i < n:
        if losses[i] > maximum:
            maximum = losses[i]
        i += 1
    return maximum


def duplicate_pairs(items):
    """All equal-value position pairs, ordered by first then second position."""
    result = []
    n = len(items)
    i = 0
    while i < n - 1:
        j = i + 1
        while j < n:
            if items[i] == items[j]:
                result.append((i + 1, j + 1))
            j += 1
        i += 1
    return result


def answer_queries(items, queries):
    """Class 2 extension: one Boolean per query, preserving query order."""
    return [contains(items, query) for query in queries]


def validate_examples():
    for items, query, expected in [
        ([], 4, False), ([4], 4, True), ([4], 5, False),
        ([7, 11], 7, True), ([7, 11], 11, True), ([7, 11], 9, False),
        ([7, 11, 7], 11, True), ([7, 11, 7], 9, False)
    ]:
        before = items.copy()
        assert contains(items, query) is expected
        assert items == before
    for losses, expected in [([-4, 6, 2], 6), ([-4, -2], -2),
                             ([3], 3), ([5, 5], 5), ([9, 2, 1], 9)]:
        before = losses.copy()
        assert max_loss(losses) == expected
        assert losses == before
    try:
        max_loss([])
    except ValueError:
        pass
    else:
        raise AssertionError("Empty maximum input must be rejected")
    for items, expected in [([], []), ([7], []), ([7, 11], []),
                            ([7, 11, 7], [(1, 3)]),
                            ([7, 7, 7], [(1, 2), (1, 3), (2, 3)]),
                            ([7, 11, 7, 11], [(1, 3), (2, 4)])]:
        before = items.copy()
        assert duplicate_pairs(items) == expected
        assert items == before
    assert answer_queries([7, 11, 7], [11, 9, 7]) == [True, False, True]
    assert answer_queries([], []) == []


def run_batch(function, args, executions):
    result = None
    for _ in range(executions):
        result = function(*args)
    return result


def figures_output_dir():
    """Write into the Overleaf tree when this repo is linked as 50_code/."""
    here = Path(__file__)
    course_figures = here.parent.parent.parent / "10_overleaf" / "figures" / "Class1_Performance"
    if (here.parent.parent.parent / "10_overleaf").is_dir():
        course_figures.mkdir(parents=True, exist_ok=True)
        return course_figures
    fallback = here.resolve().parent / "figures" / "Class1_Performance"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    validate_examples()
    out = figures_output_dir()
    workloads = [
        ("Membership", contains, [1000, 2000, 4000, 8000, 16000, 32000, 64000],
         100, 1, lambda n: ((list(range(n)), -1), False),
         "A=(0,...,n-1), x=-1; one absent membership query per execution"),
        ("Maximum", max_loss, [1000, 2000, 4000, 8000, 16000, 32000, 64000],
         100, 1, lambda n: (([(-4, 6, 2)[i % 3] for i in range(n)],), 6),
         "L repeats (-4,6,2), truncated at n; one maximum per execution"),
        ("DuplicatePairs", duplicate_pairs, [100, 200, 400, 800, 1600, 3200],
         1, 2, lambda n: ((list(range(n)),), []),
         "A=(0,...,n-1); distinct IDs; empty output; every pair still checked")
    ]
    rows, raw, profiles, macros = [], [], {}, []
    plt.rcParams.update({"font.size": 13, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42})
    for name, function, sizes, executions, power, factory, description in workloads:
        series = []
        for n in sizes:
            args, expected = factory(n)  # Preparation is excluded.
            assert function(*args) == expected  # Preflight check, also excluded.
            run_batch(function, args, executions)  # Designated untimed warm-up.
            samples = []
            for _ in range(7):
                start = perf_counter_ns()
                result = run_batch(function, args, executions)
                elapsed_ms = (perf_counter_ns() - start) / 1e6
                samples.append(elapsed_ms)
                assert result == expected  # After the ending clock reading.
            per_execution = [sample / executions for sample in samples]
            row = {"example": name, "n": n, "executions_per_repeat": executions,
                   "median_ms": statistics.median(per_execution),
                   "min_ms": min(per_execution), "max_ms": max(per_execution)}
            rows.append(row)
            series.append(row)
            raw.append({"example": name, "n": n, "executions_per_repeat": executions,
                        "batch_times_ms": samples})
        # Profiling is a different run after all timings for this example.
        profiler = cProfile.Profile()
        profiler.runcall(run_batch, function, args, executions)
        buffer = io.StringIO()
        stats = pstats.Stats(profiler, stream=buffer).sort_stats("cumulative")
        stats.print_stats(10)
        (out / f"Profile_{name}.txt").write_text(buffer.getvalue())
        entries = [(key, value) for key, value in stats.stats.items()
                   if key[2] == function.__name__]
        assert len(entries) == 1
        _, (_, calls, own_seconds, cumulative_seconds, _) = entries[0]
        profiles[name] = {"n": sizes[-1], "function": function.__name__, "calls": calls,
                          "own_ms": own_seconds * 1000,
                          "cumulative_ms": cumulative_seconds * 1000,
                          "workload": description}
        for suffix, value in [("ProfileCalls", str(calls)),
                              ("ProfileMs", f"{own_seconds * 1000:.2f}"),
                              ("EndMs", f"{series[-1]['median_ms']:.3f}"),
                              ("Doubling", f"{series[-1]['median_ms']/series[-2]['median_ms']:.2f}")]:
            macros.append("\\newcommand{\\" + name + suffix + "}{" + value + "}")
        ns = [row["n"] for row in series]
        medians = [row["median_ms"] for row in series]
        reference = [medians[0] * (n / ns[0]) ** power for n in ns]
        fig, ax = plt.subplots(figsize=(7.3, 3.0), layout="constrained")
        ax.plot(ns, medians, "o-", color="#1B4D5C", label="Measured median")
        label = ("Linear" if power == 1 else "Quadratic") + " reference (anchored)"
        ax.plot(ns, reference, "--", color="#B58226", label=label)
        ax.set_xlabel("Input length n")
        ax.set_ylabel("Milliseconds per execution")
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.ticklabel_format(axis="both", style="plain", useOffset=False)
        ax.grid(alpha=0.15)
        ax.legend(frameon=False, loc="upper left")
        fig.savefig(out / f"{name}.pdf")
        plt.close(fig)
    with (out / "Measurements.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    metadata = {"measured_utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version, "platform": platform.platform(),
                "protocol": "Preflight check and designated warm-up excluded; seven unprofiled batches; elapsed time divided by executions per batch; report median; input preparation and validation excluded; output construction included; separate diagnostic profile",
                "workloads": {name: description for name, _, _, _, _, _, description in workloads},
                "raw_samples": raw, "profiles": profiles}
    (out / "Metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "SlideMetrics.tex").write_text("% Generated by class1_profiling_demo.py\n" + "\n".join(macros) + "\n")
    print(json.dumps({"output": str(out), "profiles": profiles, "measurements": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
