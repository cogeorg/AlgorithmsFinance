"""Throughput benchmark input, summary, metadata, and persistence helpers."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
from itertools import islice
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
from time import perf_counter

from .baseline import BaselineOrderBook
from .interface import Event, OrderBook
from .measurement import (
    latency_breakdown_ns,
    measure_event_latencies,
    measure_throughput_repeats,
)
from .revised import RevisedOrderBook
from .stream_io import iter_events


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ("pytest", "pandas", "streamlit")
Clock = Callable[[], float]


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _nonnegative_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_event_batch(
    path: Path,
    *,
    max_events: int | None = None,
    clock: Clock = perf_counter,
) -> tuple[tuple[Event, ...], dict[str, object]]:
    """Parse a plain/gzip event prefix and report parsing separately."""

    if max_events is not None and (
        isinstance(max_events, bool)
        or not isinstance(max_events, int)
        or max_events <= 0
    ):
        raise ValueError("max_events must be a positive integer or None")

    resolved = path.resolve(strict=True)
    parse_started = clock()
    if max_events is None:
        events = tuple(iter_events(resolved))
    else:
        events = tuple(islice(iter_events(resolved), max_events))
    parse_seconds = clock() - parse_started
    if parse_seconds < 0:
        raise ValueError("clock produced negative parsing time")
    if not events:
        raise ValueError("benchmark input contains no events")

    metadata: dict[str, object] = {
        "path": str(resolved),
        "sha256": _sha256(resolved),
        "compressed_bytes": resolved.stat().st_size,
        "event_count": len(events),
        "max_events": max_events,
        "parse_seconds": parse_seconds,
    }
    return events, metadata


def summarize_throughput_records(
    records: Sequence[Mapping[str, int | float]],
) -> dict[str, int | float]:
    """Return medians without discarding or rewriting the raw repeats."""

    if not records:
        raise ValueError("throughput summary requires at least one record")
    event_counts = {record["event_count"] for record in records}
    if len(event_counts) != 1:
        raise ValueError("all throughput records must use one event count")
    return {
        "repeat_count": len(records),
        "median_construction_seconds": median(
            record["construction_seconds"] for record in records
        ),
        "median_replay_seconds": median(
            record["replay_seconds"] for record in records
        ),
        "median_total_engine_seconds": median(
            record["total_engine_seconds"] for record in records
        ),
        "median_throughput_events_per_second": median(
            record["throughput_events_per_second"] for record in records
        ),
    }


def write_json_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    """Create a JSON result without silently replacing earlier evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        stream_context = gzip.open(path, "xt", encoding="utf-8", newline="\n")
    else:
        stream_context = path.open("x", encoding="utf-8", newline="\n")
    with stream_context as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")


def _dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for dependency in DEPENDENCIES:
        try:
            versions[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            versions[dependency] = None
    return versions


def _git_metadata() -> dict[str, object]:
    def git_value(*arguments: str) -> str | None:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    assignment_status = git_value("status", "--short", "--", ".")
    code_status = git_value(
        "status",
        "--short",
        "--",
        ".",
        ":(exclude)results",
        ":(exclude)evidence",
    )
    return {
        "commit": git_value("rev-parse", "HEAD"),
        "branch": git_value("branch", "--show-current"),
        "dirty": None if assignment_status is None else bool(assignment_status),
        "assignment_dirty": (
            None if assignment_status is None else bool(assignment_status)
        ),
        "code_dirty": None if code_status is None else bool(code_status),
    }


def environment_metadata() -> dict[str, object]:
    """Describe the Python environment and recorded code version."""

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "dependencies": _dependency_versions(),
        "git": _git_metadata(),
    }


def book_factory(version: str) -> type[OrderBook]:
    """Select the implementation without changing the public event contract."""

    if version == "baseline":
        return BaselineOrderBook
    if version == "revised":
        return RevisedOrderBook
    raise ValueError(f"unknown version: {version}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("throughput", "latency"),
        default="throughput",
    )
    parser.add_argument("--version", choices=("baseline", "revised"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--max-events", type=_positive_integer)
    parser.add_argument("--warmups", type=_nonnegative_integer, default=1)
    parser.add_argument("--repeats", type=_positive_integer, default=5)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        events, input_metadata = load_event_batch(
            args.input,
            max_events=args.max_events,
        )
        factory = book_factory(args.version)
        if args.phase == "throughput":
            records = measure_throughput_repeats(
                factory,
                events,
                warmups=args.warmups,
                repeats=args.repeats,
            )
            settings: dict[str, object] = {
                "warmups": args.warmups,
                "repeats": args.repeats,
            }
            summary: dict[str, object] = summarize_throughput_records(records)
        else:
            records = measure_event_latencies(
                factory,
                events,
                warmups=args.warmups,
                repeats=args.repeats,
            )
            settings = {
                "clock": "time.perf_counter_ns",
                "warmups": args.warmups,
                "repeats": args.repeats,
                "window_fraction": 0.1,
            }
            summary = latency_breakdown_ns(records)
        document: dict[str, object] = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "phase": args.phase,
            "version": args.version,
            "command": [sys.executable, *sys.argv],
            "environment": environment_metadata(),
            "input": input_metadata,
            "settings": settings,
            "records": records,
            "summary": summary,
        }
        write_json_exclusive(args.out, document)
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"output": str(args.out), "summary": document["summary"]}))
    return 0
