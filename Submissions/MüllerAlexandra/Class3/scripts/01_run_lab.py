"""Run the required Class 3 American-put experiments."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SUBMISSION_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SUBMISSION_ROOT.parents[2]
SRC = SUBMISSION_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from american_put_lab.data_io import load_hourly_prices
from american_put_lab.reporting import write_boundary_table, write_experiment_tables
from american_put_lab.workflow import analyze_series, run_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("btc", "one-year", "five-year", "all"),
        default="btc",
        help="btc is a quick required single-asset run; all runs every required scope",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPOSITORY_ROOT / "Class3" / "data" / "hourly",
    )
    parser.add_argument("--output-dir", type=Path, default=SUBMISSION_ROOT / "results")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(args.data_dir.glob("*.csv"))
    supplied_paths = [path for path in paths if path.name != "SP500.csv"]
    if len(supplied_paths) != 40:
        raise SystemExit(f"expected 40 supplied asset files, found {len(supplied_paths)}")
    btc_path = args.data_dir / "BTCUSDT.csv"

    experiments = []
    if args.scope in ("btc", "all"):
        btc_series = load_hourly_prices(btc_path, periods=8760)
        btc_analysis = analyze_series(btc_series)
        write_boundary_table(btc_series, btc_analysis, args.output_dir)
        experiments.append(run_experiment((btc_path,), 8760, "btc_one_year"))
    if args.scope in ("one-year", "all"):
        experiments.append(
            run_experiment(supplied_paths, 8760, "all_40_one_year")
        )
    if args.scope in ("five-year", "all"):
        experiments.append(
            run_experiment(supplied_paths, None, "all_40_full_history")
        )

    write_experiment_tables(experiments, args.output_dir)
    for result in experiments:
        print(
            f"{result.run_label}: assets={result.asset_count}, "
            f"N={result.min_periods}..{result.max_periods}, "
            f"seconds={result.seconds:.3f}, peak_mib={result.peak_bytes / 2**20:.3f}"
        )


if __name__ == "__main__":
    main()
