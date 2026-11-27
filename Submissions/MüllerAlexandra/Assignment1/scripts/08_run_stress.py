#!/usr/bin/env python3
"""Run deterministic liquidation and small correctness diagnostics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from limit_order_book.benchmarking import (
    book_factory,
    environment_metadata,
    load_event_batch,
    write_json_exclusive,
)
from limit_order_book.stress_experiments import (
    build_liquidation_events,
    diagnose_replay,
    measure_liquidation_sale_memory,
    measure_liquidation_scenarios,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PLAN = PROJECT_ROOT / "experiments" / "08_input_plan.json"


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("baseline", "revised"), required=True)
    parser.add_argument("--order-count", type=positive_integer, default=1_000)
    parser.add_argument("--price-levels", type=positive_integer, default=100)
    parser.add_argument("--warmups", type=nonnegative_integer, default=1)
    parser.add_argument("--repeats", type=positive_integer, default=5)
    parser.add_argument("--diagnostic-events", type=positive_integer, default=1_000)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def diagnostic_specs() -> list[dict[str, object]]:
    plan = json.loads(INPUT_PLAN.read_text(encoding="utf-8"))
    specs = [
        spec
        for spec in plan["inputs"]
        if spec["event_count"] == 1_000
        and spec["seed"] == 42
        and spec["levels"] == 1_000
    ]
    if len(specs) != 5:
        raise ValueError(f"expected five diagnostic inputs, found {len(specs)}")
    return specs


def main(arguments: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.price_levels > args.order_count:
        parser.error("price-levels must not exceed order-count")
    try:
        factory = book_factory(args.version)
        build_events = build_liquidation_events(
            order_count=args.order_count,
            price_levels=args.price_levels,
        )
        timing = measure_liquidation_scenarios(
            factory,
            build_events,
            warmups=args.warmups,
            repeats=args.repeats,
        )
        memory = [
            measure_liquidation_sale_memory(
                factory,
                build_events,
                sale_size=sale_size,
            )
            for sale_size in ("10_percent", "100_percent", "200_percent")
        ]
        diagnostics: list[dict[str, object]] = []
        for spec in diagnostic_specs():
            events, input_metadata = load_event_batch(
                PROJECT_ROOT / str(spec["input_path"]),
                max_events=args.diagnostic_events,
            )
            counts = diagnose_replay(factory, events)
            if counts["rejected_events"] != 0:
                raise ValueError(f"diagnostic stream had rejections: {spec['scenario']}")
            if not all(
                counts[key]
                for key in (
                    "final_unique_order_ids",
                    "final_positive_quantities",
                    "final_uncrossed",
                )
            ):
                raise ValueError(f"diagnostic invariant failed: {spec['scenario']}")
            diagnostics.append(
                {
                    "scenario": spec["scenario"],
                    "seed": spec["seed"],
                    "input": input_metadata,
                    "counts": counts,
                }
            )
        document: dict[str, object] = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "phase": "stress_and_diagnostic",
            "version": args.version,
            "command": [sys.executable, *sys.argv],
            "environment": environment_metadata(),
            "settings": {
                "liquidation_order_count": args.order_count,
                "liquidation_price_levels": args.price_levels,
                "warmups": args.warmups,
                "repeats": args.repeats,
                "diagnostic_event_count": args.diagnostic_events,
                "diagnostic_seed": 42,
            },
            "liquidation_timing": timing,
            "liquidation_memory": memory,
            "diagnostics": diagnostics,
        }
        output_path = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
        write_json_exclusive(output_path, document)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "output": str(output_path),
                "liquidation_records": len(timing["records"]),
                "diagnostics": len(diagnostics),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
