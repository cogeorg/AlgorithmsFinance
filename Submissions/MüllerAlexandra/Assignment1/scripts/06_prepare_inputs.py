#!/usr/bin/env python3
"""Generate missing formal inputs, verify metadata, and save the input plan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from limit_order_book.experiment_matrix import (
    experiment_input_specs,
    generation_arguments,
    verify_input_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "scripts" / "02_generate_orders.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate missing generated inputs; existing files are only verified.",
    )
    parser.add_argument("--plan-out", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    verified_specs: list[dict[str, object]] = []
    for spec in experiment_input_specs():
        input_path = PROJECT_ROOT / str(spec["input_path"])
        if not input_path.exists():
            if spec["input_kind"] != "generated" or not args.generate:
                raise SystemExit(f"missing input: {input_path}")
            command = generation_arguments(
                spec,
                python_executable=sys.executable,
                generator_path=GENERATOR_PATH,
                project_root=PROJECT_ROOT,
            )
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        metadata = verify_input_metadata(spec, project_root=PROJECT_ROOT)
        verified_specs.append({**spec, "metadata": metadata})

    plan = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "generator_path": str(GENERATOR_PATH.relative_to(PROJECT_ROOT)),
        "generator_sha256": sha256(GENERATOR_PATH),
        "input_count": len(verified_specs),
        "inputs": verified_specs,
    }
    output_path = (
        args.plan_out
        if args.plan_out.is_absolute()
        else PROJECT_ROOT / args.plan_out
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(output_path), "input_count": len(verified_specs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
