#!/usr/bin/env python3
"""Build the dashboard artifact exclusively from saved measurements."""

from __future__ import annotations

import argparse
from pathlib import Path

from limit_order_book.reporting import write_dashboard_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "summary" / "13_dashboard_data.json.gz"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    results = args.results if args.results.is_absolute() else PROJECT_ROOT / args.results
    output = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
    write_dashboard_data(results, output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
