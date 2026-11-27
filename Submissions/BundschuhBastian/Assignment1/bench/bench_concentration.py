"""Phase 6c (2): queue concentration. Same number of orders (buildup, 100,000 events, seed 42),
price levels 4 / 16 / 64 / 256 / 1000 / 4000, Version A and Version B, the usual rules
(bench.bench_time.run_one: parse once, fresh book, gc enabled, first replay > 60 s -> single
measurement, 600 s limit -> stopped). Every level count is a block with a canary before and after
(bench.blocks). The 1000-level stream is measured again here so that all six are taken under the
same conditions. Writes results/concentration_raw.csv (same columns as time_raw.csv).

    .venv/bin/python -m bench.bench_concentration
"""
from __future__ import annotations

import argparse

from bench import common
from bench.bench_time import FIELDS, run_one
from bench.blocks import canary_around
from bench.common import RESULTS, read_csv, run_result

OUT = RESULTS / "concentration_raw.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--levels", nargs="+", type=int, default=list(common.CONCENTRATION_LEVELS))
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    args = parser.parse_args(argv)
    for levels in args.levels:
        spec = dict(scenario="buildup", events=100000, seed=42, levels=levels)
        todo = [v for v in ("A", "B")
                if run_result(read_csv(OUT), v, "buildup", 42, 100000, levels) is None]
        if not todo:
            continue
        with canary_around(f"concentration_L{levels}"):
            for version in todo:
                out = run_one(version, spec, args.limit_seconds, common.SLOW_FIRST_SECONDS,
                              common.TIMED_REPEATS, OUT, {"block": f"concentration_L{levels}"})
                print(version, "levels", levels, out["status"],
                      out["median"] if out["median"] != "" else out["reason"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
