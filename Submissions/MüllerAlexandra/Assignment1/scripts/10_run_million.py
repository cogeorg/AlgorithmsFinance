#!/usr/bin/env python3
"""Run the paired one-million-event throughput extension with fixed limits."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from limit_order_book.experiment_runner import (
    FORMAL_TIMEOUT_SECONDS,
    PROJECT_ROOT,
    execute_task,
    million_task_specs,
)


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("baseline", "revised"), required=True)
    parser.add_argument("--scenario")
    parser.add_argument(
        "--timeout-seconds",
        type=positive_integer,
        default=FORMAL_TIMEOUT_SECONDS,
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def selected_tasks(args: argparse.Namespace) -> list[dict[str, object]]:
    tasks = million_task_specs(args.version)
    if args.scenario is not None:
        tasks = [task for task in tasks if task["scenario"] == args.scenario]
    return tasks


def main(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    tasks = selected_tasks(args)
    if not tasks:
        raise SystemExit("no extension tasks match the requested filters")
    outcomes: Counter[str] = Counter()
    for task in tasks:
        status_path = PROJECT_ROOT / str(task["status_path"])
        if status_path.exists():
            if args.resume:
                outcomes["skipped_existing"] += 1
                continue
            raise SystemExit(f"status already exists: {status_path}")
        status = execute_task(
            task,
            project_root=PROJECT_ROOT,
            python_executable=sys.executable,
            timeout_seconds=args.timeout_seconds,
        )
        status_path.parent.mkdir(parents=True, exist_ok=True)
        with status_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"task": task, **status}, stream, indent=2)
            stream.write("\n")
        outcomes[str(status["outcome"])] += 1
        print(json.dumps({"task_id": task["task_id"], "outcome": status["outcome"]}))
    print(json.dumps({"selected": len(tasks), "outcomes": outcomes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
