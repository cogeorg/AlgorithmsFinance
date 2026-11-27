"""Why memory does not bind for PriceAmericanPut, and when it would.

The slide algorithm keeps two arrays of N + 1 entries (one date at a time), so its
auxiliary space is Theta(N). A naive implementation stores the whole recombining tree:
(N + 1)(N + 2) / 2 nodes for the stock price and again for the put value, Theta(N^2).

This script measures the peak traced allocation (tracemalloc) of both storage choices
for growing N, checks that they return the same value, and extrapolates the full-tree
cost to the lab sizes (N = 8,760 and N = 43,822) from the measured bytes per node.

    python Class3/full_tree.py          # about 2 minutes; writes results/full_tree_memory.csv
"""
from __future__ import annotations

import csv
import math
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from american_put import price_american_put, price_american_put_numpy  # noqa: E402


def full_tree_python(spot, strike, up, down, gross_rate, steps):
    """Store every node: stock[t][j] and value[t][j] as lists of Python floats."""
    q = (gross_rate - down) / (up - down)
    stock = [[spot]]
    for t in range(1, steps + 1):
        prev = stock[-1]
        stock.append([prev[0] * down] + [s * up for s in prev])
    value = [None] * (steps + 1)
    value[steps] = [max(strike - s, 0) for s in stock[steps]]
    for t in range(steps - 1, -1, -1):
        nxt, row = value[t + 1], stock[t]
        value[t] = [max(strike - row[j], 0, (q * nxt[j + 1] + (1 - q) * nxt[j]) / gross_rate)
                    for j in range(t + 1)]
    return value[0][0]


def full_tree_numpy(spot, strike, up, down, gross_rate, steps):
    """Store every node in two (N + 1) x (N + 1) float64 arrays (upper half unused)."""
    import numpy as np
    q = (gross_rate - down) / (up - down)
    n = steps + 1
    stock = np.zeros((n, n))
    value = np.zeros((n, n))
    j = np.arange(n)
    for t in range(n):
        stock[t, :t + 1] = spot * up ** j[:t + 1] * down ** (t - j[:t + 1])
    value[steps] = np.maximum(strike - stock[steps], 0.0)
    for t in range(steps - 1, -1, -1):
        cont = (q * value[t + 1, 1:t + 2] + (1 - q) * value[t + 1, :t + 1]) / gross_rate
        value[t, :t + 1] = np.maximum(strike - stock[t, :t + 1], cont)
    return float(value[0, 0])


ENGINES = {
    ("python", "full tree"): full_tree_python,
    ("python", "two arrays"): price_american_put,
    ("numpy", "full tree"): full_tree_numpy,
    ("numpy", "two arrays"): lambda *a: price_american_put_numpy(*a)[0],
}
SIZES = {"python": (250, 500, 1000, 2000, 4000), "numpy": (250, 500, 1000, 2000, 4000, 8760)}
LAB_SIZES = (8760, 43822)


def traced_peak(func, args):
    tracemalloc.start()
    start = time.perf_counter()
    result = func(*args)
    seconds = time.perf_counter() - start
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return result, peak, seconds


def main():
    s = 0.0054                                   # BTC five-year hourly volatility
    up, down, gross = math.exp(s), math.exp(-s), math.exp(0.04 / 8760)
    rows = []
    for (engine, storage), func in ENGINES.items():
        for n in SIZES[engine]:
            args = (100.0, 100.0, up, down, gross, n)
            value, peak, seconds = traced_peak(func, args)
            nodes = (n + 1) * (n + 2) // 2
            rows.append(dict(engine=engine, storage=storage, N=n, tree_nodes=nodes,
                             value=value, peak_traced_bytes=peak,
                             bytes_per_node=peak / nodes, bytes_per_period=peak / (n + 1),
                             traced_seconds=round(seconds, 3)))
            print(f"{engine:6} {storage:10} N={n:5d} peak={peak / 2**20:9.2f} MiB "
                  f"value={value:.10f}", flush=True)
    # same value from both storage choices
    for engine in SIZES:
        for n in SIZES[engine]:
            v = {r["storage"]: r["value"] for r in rows if r["engine"] == engine and r["N"] == n}
            assert math.isclose(v["full tree"], v["two arrays"], rel_tol=1e-9), (engine, n, v)

    out = HERE / "results" / "full_tree_memory.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\nExtrapolation from the largest measured N (one asset):")
    for engine in SIZES:
        for storage in ("full tree", "two arrays"):
            last = [r for r in rows if r["engine"] == engine and r["storage"] == storage][-1]
            for n in LAB_SIZES:
                if storage == "full tree":
                    est = last["bytes_per_node"] * (n + 1) * (n + 2) / 2
                else:
                    est = last["bytes_per_period"] * (n + 1)
                print(f"  {engine:6} {storage:10} N={n:6d}: ~{est / 2**30:8.3f} GiB")


if __name__ == "__main__":
    main()
