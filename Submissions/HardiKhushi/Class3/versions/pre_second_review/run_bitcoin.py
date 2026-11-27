"""Price one Bitcoin window, record its exercise path and measure the run."""

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from math import isfinite
from pathlib import Path
import platform
import sys
from time import perf_counter
import tracemalloc

from exercise import first_exercise
from market_data import DEFAULT_DATA, HERE, calibration_report, calibrate_window, load_price_window
from price_american_put import price_american_put
from tree_model import validate_tree


SOURCES = ("run_bitcoin.py", "price_american_put.py", "price_american_put_numpy.py", "tree_model.py", "market_data.py", "exercise.py")


def source_hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCES}


def save_json(path, contents):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(contents, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run(data, periods, output, engine="python"):
    if engine == "numpy":
        import numpy as np
        from price_american_put_numpy import price_american_put as pricer
        numpy_version = np.__version__
    elif engine == "python":
        pricer = price_american_put
        numpy_version = None
    else:
        raise ValueError("engine must be python or numpy")
    output = Path(output).resolve()
    if not output.is_relative_to(HERE):
        raise ValueError("output must stay inside this submission's Class3 folder")
    if output.exists():
        raise FileExistsError(f"refusing to replace existing results: {output}")
    window = load_price_window(data, periods)
    model = calibrate_window(window)
    args = (model.spot, model.strike, model.up, model.down, model.gross_rate, model.steps)
    validate_tree(*args)  # Fail before creating an incomplete results directory.
    asset = window.source.stem
    hashes = source_hashes()
    output.mkdir(parents=True)
    save_json(output / "inputs.json", calibration_report(window, model))

    print(f"Pricing {model.steps:,} periods, one asset, engine={engine}, with an exercise boundary...", flush=True)
    gc.collect()
    start = perf_counter()
    price, boundary = pricer(*args, return_boundary=True)
    seconds = perf_counter() - start
    if not isfinite(price) or not 0 <= price <= model.strike:
        raise ArithmeticError("option value is not finite or violates positive-rate put bounds")
    if any(b is not None and (not isfinite(b) or not 0 < b < model.strike) for b in boundary):
        raise ArithmeticError("invalid exercise threshold")
    crossing = first_exercise(window, boundary, model.strike)
    save_json(output / "timing.json", {
        "seconds": seconds, "put_value": price, "first_exercise": crossing,
        "repeats": 1, "tracing_enabled": False,
    })
    with (output / "boundary.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("t", "timestamp_utc", "observed_close", "exercise_boundary", "at_or_below_boundary"))
        for t, (timestamp, observed, threshold) in enumerate(zip(window.timestamps, window.prices, boundary)):
            writer.writerow((
                t, timestamp.isoformat(), observed, "" if threshold is None else threshold,
                int(threshold is not None and observed <= threshold),
            ))
    print(f"Put value: {price:.8f} USDT/BTC; untraced seconds: {seconds:.6f}", flush=True)
    print(f"First observed crossing: {crossing if crossing else 'never'}", flush=True)
    print("Measuring allocations in a separate pricing call...", flush=True)

    # Keep inputs and the first result outside tracing. The second call creates
    # fresh working arrays and output; read its allocations before deleting it.
    gc.collect()
    tracemalloc.start()
    start = perf_counter()
    try:
        traced_price, traced_boundary = pricer(*args, return_boundary=True)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        memory_seconds = perf_counter() - start
        tracemalloc.stop()
    if traced_price != price or traced_boundary != boundary:
        raise ArithmeticError("timing and memory calls disagree")
    save_json(output / "memory.json", {
        "current_traced_bytes": current, "peak_traced_bytes": peak,
        "instrumented_call_seconds": memory_seconds, "repeats": 1,
        "agrees_with_timing_call": True,
    })
    if hashes != source_hashes():
        raise RuntimeError("source code changed during this run")

    with (output / "summary.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("asset", "engine", "N", "assets", "seconds", "peak_traced_bytes", "put_value", "exercise_utc", "payoff"))
        writer.writerow((
            asset, engine, model.steps, 1, seconds, peak, price,
            crossing["timestamp_utc"] if crossing else "never",
            crossing["payoff"] if crossing else "",
        ))
    result = {
        "status": "complete", "completed_utc": datetime.now(timezone.utc).isoformat(),
        "asset": asset, "assets": 1, "engine": engine, "numpy_version": numpy_version, "model": asdict(model),
        "put_value": price, "first_exercise": crossing, "seconds": seconds,
        "peak_traced_bytes": peak, "peak_traced_KiB": peak / 1024,
        "boundary_entries": len(boundary), "python": sys.version,
        "platform": platform.platform(), "source_sha256": hashes,
        "data_sha256": window.source_sha256,
        "protocol": {
            "timing": "one perf_counter call; includes tree arrays, boundary and numerical-range checks; excludes CSV loading, calibration, path comparison and output files",
            "memory": "separate fresh tracemalloc call; includes new arrays, boundary and output; excludes pre-existing inputs and first-call output; not process RSS",
            "boundary": "highest positive-payoff tree node; strict exercise >= continuation except indifference tolerance at R=1; no early exercise at R<1",
            "tolerance": "payoff noise cutoff=32 * float epsilon * strike, no absolute floor; tie tolerance only at R=1; price always max(exercise, continuation)",
            "node_prices": "reconstructed from log prices each row; when down == 1/up, enforce exact reciprocal log moves and exact central ATM nodes",
            "expiry": "highest positive-payoff tree node, using the same tolerance; no interpolation to strike",
            "path_comparison": "first observed P[t] <= boundary[t], including expiry; calibration uses the full window in hindsight; payoff excludes initial premium",
            "samples": "one timing call and one separate memory call; no medians or confidence intervals",
        },
    }
    result["result_file_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.iterdir()) if path.is_file()
    }
    save_json(output / "result.json", result)
    print(f"Complete. Peak traced allocation: {peak:,} bytes ({peak / 1024:.2f} KiB)", flush=True)
    print(f"Results: {output}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--periods", type=int, default=8760)
    selection.add_argument("--full-file", action="store_true")
    parser.add_argument("--engine", choices=("python", "numpy"), default="python")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        horizon = "full" if args.full_file else "1y" if args.periods == 8760 else str(args.periods)
        prefix = 'bitcoin' if args.data.stem == 'BTCUSDT' else args.data.stem.lower()
        output = args.output or HERE / "results" / f"{prefix}_{horizon}_{args.engine}"
        run(args.data, None if args.full_file else args.periods, output, args.engine)
    except (ValueError, OSError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
