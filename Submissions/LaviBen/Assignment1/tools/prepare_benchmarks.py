#!/usr/bin/env python3
"""Pre-generate deterministic benchmark inputs outside all measured regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from measurement.datasets import (  # noqa: E402
    STREAM_SCENARIOS,
    generate_events,
    standard_specs,
    write_dataset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "canonical"), default="smoke")
    parser.add_argument("--sizes", nargs="+", type=int)
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=STREAM_SCENARIOS,
        default=list(STREAM_SCENARIOS),
    )
    parser.add_argument("--levels", type=int, default=1_000)
    parser.add_argument("--skip-special", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "generated" / "benchmark",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sizes = args.sizes or ([1_000] if args.profile == "smoke" else [1_000, 10_000, 100_000])
    seeds = args.seeds or ([42] if args.profile == "smoke" else [42, 43, 44])
    specs = standard_specs(
        sizes=sizes,
        seeds=seeds,
        scenarios=args.scenarios,
        levels=args.levels,
        include_special=not args.skip_special,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, object] = {
        "profile": args.profile,
        "sizes": sizes,
        "seeds": seeds,
        "scenarios": args.scenarios,
        "levels": args.levels,
        "include_special": not args.skip_special,
        "datasets": [],
    }
    for spec in specs:
        path = args.output_dir / f"{spec.dataset_id}.jsonl.gz"
        events = generate_events(spec)
        metadata = write_dataset(path, spec, events)
        index["datasets"].append(metadata)  # type: ignore[union-attr]
        print(
            f"prepared {spec.dataset_id}: events={spec.event_count} "
            f"sha256={metadata['event_sha256']}"
        )

    (args.output_dir / "INDEX.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"prepared_datasets={len(specs)}")
    print(f"index={args.output_dir / 'INDEX.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
