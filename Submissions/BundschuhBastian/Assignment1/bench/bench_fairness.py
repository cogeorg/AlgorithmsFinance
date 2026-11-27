"""Phase 6c (5): fairness check, 10,000 events only. A, "A_idset" (A + a set of live ids, see
bench.variants) and B on the five scenarios, seed 42, usual timing rules, one block per scenario
with a canary before and after. Writes results/fairness_time.csv; the variant is labeled in the
`version` column. It answers: how much of A's cost is the id scan alone?

    .venv/bin/python -m bench.bench_fairness
"""
from __future__ import annotations

import argparse

from bench import common, variants
from bench.bench_time import run_one
from bench.blocks import canary_around
from bench.common import RESULTS, read_csv, run_result
from lob import VERSIONS

OUT = RESULTS / "fairness_time.csv"
EVENTS = 10000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    args = parser.parse_args(argv)
    VERSIONS[variants.NAME] = variants.OrderBookAIdSet     # visible to the forked child runs
    names = ("A", variants.NAME, "B")
    for scenario in common.SCENARIOS:
        spec = dict(scenario=scenario, events=EVENTS, seed=42, levels=1000)
        todo = [v for v in names if run_result(read_csv(OUT), v, scenario, 42, EVENTS, 1000) is None]
        if not todo:
            continue
        with canary_around(f"fairness_{scenario}"):
            for version in todo:
                out = run_one(version, spec, args.limit_seconds, common.SLOW_FIRST_SECONDS,
                              common.TIMED_REPEATS, OUT, {"block": f"fairness_{scenario}"})
                print(scenario, version, out["status"],
                      out["median"] if out["median"] != "" else out["reason"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
