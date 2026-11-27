"""Class 3 lab driver: price at-the-money American puts on hourly market data.

One invocation is one run: it loads, calibrates and prices every requested asset in
one process, then prints a JSON summary (N, number of assets, seconds, memory).

Examples (from Submissions/WelscherYannick):
    python Class3/lab.py --assets BTCUSDT --horizon 1y            # Tasks 2 and 3
    python Class3/lab.py --assets BTCUSDT --horizon 5y            # Task 4
    python Class3/lab.py --assets all --horizon 1y --engine numpy # Task 5
    python Class3/lab.py --assets all --horizon 5y --trace-memory # Task 6, memory run

Measurement protocol (as in Class3/class3_evidence.py):
- seconds_total: time.perf_counter around load + window + calibration + pricing +
  exercise check for all assets; writing output files is outside the timing.
- seconds_pricing: the pricing calls alone.
- peak_traced_bytes: tracemalloc peak over the same work, measured in a separate run
  (--trace-memory) because tracing slows pure Python down. NumPy reports its array
  allocations to tracemalloc, so both engines are traced.
- max_rss_bytes: peak resident set size of the whole process (interpreter, imports,
  data), from getrusage; recorded in every run.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import resource
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from american_put import price_american_put_numpy, price_american_put_with_boundary  # noqa: E402
from calibrate import (  # noqa: E402
    ONE_YEAR_STEPS,
    available_symbols,
    calibrate,
    first_exercise,
    last_window,
    load_series,
)

ENGINES = {"python": price_american_put_with_boundary, "numpy": price_american_put_numpy}
HORIZONS = {"1y": ONE_YEAR_STEPS, "5y": None}        # 5y = the full file (at most five years)

ASSET_FIELDS = [
    "symbol", "N", "start_utc", "end_utc", "T_years", "S0_K", "s_hourly", "u", "d", "R", "q",
    "put_value", "put_pct_of_spot", "boundary_dates", "P_N",
    "exercise_t", "exercise_utc", "exercise_price", "exercise_boundary", "exercise_payoff",
]


def max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024     # Linux reports KiB


def price_one(symbol: str, steps, engine):
    window = last_window(load_series(symbol), steps)
    params = calibrate(window)
    t0 = time.perf_counter()
    value, boundary = engine(*params.pricing_args())
    pricing = time.perf_counter() - t0
    hit = first_exercise(window, params.strike, boundary)
    row = {
        "symbol": symbol, "N": params.steps,
        "start_utc": window.timestamps[0].strftime("%Y-%m-%dT%H:%MZ"),
        "end_utc": window.timestamps[-1].strftime("%Y-%m-%dT%H:%MZ"),
        "T_years": params.years, "S0_K": params.spot, "s_hourly": params.sigma,
        "u": params.up, "d": params.down, "R": params.gross_rate, "q": params.q,
        "put_value": value, "put_pct_of_spot": 100 * value / params.spot,
        "boundary_dates": sum(b is not None for b in boundary), "P_N": window.closes[-1],
        "exercise_t": hit.t if hit else "never",
        "exercise_utc": hit.timestamp.strftime("%Y-%m-%dT%H:%MZ") if hit else "never",
        "exercise_price": hit.price if hit else "",
        "exercise_boundary": hit.boundary if hit else "",
        "exercise_payoff": hit.payoff if hit else "",
    }
    return row, window, boundary, pricing


def run(symbols, horizon, engine_name, trace_memory, keep_boundary):
    engine = ENGINES[engine_name]
    steps = HORIZONS[horizon]
    if trace_memory:
        tracemalloc.start()
    rows, kept, pricing_total = [], {}, 0.0
    t0 = time.perf_counter()
    for symbol in symbols:
        row, window, boundary, pricing = price_one(symbol, steps, engine)
        rows.append(row)
        pricing_total += pricing
        if keep_boundary:
            kept[symbol] = (window, boundary)
        del window, boundary                    # one asset in memory at a time
    seconds = time.perf_counter() - t0
    peak = tracemalloc.get_traced_memory()[1] if trace_memory else None
    if trace_memory:
        tracemalloc.stop()
    summary = {
        "engine": engine_name, "horizon": horizon, "assets": len(symbols),
        "N": sorted({r["N"] for r in rows}), "seconds_total": seconds,
        "seconds_pricing": pricing_total, "trace_memory": trace_memory,
        "peak_traced_bytes": peak, "max_rss_bytes": max_rss_bytes(),
        "python": platform.python_version(),
    }
    return summary, rows, kept


def write_assets(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ASSET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_boundary(path: Path, window, boundary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t", "timestamp_utc", "close_P_t", "boundary"])
        for t, (stamp, close, edge) in enumerate(zip(window.timestamps, window.closes, boundary)):
            writer.writerow([t, stamp.strftime("%Y-%m-%dT%H:%MZ"), close,
                             "" if edge is None else repr(edge)])


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", default="BTCUSDT",
                        help="'all' or a comma-separated list of symbols")
    parser.add_argument("--horizon", choices=HORIZONS, default="1y")
    parser.add_argument("--engine", choices=ENGINES, default="python")
    parser.add_argument("--trace-memory", action="store_true")
    parser.add_argument("--assets-out", type=Path, help="per-asset results CSV")
    parser.add_argument("--boundary-dir", type=Path,
                        help="write <symbol>_<horizon>_boundary.csv for every asset")
    parser.add_argument("--summary-out", type=Path, help="append the JSON summary here")
    args = parser.parse_args(argv)

    symbols = available_symbols() if args.assets == "all" else args.assets.split(",")
    summary, rows, kept = run(symbols, args.horizon, args.engine, args.trace_memory,
                              keep_boundary=args.boundary_dir is not None)
    if args.assets_out:
        write_assets(args.assets_out, rows)
    for symbol, (window, boundary) in kept.items():
        write_boundary(args.boundary_dir / f"{symbol}_{args.horizon}_boundary.csv", window, boundary)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_out.open("a") as handle:
            handle.write(json.dumps(summary) + "\n")
    print(json.dumps(summary))
    if len(rows) <= 3:
        for row in rows:
            print(json.dumps(row))
    return summary


if __name__ == "__main__":
    main()
