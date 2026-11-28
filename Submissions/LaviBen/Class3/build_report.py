#!/usr/bin/env python3
"""Build deterministic Class 3 tables and report from saved results only."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path


SUBMISSION_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SUBMISSION_DIR / "results"
SCENARIO_NAMES = (
    "bitcoin_one_year",
    "bitcoin_full",
    "all_assets_one_year",
    "all_assets_full",
)


@dataclass(frozen=True)
class ResultsBundle:
    scenarios: dict
    python_pilot: dict
    compiled_pilot: dict


def _load_json(path: Path):
    with path.open() as stream:
        return json.load(stream)


def load_results(results_dir: str | Path = RESULTS_DIR) -> ResultsBundle:
    results_dir = Path(results_dir)
    scenarios = {
        name: _load_json(results_dir / f"{name}.json") for name in SCENARIO_NAMES
    }
    for name, payload in scenarios.items():
        if payload.get("status") != "completed" or payload.get("scenario") != name:
            raise ValueError(f"{name} is not a completed canonical result")
        if len(payload.get("timing", {}).get("raw_seconds", ())) != 5:
            raise ValueError(f"{name} does not contain five raw timing repeats")
    python_pilot = _load_json(results_dir / "worker_pilot_python.json")
    compiled_pilot = _load_json(results_dir / "worker_pilot.json")
    if python_pilot.get("status") != "completed" or compiled_pilot.get("status") != "completed":
        raise ValueError("both worker pilots must be complete")
    return ResultsBundle(scenarios, python_pilot, compiled_pilot)


def _scenario_fields(name: str, payload: dict):
    if name.startswith("bitcoin"):
        steps = payload["input"]["steps"]
        assets = 1
        workers = 1
        peak = payload["memory"]["aggregate_peak_rss_bytes"]
    else:
        steps = payload["inputs"][0]["steps"]
        assets = payload["asset_count"]
        workers = payload["workers"]
        peak = payload["memory"]["parent_plus_tree_peak_rss_bytes"]
    return steps, assets, workers, payload["timing"]["median_seconds"], peak


def _mib(value: int) -> float:
    return value / (1024 * 1024)


def _pilot_rows(bundle: ResultsBundle):
    rows = []
    for label, key in (("All 40, one year", "one_year_all_assets"),):
        old = {row["workers"]: row for row in bundle.python_pilot[key]}
        new = {row["workers"]: row for row in bundle.compiled_pilot[key]}
        for workers in sorted(set(old) & set(new)):
            rows.append((label, workers, old[workers]["wall_seconds"],
                         new[workers]["wall_seconds"]))
    old = {row["workers"]: row
           for row in bundle.python_pilot["full_history_subset"]["records"]}
    new = {row["workers"]: row
           for row in bundle.compiled_pilot["full_history_subset"]["records"]}
    for workers in sorted(set(old) & set(new)):
        rows.append(("Four assets, full history", workers,
                     old[workers]["wall_seconds"], new[workers]["wall_seconds"]))
    return rows


def _full_subset_backend_difference(bundle: ResultsBundle):
    old = bundle.python_pilot["full_history_subset"]["records"][0]["values"]
    new = bundle.compiled_pilot["full_history_subset"]["records"][0]["values"]
    if set(old) != set(new):
        raise ValueError("full-history pilot asset sets differ across backends")
    maximum_absolute = max(abs(old[symbol] - new[symbol]) for symbol in old)
    maximum_relative = max(
        abs(old[symbol] - new[symbol]) / max(1.0, abs(old[symbol]))
        for symbol in old
    )
    return maximum_absolute, maximum_relative


def _joined_values(bundle: ResultsBundle):
    one_year = {
        row["symbol"]: row for row in bundle.scenarios["all_assets_one_year"]["outputs"]
    }
    full = {row["symbol"]: row for row in bundle.scenarios["all_assets_full"]["outputs"]}
    if len(one_year) != 40 or set(one_year) != set(full):
        raise ValueError("one-year and full-history asset sets must contain the same 40 symbols")
    return [(symbol, one_year[symbol]["value"], full[symbol]["value"])
            for symbol in sorted(one_year)]


def render_report(bundle: ResultsBundle) -> str:
    scenarios = bundle.scenarios
    lines = [
        "# Class 3 report: American puts on market data",
        "",
        "## Outcome",
        "",
        "The exact rolling binomial recurrence was implemented with one value vector, "
        "validated against an independent recursive oracle, and executed through a "
        "compiled C backend after the pure-Python worker pilot established the runtime "
        "need. Bitcoin boundaries and observed exercise decisions are retained; the "
        "40-asset runs return values only.",
        "",
        "## Required run table",
        "",
        "| Scenario | N | Assets | Workers | Median seconds | Peak RSS bytes | Peak RSS MiB |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "bitcoin_one_year": "Bitcoin, one year",
        "bitcoin_full": "Bitcoin, full history",
        "all_assets_one_year": "All assets, one year",
        "all_assets_full": "All assets, full history",
    }
    for name in SCENARIO_NAMES:
        steps, assets, workers, median, peak = _scenario_fields(name, scenarios[name])
        lines.append(
            f"| {labels[name]} | {steps:,} | {assets} | {workers} | "
            f"{median:.9f} | {peak:,} | {_mib(peak):.3f} |"
        )

    lines.extend(["", "## Bitcoin results", ""])
    for name, label in (("bitcoin_one_year", "One year"), ("bitcoin_full", "Full history")):
        payload = scenarios[name]
        output = payload["output"]
        exercise = output["exercise"]
        lines.extend([
            f"### {label}",
            "",
            f"- Put value: `{output['put_value']:.12f}`",
            f"- Boundary dates present: `{output['boundary_count']:,}` of "
            f"`{output['boundary_length']:,}`",
            f"- First observed exercise: `{exercise['timestamp_utc']}`",
            f"- Observed price: `{exercise['observed_price']:.8f}`",
            f"- Boundary price: `{exercise['boundary_price']:.12f}`",
            f"- Payoff: `{exercise['payoff']:.8f}`",
            "",
        ])

    lines.extend([
        "## Optimization and CPU scaling",
        "",
        "Both pilots used identical prepared jobs and required exact ordered values at "
        "every worker count. Compilation and worker warm-up were outside timing.",
        "",
        "| Workload | Workers | Python seconds | Compiled seconds | Speedup |",
        "|---|---:|---:|---:|---:|",
    ])
    for label, workers, old, new in _pilot_rows(bundle):
        lines.append(f"| {label} | {workers} | {old:.6f} | {new:.6f} | {old/new:.2f}x |")

    maximum_absolute, maximum_relative = _full_subset_backend_difference(bundle)

    lines.extend([
        "",
        "Across the four full-history pilot assets, Python and compiled values had "
        f"maximum absolute difference `{maximum_absolute:.17g}` and maximum relative "
        f"difference `{maximum_relative:.17g}`.",
        "",
        "8 workers were selected because they had the lowest measured all-assets "
        "one-year wall time. Separate processes bypass the Python GIL; macOS schedules "
        "them across CPUs without a claim of fixed core affinity.",
        "",
        "## Raw timing repeats",
        "",
    ])
    for name in SCENARIO_NAMES:
        raw = ", ".join(f"{value:.9f}" for value in scenarios[name]["timing"]["raw_seconds"])
        lines.append(f"- {labels[name]}: `{raw}` seconds")

    lines.extend([
        "",
        "## All 40 put values",
        "",
        "| Symbol | One-year value | Full-history value |",
        "|---|---:|---:|",
    ])
    for symbol, one_year, full in _joined_values(bundle):
        lines.append(f"| {symbol} | {one_year:.12f} | {full:.12f} |")

    one_year = scenarios["bitcoin_one_year"]
    full = scenarios["bitcoin_full"]
    lines.extend([
        "",
        "## Correctness and data integrity",
        "",
        "- The two-period example equals `1175/147 = 7.9931972789` and displays as "
        "`7.9932`; its boundary is `(None, 80, 96)`.",
        "- The Python and compiled kernels agree on the exhaustive small-tree suite and "
        "the complete Bitcoin one-year boundary.",
        "- All 40 CSV files contain finite, strictly positive prices and ordered UTC "
        "timestamps.",
        "- The one-year windows contain 8,761 observations and no missing hours.",
        "- Full files contain 43,823 observations (`N=43,822`) and one common missing "
        "hour, 2023-03-24 13:00 UTC; it is reported and not filled.",
        f"- Bitcoin source SHA-256: `{one_year['input']['sha256']}`.",
        "",
        "## Measurement protocol",
        "",
        "Inputs were parsed, validated, checksummed, and calibrated outside timing. Each "
        "scenario has five fresh raw repeats and reports their median. Worker processes "
        "were warmed outside timing. Required output construction is inside timing; "
        "serialization and cleanup are outside. Peak memory comes from a separate fresh "
        "run sampling RSS with `psutil`; Bitcoin includes parent plus child, and batch "
        "runs include parent plus the coordinator process tree. Outputs remain alive at "
        "the final sample.",
        "",
        "## Assumptions and limitations",
        "",
        "- A year is 8,760 hours, matching the assignment's one-year definition.",
        "- The missing full-history exchange hour is not interpolated; adjacent available "
        "observations remain adjacent tree periods, while endpoint timestamps determine T.",
        "- USDT is treated as the supplied US-dollar proxy; PAXG is the supplied gold proxy.",
        "- The S&P 500 file is optional, date-dependent, and not part of the required 40 "
        "tracked assets.",
        "- Canonical measurements identify the committed implementation by Git commit "
        "and by SHA-256 source hashes.",
        "",
        "## Dashboard",
        "",
        "`results/dashboard.html` is a standalone, saved-results-only dashboard. It "
        "exposes all raw repeats, statuses, units, memory definitions, all 40 values, "
        "Bitcoin boundary charts, CPU-scaling pilots, environment details, and source "
        "checksums. It has no network dependency and does not run pricing or measurement "
        "code. `python3 dashboard.py --check` verifies byte-stable regeneration.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "python3 -m unittest discover -s tests -v",
        "python3 run_bitcoin.py --window one_year",
        "python3 run_bitcoin.py --window full",
        "python3 pilot_workers.py",
        "python3 run_all_assets.py --window one_year --workers 8",
        "python3 run_all_assets.py --window full --workers 8",
        "python3 dashboard.py",
        "python3 dashboard.py --check",
        "python3 build_report.py",
        "python3 build_report.py --check",
        "```",
        "",
    ])
    return "\n".join(lines)


def render_summary_csv(bundle: ResultsBundle) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([
        "scenario", "steps", "assets", "workers", "median_seconds",
        "peak_rss_bytes", "peak_rss_mib", "status"
    ])
    for name in SCENARIO_NAMES:
        payload = bundle.scenarios[name]
        steps, assets, workers, median, peak = _scenario_fields(name, payload)
        writer.writerow([name, steps, assets, workers, repr(median), peak,
                         repr(_mib(peak)), payload["status"]])
    return stream.getvalue()


def render_combined_values_csv(bundle: ResultsBundle) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["symbol", "one_year_value", "full_history_value"])
    for symbol, one_year, full in _joined_values(bundle):
        writer.writerow([symbol, repr(one_year), repr(full)])
    return stream.getvalue()


def render_results_readme(bundle: ResultsBundle) -> str:
    lines = [
        "# Saved Class 3 evidence",
        "",
        "Canonical machine-readable records:",
        "",
        "- `bitcoin_one_year.json` and complete ordered boundary CSV",
        "- `bitcoin_full.json` and complete ordered boundary CSV",
        "- `all_assets_one_year.json` and values CSV",
        "- `all_assets_full.json` and values CSV",
        "- `worker_pilot_python.json` and `worker_pilot.json`",
        "- `summary.csv` and `all_asset_values.csv`, generated from the JSON files",
        "- `dashboard.html`, a standalone presentation of the saved evidence",
        "",
        "All four canonical scenarios contain five raw timing repeats, separate peak-RSS "
        "measurements, environment and compiler metadata, data/source checksums, and "
        "completed status. `CHECKSUMS.sha256` covers the result evidence except itself.",
        "",
    ]
    return "\n".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def _checksums(results_dir: Path) -> str:
    lines = []
    for path in sorted(results_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == "CHECKSUMS.sha256" or path.suffix == ".tmp":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    return "\n".join(lines) + "\n"


def expected_outputs(bundle: ResultsBundle, results_dir: Path):
    outputs = {
        SUBMISSION_DIR / "REPORT.md": render_report(bundle),
        results_dir / "summary.csv": render_summary_csv(bundle),
        results_dir / "all_asset_values.csv": render_combined_values_csv(bundle),
        results_dir / "README.md": render_results_readme(bundle),
    }
    return outputs


def build(results_dir: Path, *, check: bool) -> None:
    bundle = load_results(results_dir)
    outputs = expected_outputs(bundle, results_dir)
    if check:
        for path, expected in outputs.items():
            if not path.exists() or path.read_text() != expected:
                raise SystemExit(f"generated output differs: {path}")
        expected_checksums = _checksums(results_dir)
        checksum_path = results_dir / "CHECKSUMS.sha256"
        if not checksum_path.exists() or checksum_path.read_text() != expected_checksums:
            raise SystemExit(f"generated output differs: {checksum_path}")
        print("Saved report outputs are byte-stable")
        return
    for path, text in outputs.items():
        _write_atomic(path, text)
    _write_atomic(results_dir / "CHECKSUMS.sha256", _checksums(results_dir))
    print("Report and tables rebuilt from saved results")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    build(args.results_dir.resolve(), check=args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
