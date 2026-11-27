"""One-off, bounded phase execution for Assignment 1 evidence recovery."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import benchmarks.run_benchmarks as runner


RUN_ID = "coverage_recovery_short_20261126_1232"
SOURCE_RUN = "full_20261125"
WALL_BUDGET_SECONDS = 8 * 60
PRIMARY_LIMIT_SECONDS = 30.0
MEMORY_LIMIT_MIB = 4096.0


def _case_from_manifest(source: dict[str, Any]) -> dict[str, Any]:
    case = dict(source)
    paths = []
    for raw_path in source["input_paths"]:
        path = Path(str(raw_path).replace("\\", "/"))
        if not path.is_absolute():
            path = runner.ROOT / path
        paths.append(str(path.resolve()))
    case["input_paths"] = paths
    case["input_path"] = paths[0]
    for path in paths:
        expected = source["input_checksums"].get(Path(path).name)
        if not expected or runner._sha256_file(path) != expected:
            raise ValueError(f"source input checksum mismatch: {path}")
    return case


def _save_status(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    started = time.monotonic()
    run_dir = runner._create_run_directory(RUN_ID)
    source_metadata = json.loads(
        (runner.RUNS_DIR / SOURCE_RUN / "metadata.json").read_text(encoding="utf-8")
    )
    source_cases = {
        case["case_id"]: case for case in source_metadata.get("cases", [])
    }

    case_ids = [
        *[
            f"workload_{scenario}_M100000_seed{seed}"
            for scenario in ("sweep", "cancel_churn")
            for seed in (42, 43, 44)
        ],
        "workload_mixed_M100000_seed44",
        "queue_concentration_prices4_M10000",
        "queue_concentration_prices1000_M10000",
    ]
    cases = [_case_from_manifest(source_cases[case_id]) for case_id in case_ids]

    million_path = run_dir / "inputs" / "buildup_M1000000_seed42_levels1000.jsonl.gz"
    generation_command = [
        sys.executable,
        str(runner.ROOT / "generate_orders.py"),
        "--scenario", "buildup",
        "--events", "1000000",
        "--levels", "1000",
        "--seed", "42",
        "--out", str(million_path),
    ]
    generation_started = time.perf_counter()
    try:
        generated = subprocess.run(
            generation_command,
            cwd=str(runner.ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as error:
        (run_dir / "generation_failure.json").write_text(
            json.dumps({
                "status": "generation_failed",
                "command": generation_command,
                "duration_seconds": time.perf_counter() - generation_started,
                "error_type": type(error).__name__,
                "error": str(error),
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise
    generation_seconds = time.perf_counter() - generation_started
    generated_metadata = json.loads(generated.stdout.strip().splitlines()[-1])
    checksum = runner._sha256_file(million_path)
    if generated_metadata.get("sha256") != checksum:
        raise ValueError("one-million-event input checksum disagrees with generator metadata")
    million_case = {
        "case_id": "workload_buildup_M1000000_seed42",
        "experiment": "workload_replay",
        "scenario": "buildup",
        "seed": 42,
        "event_count": 1_000_000,
        "input_path": str(million_path.resolve()),
        "input_paths": [str(million_path.resolve())],
        "input_checksums": {million_path.name: checksum},
        "generator_settings": {
            "generator": "generate_orders.py",
            "scenario": "buildup",
            "events": 1_000_000,
            "seed": 42,
            "levels": 1000,
            "source": "generated",
        },
        "profile": False,
    }
    cases.append(million_case)

    settings = dict(source_metadata["settings"])
    settings["phase_budgets"] = {
        "primary": PRIMARY_LIMIT_SECONDS,
        "latency": PRIMARY_LIMIT_SECONDS,
        "memory": PRIMARY_LIMIT_SECONDS,
        "state_peaks": PRIMARY_LIMIT_SECONDS,
        "counters": PRIMARY_LIMIT_SECONDS,
        "profile": PRIMARY_LIMIT_SECONDS,
    }
    settings["time_limit_seconds"] = PRIMARY_LIMIT_SECONDS
    settings["memory_limit_mib"] = MEMORY_LIMIT_MIB
    settings["timing_repeats"] = runner.TIMING_REPEATS
    source_parity = {
        entry["case_id"]: entry
        for entry in source_metadata.get("parity_validation", [])
    }
    metadata = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "cases": [runner._case_manifest(case) for case in cases],
        "parity_validation": [
            source_parity[case_id] for case_id in case_ids
            if case_id in source_parity
        ],
        "environment": runner._environment_snapshot(),
        "code_hashes": runner._code_hashes(),
        "execution_scope": {
            "command": r".\.venv\Scripts\python.exe results\coverage_recovery_execution.py",
            "source_run": SOURCE_RUN,
            "selected_cases": [*case_ids, million_case["case_id"]],
            "phases": ["engine_replay"],
            "warmup": "one untimed replay before five timed repeats",
            "primary_time_limit_seconds_per_version": PRIMARY_LIMIT_SECONDS,
            "sampled_memory_limit_mib_per_version": MEMORY_LIMIT_MIB,
            "one_million_feasibility": {
                "scenario": "buildup",
                "seed": 42,
                "event_count": 1_000_000,
                "generation_command": generation_command,
                "generation_seconds": generation_seconds,
                "sha256": checksum,
                "generated_bytes": million_path.stat().st_size,
            },
            "execution_script_sha256": runner._sha256_file(Path(__file__)),
            "note": (
                "Only selected phases were run via the existing bounded "
                "phase worker; no engine or benchmark implementation changed."
            ),
        },
    }
    runner._json_write_exclusive(run_dir / "metadata.json", metadata)

    attempts: list[dict[str, Any]] = []
    status_path = run_dir / "execution_status.json"
    work: list[tuple[dict[str, Any], str, str]] = []
    for case in cases[:6]:
        for version in runner.VERSIONS:
            work.append((case, version, "engine_replay"))
    work.append((cases[6], "revised", "engine_replay"))
    for case in cases[7:9]:
        for version in runner.VERSIONS:
            work.append((case, version, "engine_replay"))
    for version in runner.VERSIONS:
        work.append((million_case, version, "engine_replay"))

    try:
        for case, version, phase in work:
            if time.monotonic() - started + PRIMARY_LIMIT_SECONDS + 2 > WALL_BUDGET_SECONDS:
                attempts.append({
                    "config_id": runner._config_id(case, version),
                    "phase": phase,
                    "status": "not_attempted_wall_budget",
                    "completed_repeats": 0,
                })
                continue
            record = runner._run_one_phase(
                run_dir,
                case,
                version,
                phase,
                1,
                settings,
                PRIMARY_LIMIT_SECONDS,
            )
            result = {
                "config_id": record["config_id"],
                "phase": phase,
                "status": record["status"],
                "duration_seconds": record["duration_until_stop_seconds"],
                "completed_repeats": sum(
                    row.get("repeat") is not None
                    and row.get("status") == "completed"
                    for row in record["rows"]
                ),
                "record_file": record["record_file"],
            }
            attempts.append(result)
            _save_status(status_path, {
                "run_id": RUN_ID,
                "started_at_utc": metadata["created_at_utc"],
                "wall_budget_seconds": WALL_BUDGET_SECONDS,
                "attempts": attempts,
            })
            print(json.dumps(result, sort_keys=True), flush=True)
    except KeyboardInterrupt:
        attempts.append({"status": "interrupted_by_operator"})
        raise
    finally:
        _save_status(status_path, {
            "run_id": RUN_ID,
            "started_at_utc": metadata["created_at_utc"],
            "wall_budget_seconds": WALL_BUDGET_SECONDS,
            "elapsed_seconds": time.monotonic() - started,
            "attempts": attempts,
        })
    print(json.dumps({
        "run_id": RUN_ID,
        "elapsed_seconds": time.monotonic() - started,
        "attempts": len(attempts),
        "status_path": str(status_path),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
