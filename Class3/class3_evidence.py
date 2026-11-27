#!/usr/bin/env python3
"""Class 3 evidence: validate, time, profile and plot the four Class 3 procedures.

Usage (Python 3.9+):
    python3 class3_evidence.py --validate-only   # correctness checks only, standard library
    python3 class3_evidence.py                   # full run; plotting needs matplotlib
    python3 class3_evidence.py --replot          # redraw figures from saved CSV files

Outputs go to the folder given by --out (default: output/ beside this script).
Timings depend on your machine; compare growth ratios, not absolute times.
"""
from __future__ import annotations

import argparse
import cProfile
import csv
from datetime import datetime, timezone
from fractions import Fraction
from functools import lru_cache
import gc
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import pstats
import random
import statistics
import sys
import time
import tracemalloc

OUT = Path(__file__).resolve().parent / "output"


def fill_market_sell(book, quantity):
    """Read descending (price, available quantity) levels; return sparse fills."""
    remaining, proceeds, fills = quantity, 0, []
    for i, (price, available) in enumerate(book, 1):
        if remaining == 0:
            break
        taken = min(remaining, available)
        fills.append((i, taken))
        remaining -= taken
        proceeds += price * taken
    return fills, remaining, proceeds


def price_american_put(spot, strike, up, down, gross_rate, steps):
    """Two rolling arrays, exactly the ascending-index slide algorithm."""
    probability = (gross_rate - down) / (up - down)
    stock = [spot] * (steps + 1)
    for _ in range(steps):
        stock[0] *= down
    for j in range(1, steps + 1):
        stock[j] = stock[j - 1] * up / down
    value = [max(strike - s, 0) for s in stock]
    for t in range(steps - 1, -1, -1):
        for j in range(t + 1):
            stock[j] /= down
            continuation = (probability * value[j + 1]
                            + (1 - probability) * value[j]) / gross_rate
            value[j] = max(strike - stock[j], 0, continuation)
    return value[0]


def random_partition(records, left, right, rng):
    """Lomuto partition; records have distinct (loss, scenario number) keys."""
    k = rng.randrange(left, right + 1)
    records[k], records[right] = records[right], records[k]
    pivot, i = records[right], left
    for j in range(left, right):
        if records[j] < pivot:
            records[i], records[j] = records[j], records[i]
            i += 1
    records[i], records[right] = records[right], records[i]
    return i


def randomized_quick_sort(records, left, right, rng):
    if left < right:
        k = random_partition(records, left, right, rng)
        randomized_quick_sort(records, left, k - 1, rng)
        randomized_quick_sort(records, k + 1, right, rng)


def draw_toy_loss(rng):
    u = rng.random()
    if u < 0.5:
        return 0
    if u < 0.8:
        return 4
    return 12


def estimate_mean_loss(draw, samples):
    total = 0
    for _ in range(samples):
        total += draw()
    return total / samples


def recursive_put_oracle(spot, strike, up, down, gross_rate, steps):
    """Independent exponential exercise-decision tree; exact fractions in checks."""
    exercise = max(strike - spot, 0)
    if steps == 0:
        return exercise
    q = (gross_rate - down) / (up - down)
    continuation = (
        q * recursive_put_oracle(spot * up, strike, up, down, gross_rate, steps - 1)
        + (1 - q) * recursive_put_oracle(
            spot * down, strike, up, down, gross_rate, steps - 1)
    ) / gross_rate
    return max(exercise, continuation)


class RankChoices:
    def __init__(self, choices):
        self.choices = iter(choices)

    def randrange(self, left, stop):
        return left + next(self.choices) % (stop - left)


def counted_quicksort(records, rng):
    """Separate instrumentation so measurements time the uninstrumented version."""
    comparisons, peak_depth = 0, 0

    def visit(left, right, depth):
        nonlocal comparisons, peak_depth
        peak_depth = max(peak_depth, depth)
        if left >= right:
            return
        comparisons += right - left
        k = random_partition(records, left, right, rng)
        visit(left, k - 1, depth + 1)
        visit(k + 1, right, depth + 1)
    visit(0, len(records) - 1, 1)
    return comparisons, peak_depth


def validate():
    # Exhaustive integer fills give an independent linear-program optimum here.
    greedy_cases = 0
    for n in range(5):
        for prices in itertools.combinations_with_replacement(range(1, 4), n):
            prices = tuple(reversed(prices))
            for capacities in itertools.product((1, 2), repeat=n):
                book = list(zip(prices, capacities))
                for quantity in range(sum(capacities) + 2):
                    expected_qty = min(quantity, sum(capacities))
                    candidates = (x for x in itertools.product(
                        *(range(a + 1) for a in capacities)) if sum(x) == expected_qty)
                    optimum = max(sum(p * x for p, x in zip(prices, xs))
                                  for xs in candidates)
                    before = list(book)
                    fills, remaining, proceeds = fill_market_sell(book, quantity)
                    assert book == before and remaining == quantity - expected_qty
                    assert sum(x for _, x in fills) == expected_qty
                    assert proceeds == optimum
                    greedy_cases += 1
    assert fill_market_sell([(60000, 2), (59900, 3), (59700, 5)], 6) == (
        [(1, 2), (2, 3), (3, 1)], 0, 359400)
    assert fill_market_sell([(10, 1)], Fraction(1, 2))[2] == 5

    put_cases = 0
    for steps, spot, strike, gross in itertools.product(
            range(7), (60, 100, 140), (80, 100, 120),
            (Fraction(19, 20), Fraction(1), Fraction(21, 20))):
        args = (Fraction(spot), Fraction(strike), Fraction(6, 5),
                Fraction(4, 5), gross, steps)
        assert price_american_put(*args) == recursive_put_oracle(*args)
        put_cases += 1
    toy_put = price_american_put(Fraction(100), Fraction(100), Fraction(6, 5),
                                 Fraction(4, 5), Fraction(21, 20), 2)
    assert toy_put == Fraction(1175, 147)

    sort_cases = 0
    for n in range(7):
        for losses in itertools.product((-1, 0, 1), repeat=n):
            records = [(v, i) for i, v in enumerate(losses, 1)]
            for seed in (0, 1, 19):
                actual = list(records)
                randomized_quick_sort(actual, 0, n - 1, random.Random(seed))
                assert actual == sorted(records)
                sort_cases += 1
    # Average over every pivot and both actual partition outputs recursively.
    # Fractions retain exact conditional path probabilities.
    @lru_cache(maxsize=None)
    def exact_expected_cost(keys):
        if len(keys) <= 1:
            return Fraction(0)
        total = Fraction(0)
        for k in range(len(keys)):
            actual = list(keys)
            b = random_partition(actual, 0, len(actual) - 1, RankChoices([k]))
            total += (len(keys) - 1 + exact_expected_cost(tuple(actual[:b]))
                      + exact_expected_cost(tuple(actual[b + 1:])))
        return total / len(keys)

    expected_comparisons = {}
    for n in range(2, 7):
        weighted = exact_expected_cost(tuple((i, i) for i in range(n)))
        h = sum((Fraction(1, j) for j in range(1, n + 1)), Fraction(0))
        exact = 2 * (n + 1) * h - 4 * n
        assert weighted == exact
        expected_comparisons[str(n)] = str(exact)

    class EndPivot:
        def randrange(self, left, stop):
            return stop - 1
    for n in range(1, 33):
        records = [(i, i) for i in range(n)]
        comparisons, depth = counted_quicksort(records, EndPivot())
        assert comparisons == n * (n - 1) // 2
        assert depth == n

    class UniformSequence:
        def __init__(self, values):
            self.values = iter(values)

        def random(self):
            return next(self.values)
    rng = UniformSequence([0., .499, .5, .799, .8, .999])
    assert [draw_toy_loss(rng) for _ in range(6)] == [0, 0, 4, 4, 12, 12]
    rng = UniformSequence([.1, .6, .9, .2, .7])
    assert estimate_mean_loss(lambda: draw_toy_loss(rng), 5) == 4

    outcomes = ((0, Fraction(1, 2)), (4, Fraction(3, 10)), (12, Fraction(1, 5)))
    mu = sum(v * p for v, p in outcomes)
    variance = sum(p * (v - mu) ** 2 for v, p in outcomes)
    mean_cases = 0
    for m in range(1, 6):
        expectation = Fraction(0)
        mean_variance = Fraction(0)
        for sample in itertools.product(outcomes, repeat=m):
            values, probabilities = zip(*sample)
            iterator = iter(values)
            actual = estimate_mean_loss(lambda: Fraction(next(iterator)), m)
            weight = math.prod(probabilities)
            expectation += weight * actual
            mean_variance += weight * (actual - mu) ** 2
            mean_cases += 1
        assert expectation == mu and mean_variance == variance / m
    assert mu == Fraction(18, 5) and variance == Fraction(516, 25)
    return {"greedy_oracle_cases": greedy_cases, "put_exact_tree_cases": put_cases,
            "sort_cases": sort_cases, "exact_mean_sample_sequences": mean_cases,
            "quicksort_exact_expected_comparisons": expected_comparisons,
            "toy_put": str(toy_put), "toy_mean": str(mu), "toy_variance": str(variance)}


def measure(factory, repeats=7, batch=1):
    """factory prepares one call outside timing/tracing; retain returned output."""
    factory()()  # warm-up
    samples = []
    for _ in range(repeats):
        calls = [factory() for _ in range(batch)]
        start = time.perf_counter()
        for call in calls:
            result = call()
        elapsed = time.perf_counter() - start
        samples.append(elapsed / batch)
        del result, calls
    gc.collect()
    call = factory()
    tracemalloc.start()
    result = call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del result
    return statistics.median(samples), peak


def benchmark():
    rows, seed_rows, accuracy = [], [], []
    for n in (256, 512, 1024, 2048, 4096):
        book = [(100000 - i, 1) for i in range(n)]
        factory = lambda: lambda: fill_market_sell(book, n)
        seconds, peak = measure(factory, batch=10)
        rows.append(dict(algorithm="FillMarketSell", size=n, seconds=seconds,
                         peak_bytes=peak, work=n))
    for n in (32, 64, 128, 256, 512):
        # Fixed two-year maturity, 20% volatility, 5% continuously compounded rate.
        dt = 2 / n
        up, down, gross = math.exp(.2 * math.sqrt(dt)), math.exp(-.2 * math.sqrt(dt)), math.exp(.05 * dt)
        factory = lambda: lambda: price_american_put(100., 100., up, down, gross, n)
        seconds, peak = measure(factory, batch=1)
        rows.append(dict(algorithm="PriceAmericanPut", size=n, seconds=seconds,
                         peak_bytes=peak, work=n * (n + 1) // 2))
    for n in (256, 512, 1024, 2048, 4096):
        for order in ("ascending", "descending", "shuffled"):
            records = [(i, i) for i in range(n)]
            if order == "descending":
                records.reverse()
            elif order == "shuffled":
                random.Random(314159).shuffle(records)
            for seed in range(21):
                def factory():
                    a, rng = list(records), random.Random(seed)
                    return lambda: randomized_quick_sort(a, 0, len(a) - 1, rng)
                seconds, peak = measure(factory, repeats=3)
                a = list(records)
                comparisons, depth = counted_quicksort(a, random.Random(seed))
                seed_rows.append(dict(size=n, order=order, seed=seed, seconds=seconds,
                                      peak_bytes=peak, comparisons=comparisons, depth=depth))
        selected = [r for r in seed_rows if r["size"] == n and r["order"] == "ascending"]
        rows.append(dict(algorithm="RandomizedQuickSort", size=n,
                         seconds=statistics.median(r["seconds"] for r in selected),
                         peak_bytes=statistics.median(r["peak_bytes"] for r in selected),
                         work=statistics.mean(r["comparisons"] for r in selected)))
    for m in (256, 1024, 4096, 16384, 65536):
        def factory():
            rng = random.Random(2026)
            return lambda: estimate_mean_loss(lambda: draw_toy_loss(rng), m)
        seconds, peak = measure(factory, batch=3)
        rows.append(dict(algorithm="EstimateMeanLoss", size=m, seconds=seconds,
                         peak_bytes=peak, work=m))
        for seed in range(200):
            rng = random.Random(seed)
            estimate = estimate_mean_loss(lambda: draw_toy_loss(rng), m)
            accuracy.append(dict(samples=m, seed=seed, estimate=estimate,
                                 error=estimate - 3.6))
    return rows, seed_rows, accuracy


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(rows, seeds, accuracy):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 16, "xtick.labelsize": 14,
                         "ytick.labelsize": 14, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42,
                         "text.color": "#2C3E50", "axes.labelcolor": "#2C3E50"})
    teal, amber, coral = "#1B4D5C", "#D4A84B", "#C0534D"

    def axis_style(ax):
        ax.set_xscale("log", base=2)
        ax.set_yscale("log", base=2)
        ax.grid(alpha=.16)

    for algorithm, exponent in (("FillMarketSell", 1), ("PriceAmericanPut", 2),
                                ("EstimateMeanLoss", 1)):
        selected = [r for r in rows if r["algorithm"] == algorithm]
        xs, ys = [r["size"] for r in selected], [r["seconds"] * 1000 for r in selected]
        fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.1), layout="constrained")
        axes[0].plot(xs, ys, "o-", color=teal, label="Measured median")
        symbol = {"FillMarketSell": "n", "PriceAmericanPut": "N",
                  "EstimateMeanLoss": "m"}[algorithm]
        power = symbol if exponent == 1 else f"{symbol}^{exponent}"
        axes[0].plot(xs, [ys[0] * (x / xs[0]) ** exponent for x in xs], "--",
                     color=amber, label=f"Reference: $\\propto {power}$")
        axes[0].set(xlabel="Samples m" if algorithm == "EstimateMeanLoss" else
                    "Periods N" if algorithm == "PriceAmericanPut" else "Levels n",
                    ylabel="Time (ms)")
        axes[0].legend(fontsize=13)
        axis_style(axes[0])
        if algorithm == "EstimateMeanLoss":
            rmse = [math.sqrt(statistics.mean(r["error"] ** 2 for r in accuracy
                                            if r["samples"] == m)) for m in xs]
            axes[1].plot(xs, rmse, "o-", color=teal, label="Measured: 200 seeds")
            axes[1].plot(xs, [math.sqrt(20.64 / m) for m in xs], "--", color=amber,
                         label="Theory: standard error")
            axes[1].set(xlabel="Samples m", ylabel="Error (million dollars)")
            axes[1].legend(fontsize=13)
        else:
            axes[1].plot(xs, [r["peak_bytes"] / 1024 for r in selected], "o-", color=teal)
            axes[1].set(xlabel="Periods N" if algorithm == "PriceAmericanPut" else "Levels n",
                        ylabel="Allocation (KiB)")
        axis_style(axes[1])
        fig.savefig(OUT / (algorithm + ".pdf"))
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.1), layout="constrained")
    for order, color in (("ascending", teal), ("descending", coral), ("shuffled", amber)):
        xs = sorted({r["size"] for r in seeds})
        ys, lo, hi = [], [], []
        for n in xs:
            vals = sorted(r["comparisons"] for r in seeds if r["size"] == n and r["order"] == order)
            ys.append(statistics.median(vals)); lo.append(vals[2]); hi.append(vals[18])
        axes[0].plot(xs, ys, "o-", color=color, label=order.capitalize())
        axes[0].fill_between(xs, lo, hi, color=color, alpha=.08)
    expected = [2 * (n + 1) * sum(1 / j for j in range(1, n + 1)) - 4 * n for n in xs]
    axes[0].plot(xs, expected, "k--", linewidth=1, label="Exact expectation")
    axes[0].set(xlabel="Records n", ylabel="Key comparisons")
    axes[0].legend(fontsize=12)
    axis_style(axes[0])
    selected = [r for r in rows if r["algorithm"] == "RandomizedQuickSort"]
    ys = [r["seconds"] * 1000 for r in selected]
    axes[1].plot(xs, ys, "o-", color=teal, label="Median: ascending input")
    axes[1].plot(xs, [ys[0] * (n * math.log2(n)) / (xs[0] * math.log2(xs[0])) for n in xs],
                 "--", color=amber, label="Reference: $\\propto n\\,\\log n$")
    axes[1].set(xlabel="Records n", ylabel="Time (ms)")
    axes[1].legend(fontsize=12)
    axis_style(axes[1])
    fig.savefig(OUT / "RandomizedQuickSort.pdf")
    plt.close(fig)


def main():
    global OUT
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate-only", action="store_true",
                        help="run correctness checks only")
    parser.add_argument("--replot", action="store_true",
                        help="redraw figures from CSV files already in --out")
    parser.add_argument("--out", type=Path, default=OUT,
                        help="output folder (default: output/ beside this script)")
    args = parser.parse_args()
    OUT = args.out.resolve()
    if args.replot:
        def load(name, ints, floats):
            with (OUT / name).open(newline="") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                for k in ints: r[k] = int(r[k])
                for k in floats: r[k] = float(r[k])
            return rows
        rows = load("Measurements.csv", ["size", "peak_bytes"], ["seconds"])
        seed_rows = load("QuickSortSeeds.csv", ["size", "comparisons"], [])
        accuracy = load("MeanLossSeeds.csv", ["samples"], ["error"])
        plot(rows, seed_rows, accuracy)
        print("Figures redrawn in", OUT)
        return
    validation = validate()
    print(json.dumps(validation, indent=2))
    if args.validate_only:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    rows, seed_rows, accuracy = benchmark()
    write_csv("Measurements.csv", rows)
    write_csv("QuickSortSeeds.csv", seed_rows)
    write_csv("MeanLossSeeds.csv", accuracy)
    plot(rows, seed_rows, accuracy)
    profiler = cProfile.Profile()
    profiler.runcall(price_american_put, 100., 100., 1.02, .98, 1.001, 256)
    with (OUT / "Profile_PriceAmericanPut.txt").open("w") as f:
        pstats.Stats(profiler, stream=f).strip_dirs().sort_stats("cumulative").print_stats(12)
    stats = {}
    for name in ("FillMarketSell", "PriceAmericanPut", "RandomizedQuickSort", "EstimateMeanLoss"):
        selected = [r for r in rows if r["algorithm"] == name]
        stats[name] = {"last_time_ratio": selected[-1]["seconds"] / selected[-2]["seconds"],
                       "last_peak_bytes": selected[-1]["peak_bytes"]}
    metadata = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    python=sys.version, platform=platform.platform(),
                    machine=platform.machine(), timer=str(time.get_clock_info("perf_counter")),
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    validation=validation, summary=stats,
                    protocol="7-repeat median; quicksort 21 seeds x 3 repeats per order; "
                    "setup/copies/RNG construction outside timing; output included; "
                    "separate one-call tracemalloc and cProfile runs; warm-up before timing; "
                    "traced bytes exclude pre-existing inputs, include returned outputs, "
                    "do not measure total process/native stack memory; "
                    "MC accuracy uses 200 seeds, independent of pivot experiments.")
    (OUT / "Metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    macros = {"GreedyTimeRatio": stats["FillMarketSell"]["last_time_ratio"],
              "PutTimeRatio": stats["PriceAmericanPut"]["last_time_ratio"],
              "QuickTimeRatio": stats["RandomizedQuickSort"]["last_time_ratio"],
              "MeanTimeRatio": stats["EstimateMeanLoss"]["last_time_ratio"]}
    text = "% Generated by class3_evidence.py; see Metadata.json.\n"
    text += "".join("\\newcommand{\\" + key + "}{" + f"{value:.2f}" + "}\n"
                    for key, value in macros.items())
    (OUT / "SlideMetrics.tex").write_text(text)
    print("Evidence written to", OUT)


if __name__ == "__main__":
    main()
