"""Measure workload reading/decompression separately from JSON decoding.

No matching-engine module is imported or executed. The timed boundaries are:

* ``read_decompress_seconds``: open the gzip file, read it from the filesystem,
  validate the gzip stream, decompress it, and allocate the decompressed bytes.
* ``json_decode_seconds``: split the already-decompressed JSONL bytes into lines,
  decode each line with :func:`json.loads`, validate that it is an object, and
  discard it before moving to the next line.

The operating-system file cache is not flushed. These are warmed-cache
application parsing costs, not cold-storage latency or engine replay time.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_MANIFEST = PROJECT_ROOT / "07_results" / "results_manifest.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "07_results" / "parsing" / "parsing_runs.jsonl"
PROTOCOL_VERSION = "parsing-only-v1"
REPETITIONS = 5
APPROVED_BUDGET_SECONDS = 300.0
MAX_DECOMPRESSED_BYTES = 128 * 1024 * 1024
EXPECTED_SCENARIOS = {"buildup", "crowded", "mixed", "sweep", "cancel_churn"}
EXPECTED_SIZES = {1_000, 10_000, 100_000}
EXPECTED_SEEDS = {42, 43, 44}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _environment() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }


def _read_jsonl(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise ValueError(f"truncated JSONL: {path}")
    records = []
    for number, line in enumerate(data.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank JSONL line: {path}:{number}")
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"non-object JSONL record: {path}:{number}")
        records.append(record)
    return data, records


def _project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"path escapes project: {relative_path}") from error
    return path


def _resolve_output(value: str | None) -> Path:
    if value is None:
        return DEFAULT_OUTPUT
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"output must remain inside project: {resolved}") from error
    return resolved


def _build_plan(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    warmed = manifest["artifacts"]["warmed_primary"]
    data, records = _read_jsonl(_project_path(warmed["path"]))
    if len(data) != warmed["bytes"] or hashlib.sha256(data).hexdigest() != warmed["sha256"]:
        raise ValueError("warmed-primary evidence differs from results manifest")
    if len(records) != warmed["record_count"]:
        raise ValueError("warmed-primary record count differs from results manifest")

    unique_workloads: dict[str, dict[str, Any]] = {}
    for record in records:
        identity = {
            "workload_id": record["workload_id"],
            "workload_sha256": record["workload_sha256"],
            "scenario": record["scenario"],
            "event_count": record["event_count"],
            "seed": record["seed"],
        }
        previous = unique_workloads.setdefault(record["workload_id"], identity)
        if previous != identity:
            raise ValueError(f"contradictory workload identity: {record['workload_id']}")
    plan = sorted(
        unique_workloads.values(),
        key=lambda item: (item["event_count"], item["scenario"], item["seed"]),
    )
    combinations = {(item["scenario"], item["event_count"], item["seed"]) for item in plan}
    expected = {
        (scenario, event_count, seed)
        for scenario in EXPECTED_SCENARIOS
        for event_count in EXPECTED_SIZES
        for seed in EXPECTED_SEEDS
    }
    if len(plan) != 45 or combinations != expected:
        raise ValueError("parsing plan must cover exactly the 45 core workloads")
    for item in plan:
        path = _project_path(item["workload_id"])
        if path.suffix != ".gz":
            raise ValueError(f"core parsing workload is not gzip: {item['workload_id']}")
        if _sha256(path) != item["workload_sha256"]:
            raise ValueError(f"workload hash mismatch: {item['workload_id']}")
        item["compressed_bytes"] = path.stat().st_size
    return plan


def _read_decompress(path: Path) -> tuple[bytes, float]:
    start = time.perf_counter()
    with gzip.open(path, "rb") as stream:
        payload = stream.read()
    elapsed = time.perf_counter() - start
    if len(payload) > MAX_DECOMPRESSED_BYTES:
        raise MemoryError(f"decompressed workload exceeds {MAX_DECOMPRESSED_BYTES} bytes: {path}")
    return payload, elapsed


def _decode_jsonl(payload: bytes) -> tuple[int, float]:
    start = time.perf_counter()
    count = 0
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank decompressed JSONL line {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object decompressed JSONL line {line_number}")
        count += 1
    return count, time.perf_counter() - start


def _warm_up(manifest: dict[str, Any]) -> dict[str, Any]:
    warmup = manifest["artifacts"]["warmed_primary"]["warmup"]
    path = _project_path(warmup["path"])
    if _sha256(path) != warmup["sha256"]:
        raise ValueError("parsing warm-up hash mismatch")
    payload, _ = _read_decompress(path)
    count, _ = _decode_jsonl(payload)
    if count != warmup["event_count"]:
        raise ValueError("parsing warm-up event-count mismatch")
    return warmup


def _append_record(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def _validate_records(
    records: list[dict[str, Any]], plan: list[dict[str, Any]], script_sha256: str
) -> dict[str, Any]:
    if len(records) != 45 * REPETITIONS:
        raise ValueError(f"expected 225 parsing records, observed {len(records)}")
    expected_keys = {
        (item["scenario"], item["event_count"], item["seed"], repetition)
        for item in plan
        for repetition in range(1, REPETITIONS + 1)
    }
    actual_keys = {
        (record["scenario"], record["event_count"], record["seed"], record["repetition"])
        for record in records
    }
    if actual_keys != expected_keys or len(actual_keys) != len(records):
        raise ValueError("parsing repetition coverage or uniqueness mismatch")
    for record in records:
        if record["status"] != "completed":
            raise ValueError("parsing evidence contains an incomplete record")
        if record["protocol_version"] != PROTOCOL_VERSION:
            raise ValueError("parsing protocol mismatch")
        if record["script_sha256"] != script_sha256:
            raise ValueError("parsing script fingerprint mismatch")
        if record["decoded_events"] != record["event_count"]:
            raise ValueError("decoded event count mismatch")
        if min(
            record["read_decompress_seconds"],
            record["json_decode_seconds"],
            record["combined_seconds"],
        ) <= 0:
            raise ValueError("parsing durations must be positive")
        if not math_isclose(
            record["combined_seconds"],
            record["read_decompress_seconds"] + record["json_decode_seconds"],
        ):
            raise ValueError("combined parsing duration mismatch")
    medians = {}
    for item in plan:
        group = [
            record
            for record in records
            if (record["scenario"], record["event_count"], record["seed"])
            == (item["scenario"], item["event_count"], item["seed"])
        ]
        key = f"{item['scenario']}:{item['event_count']}:{item['seed']}"
        medians[key] = {
            "median_read_decompress_seconds": statistics.median(
                record["read_decompress_seconds"] for record in group
            ),
            "median_json_decode_seconds": statistics.median(
                record["json_decode_seconds"] for record in group
            ),
            "median_combined_seconds": statistics.median(
                record["combined_seconds"] for record in group
            ),
        }
    return medians


def math_isclose(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-12, 1e-12 * max(abs(left), abs(right)))


def _dry_run_summary(plan: list[dict[str, Any]], output: Path, budget: float) -> dict[str, Any]:
    return {
        "action": "dry_run",
        "protocol_version": PROTOCOL_VERSION,
        "output": output.as_posix(),
        "output_exists": output.exists(),
        "workloads": len(plan),
        "planned_records": len(plan) * REPETITIONS,
        "scenarios": sorted(EXPECTED_SCENARIOS),
        "event_counts": sorted(EXPECTED_SIZES),
        "seeds": sorted(EXPECTED_SEEDS),
        "repetitions_per_workload": REPETITIONS,
        "planned_json_decodes": sum(item["event_count"] for item in plan) * REPETITIONS,
        "compressed_bytes_per_full_matrix_repeat": sum(item["compressed_bytes"] for item in plan),
        "compressed_bytes_across_five_repeats": sum(item["compressed_bytes"] for item in plan)
        * REPETITIONS,
        "largest_compressed_workload_bytes": max(item["compressed_bytes"] for item in plan),
        "budget_seconds": budget,
        "engine_imports": 0,
        "measurement_boundaries": {
            "read_decompress_seconds": "filesystem read + gzip validation/decompression + decompressed-byte allocation",
            "json_decode_seconds": "preloaded decompressed bytes; JSONL split + json.loads + mapping check",
            "combined_seconds": "sum of the two separately timed phases",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure parsing only; never import or replay an engine.")
    parser.add_argument("--output", help="JSONL output; relative paths resolve against caller cwd")
    parser.add_argument("--budget-seconds", type=float, default=APPROVED_BUDGET_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.dry_run and args.verify_only:
        parser.error("--dry-run and --verify-only are mutually exclusive")
    if args.budget_seconds != APPROVED_BUDGET_SECONDS:
        parser.error(f"approved budget is exactly {APPROVED_BUDGET_SECONDS:g} seconds")

    output = _resolve_output(args.output)
    manifest = json.loads(RESULTS_MANIFEST.read_text(encoding="utf-8"))
    plan = _build_plan(manifest)
    script_sha256 = _sha256(Path(__file__).resolve())
    if args.dry_run:
        print(json.dumps(_dry_run_summary(plan, output, args.budget_seconds), sort_keys=True))
        return 0

    if args.verify_only:
        _, records = _read_jsonl(output)
        medians = _validate_records(records, plan, script_sha256)
        print(
            json.dumps(
                {
                    "action": "verified",
                    "output": output.as_posix(),
                    "bytes": output.stat().st_size,
                    "sha256": _sha256(output),
                    "records": len(records),
                    "configurations": len(medians),
                    "status_counts": dict(Counter(record["status"] for record in records)),
                    "script_sha256": script_sha256,
                },
                sort_keys=True,
            )
        )
        return 0

    if output.exists():
        raise FileExistsError(f"refusing to overwrite parsing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    warmup = _warm_up(manifest)
    environment = _environment()
    environment_fingerprint = _stable_digest(environment)
    session_id = uuid.uuid4().hex
    session_start = time.perf_counter()
    planned_index = 0
    try:
        for item in plan:
            path = _project_path(item["workload_id"])
            for repetition in range(1, REPETITIONS + 1):
                planned_index += 1
                if time.perf_counter() - session_start >= args.budget_seconds:
                    raise TimeoutError(
                        f"parsing budget exhausted before record {planned_index}; stop for review"
                    )
                gc.collect()
                payload, read_seconds = _read_decompress(path)
                decoded_events, decode_seconds = _decode_jsonl(payload)
                if decoded_events != item["event_count"]:
                    raise ValueError(f"event-count mismatch: {item['workload_id']}")
                record = {
                    "protocol_version": PROTOCOL_VERSION,
                    "phase": "parsing",
                    "measurement_mode": "reading_decompression_and_json_decode",
                    "session_id": session_id,
                    "planned_index": planned_index,
                    "scenario": item["scenario"],
                    "event_count": item["event_count"],
                    "seed": item["seed"],
                    "repetition": repetition,
                    "status": "completed",
                    "workload_id": item["workload_id"],
                    "workload_sha256": item["workload_sha256"],
                    "compressed_bytes": item["compressed_bytes"],
                    "decompressed_bytes": len(payload),
                    "decoded_events": decoded_events,
                    "read_decompress_seconds": read_seconds,
                    "json_decode_seconds": decode_seconds,
                    "combined_seconds": read_seconds + decode_seconds,
                    "units": {"time": "seconds", "bytes": "bytes", "events": "count"},
                    "measurement_boundary": {
                        "read_decompress": "filesystem read + gzip validation/decompression + decompressed-byte allocation",
                        "json_decode": "preloaded decompressed bytes; JSONL split + json.loads + mapping check",
                        "engine_import_or_replay": False,
                        "os_file_cache_flushed": False,
                        "decoded_objects_retained": False,
                    },
                    "warmup": {
                        "workload_id": warmup["path"],
                        "workload_sha256": warmup["sha256"],
                        "event_count": warmup["event_count"],
                        "policy": "one untimed read/decompress/decode pass before the matrix",
                    },
                    "gc_policy": "gc.collect before each repeat; cyclic GC otherwise enabled",
                    "budget_seconds": args.budget_seconds,
                    "session_elapsed_seconds": time.perf_counter() - session_start,
                    "environment": environment,
                    "environment_fingerprint": environment_fingerprint,
                    "script_sha256": script_sha256,
                    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                _append_record(output, record)
    except BaseException:
        if output.exists() and output.stat().st_size == 0:
            output.unlink()
        raise

    _, records = _read_jsonl(output)
    medians = _validate_records(records, plan, script_sha256)
    elapsed = time.perf_counter() - session_start
    print(
        json.dumps(
            {
                "action": "completed",
                "output": output.as_posix(),
                "bytes": output.stat().st_size,
                "sha256": _sha256(output),
                "records": len(records),
                "configurations": len(medians),
                "status_counts": dict(Counter(record["status"] for record in records)),
                "actual_session_wall_seconds": elapsed,
                "budget_seconds": args.budget_seconds,
                "script_sha256": script_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
