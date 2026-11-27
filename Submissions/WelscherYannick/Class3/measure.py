"""Task 6: run every configuration in a fresh process and tabulate the measurements.

Suites (each run is a separate `python Class3/lab.py ...` subprocess):
  time    seconds and max RSS, no tracing; also writes the per-asset result CSVs
  memory  the same runs with tracemalloc (peak traced allocations)

Usage (from Submissions/WelscherYannick):
    python Class3/measure.py time      # about 60 minutes, dominated by python/all/5y (52 min)
    python Class3/measure.py memory    # about 70 minutes
    python Class3/measure.py table     # merge both into results/runs.csv and runs.md

tracemalloc slows the pure-Python engine about 19-fold (every float object is a traced
allocation), so the memory suite skips python/all/5y: it would take about 17 hours.
That run holds one asset at a time, so its traced peak is bounded by python/BTC/5y.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
LAB = HERE / "lab.py"

RUNS = [  # (engine, assets, horizon) in execution order: fast runs first
    ("numpy", "BTCUSDT", "1y"), ("numpy", "BTCUSDT", "5y"),
    ("numpy", "all", "1y"), ("numpy", "all", "5y"),
    ("python", "BTCUSDT", "1y"), ("python", "all", "1y"),
    ("python", "BTCUSDT", "5y"), ("python", "all", "5y"),
]
SKIP_MEMORY = {("python", "all", "5y"): "not traced: ~17 h under tracemalloc; see python/BTCUSDT/5y"}


def run_suite(suite: str) -> None:
    RESULTS.mkdir(exist_ok=True)
    log = RESULTS / f"runs_{suite}.jsonl"
    log.unlink(missing_ok=True)
    for engine, assets, horizon in RUNS:
        if suite == "memory" and (engine, assets, horizon) in SKIP_MEMORY:
            continue
        cmd = [sys.executable, str(LAB), "--assets", assets, "--horizon", horizon,
               "--engine", engine, "--summary-out", str(log)]
        if suite == "memory":
            cmd.append("--trace-memory")
        else:
            tag = "BTCUSDT" if assets == "BTCUSDT" else "all"
            cmd += ["--assets-out", str(RESULTS / f"assets_{tag}_{horizon}_{engine}.csv")]
            if assets == "BTCUSDT" and engine == "python":
                cmd += ["--boundary-dir", str(RESULTS)]
        print(datetime.now().strftime("%H:%M:%S"), " ".join(cmd[2:]), flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    write_metadata(suite)


def write_metadata(suite: str) -> None:
    import numpy
    path = RESULTS / f"metadata_{suite}.json"      # one file per suite: suites may run in parallel
    meta = {}
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
               for p in sorted(HERE.glob("*.py"))}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()
    meta[suite] = {
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "numpy": numpy.__version__,
        "machine": platform.platform(), "processor": platform.processor(),
        "git_commit_at_run": commit, "source_sha256_16": sources,
    }
    path.write_text(json.dumps(meta, indent=2) + "\n")


def mib(value):
    return "" if value in (None, "") else f"{value / 2**20:.1f}"


def table() -> None:
    def load(name):
        path = RESULTS / f"runs_{name}.jsonl"
        if not path.exists():
            return {}
        out = {}
        for line in path.read_text().splitlines():
            s = json.loads(line)
            out[(s["engine"], "all" if s["assets"] > 1 else "BTCUSDT", s["horizon"])] = s
        return out

    timed, traced = load("time"), load("memory")
    rows = []
    for key in RUNS:
        t, m = timed.get(key), traced.get(key)
        if t is None:
            continue
        rows.append({
            "engine": key[0], "assets": t["assets"], "horizon": key[2],
            "N": "/".join(map(str, t["N"])),
            "seconds_total": f"{t['seconds_total']:.2f}",
            "seconds_pricing": f"{t['seconds_pricing']:.2f}",
            "peak_traced_MiB": mib(m["peak_traced_bytes"]) if m else SKIP_MEMORY.get(key, ""),
            "max_rss_MiB": mib(t["max_rss_bytes"]),
        })
    with (RESULTS / "runs.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    header = ("| Engine | Assets | Horizon | N | Seconds (total) | Seconds (pricing) "
              "| Peak traced (MiB) | Max RSS (MiB) |\n|---|---:|---|---:|---:|---:|---:|---:|\n")
    body = "".join(f"| {r['engine']} | {r['assets']} | {r['horizon']} | {r['N']} | "
                   f"{r['seconds_total']} | {r['seconds_pricing']} | "
                   f"{r['peak_traced_MiB'] if not r['peak_traced_MiB'].startswith('not') else 'n/a'} | "
                   f"{r['max_rss_MiB']} |\n" for r in rows)
    (RESULTS / "runs.md").write_text(header + body)
    print(header + body)
    assets_table()


def assets_table() -> None:
    """Task 5 summary: one row per asset, one-year and full-file windows side by side.

    Uses the pure-Python result files and checks that the NumPy engine produced the
    same numbers (it performs the same floating-point operations in the same order).
    """
    def read(horizon, engine):
        path = RESULTS / f"assets_all_{horizon}_{engine}.csv"
        return {r["symbol"]: r for r in csv.DictReader(path.open())} if path.exists() else None

    tables = {}
    for horizon in ("1y", "5y"):
        py, nps = read(horizon, "python"), read(horizon, "numpy")
        if py and nps:
            for symbol in py:
                for field in ("put_value", "exercise_utc", "boundary_dates"):
                    assert py[symbol][field] == nps[symbol][field], (horizon, symbol, field)
        tables[horizon] = py or nps
    if not all(tables.values()):
        return

    def fmt(r):
        payoff = (f"{100 * float(r['exercise_payoff']) / float(r['S0_K']):.1f}"
                  if r["exercise_payoff"] else "")
        when = r["exercise_utc"].replace("T", " ").replace("Z", "") if r["exercise_t"] != "never" \
            else "never"
        return (f"{float(r['s_hourly']):.5f} | {float(r['put_pct_of_spot']):.2f} | "
                f"{when} | {payoff}")

    lines = ["| Asset | s (1y) | Put % of S0 (1y) | First exercise (1y) | Payoff % of K (1y) "
             "| s (5y) | Put % of S0 (5y) | First exercise (5y) | Payoff % of K (5y) |",
             "|---|---:|---:|---|---:|---:|---:|---|---:|"]
    for symbol in sorted(tables["1y"]):
        lines.append(f"| {symbol.removesuffix('USDT')} | {fmt(tables['1y'][symbol])} | "
                     f"{fmt(tables['5y'][symbol])} |")
    for horizon in ("1y", "5y"):
        rows = tables[horizon].values()
        never = sorted(r["symbol"].removesuffix("USDT") for r in rows if r["exercise_t"] == "never")
        lines.append(f"\n{horizon}: exercised for {len(rows) - len(never)} of {len(rows)} assets; "
                     f"never: {', '.join(never) or 'none'}.")
    (RESULTS / "assets_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-2:]))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "table"
    if command in ("time", "memory"):
        run_suite(command)
    elif command == "table":
        table()
    else:
        raise SystemExit(f"unknown command {command!r}: use time, memory or table")
