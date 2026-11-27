"""Resource-bounded pilot and resumable final-primary benchmark controller."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve().with_name("_benchmark_worker.py")
IMPLEMENTATION_ROOT = PROJECT_ROOT / "04_implementation"
MAX_GLOBAL_SECONDS = 1200.0
FINAL_GLOBAL_SECONDS = 5400.0
FINAL_PROTOCOL_VERSION = "final-primary-v2"
FINAL_PHASE = "final"
FINAL_MODE = "primary_timing"
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
IMPLEMENTATION_SHARED_FILES = ("validation.py", "contracts.py", "__init__.py")
HARNESS_FILES = (
    "05_benchmarks/run_benchmarks.py",
    "05_benchmarks/_benchmark_worker.py",
)

PILOT_CONFIGS = [
    {
        "scenario": scenario,
        "events": 10_000,
        "seed": 42,
        "workload_id": f"02_data/supplied/data/{scenario}_10000.jsonl.gz",
        "processing_timeout": 30.0,
        "preparation_timeout": 15.0,
    }
    for scenario in ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
] + [
    {
        "scenario": scenario,
        "events": 100_000,
        "seed": 42,
        "workload_id": f"02_data/generated/{scenario}_100000_seed42.jsonl.gz",
        "processing_timeout": 120.0,
        "preparation_timeout": 45.0,
    }
    for scenario in ("buildup", "cancel_churn", "sweep")
]


def _total_ram_bytes() -> int | None:
    try:
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.total_physical)
            return None
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages * page_size)
    except (AttributeError, OSError, ValueError):
        return None


def _environment() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "total_ram_bytes": _total_ram_bytes(),
    }


def _reader(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _stderr_reader(stream: TextIO, lines: list[str]) -> None:
    for line in stream:
        lines.append(line.rstrip())
        if len(lines) > 50:
            del lines[0]


def _receive(messages: queue.Queue[str | None], timeout: float) -> dict[str, Any]:
    if timeout <= 0:
        raise queue.Empty
    line = messages.get(timeout=timeout)
    if line is None:
        raise EOFError("worker stdout closed")
    payload = json.loads(line)
    if type(payload) is not dict:
        raise ValueError("worker message is not an object")
    return payload


def _stop_worker(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        process.wait()
        return
    process.terminate()
    try:
        process.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3.0)


def _write_record(stream: TextIO, record: dict[str, Any]) -> None:
    stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _plan() -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for config_index, config in enumerate(PILOT_CONFIGS):
        order = ("baseline", "optimized") if config_index % 2 == 0 else ("optimized", "baseline")
        for engine in order:
            planned.append({**config, "engine": engine})
    return planned


def _core_workload_id(scenario: str, events: int, seed: int) -> str:
    if events == 10_000 and seed == 42:
        return f"02_data/supplied/data/{scenario}_10000.jsonl.gz"
    return f"02_data/generated/{scenario}_{events}_seed{seed}.jsonl.gz"


def _final_plan() -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    config_index = 0
    for events in (1_000, 10_000, 100_000):
        for scenario in SCENARIOS:
            for seed in (42, 43, 44):
                processing_timeout = 120.0 if events == 100_000 else 30.0
                preparation_timeout = 45.0 if events == 100_000 else 15.0
                workload_id = _core_workload_id(scenario, events, seed)
                for repetition in range(1, 6):
                    order = (
                        ("baseline", "optimized")
                        if (config_index + repetition) % 2 == 0
                        else ("optimized", "baseline")
                    )
                    for engine in order:
                        planned.append(
                            {
                                "scenario": scenario,
                                "events": events,
                                "seed": seed,
                                "workload_id": workload_id,
                                "processing_timeout": processing_timeout,
                                "preparation_timeout": preparation_timeout,
                                "engine": engine,
                                "repetition": repetition,
                            }
                        )
                config_index += 1
    return planned


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint_components(paths: tuple[Path, ...]) -> list[dict[str, str]]:
    """Return ordered project-relative names and content hashes for fingerprinting."""
    return [
        {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": _sha256(path),
        }
        for path in paths
    ]


def _fingerprint_sha256(components: list[dict[str, str]]) -> str:
    """Hash a stable JSON serialization without changing component order."""
    encoded = json.dumps(
        components,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_fingerprint(paths: tuple[Path, ...]) -> dict[str, Any]:
    components = _fingerprint_components(paths)
    return {
        "components": components,
        "sha256": _fingerprint_sha256(components),
    }


def _manifest_hashes() -> dict[str, str]:
    generated = json.loads(
        (PROJECT_ROOT / "02_data" / "generated_manifest.json").read_text(encoding="utf-8")
    )
    supplied = json.loads(
        (PROJECT_ROOT / "02_data" / "supplied" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    hashes = {
        f"02_data/generated/{record['filename']}": record["sha256"]
        for record in generated["direct_workloads"]
    }
    hashes.update(
        {
            f"02_data/supplied/{relative}": metadata["sha256"]
            for relative, metadata in supplied["files"].items()
        }
    )
    return hashes


def _environment_fingerprint(environment: dict[str, Any]) -> str:
    import hashlib

    canonical = json.dumps(environment, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _final_templates(
    plan: list[dict[str, Any]], environment: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    manifest_hashes = _manifest_hashes()
    workload_hashes: dict[str, str] = {}
    unique_workloads = {run["workload_id"] for run in plan}
    for workload_id in sorted(unique_workloads):
        path = PROJECT_ROOT / workload_id
        if not path.is_file():
            raise FileNotFoundError(f"required workload is absent: {workload_id}")
        actual = _sha256(path)
        expected = manifest_hashes.get(workload_id)
        if expected is None:
            raise ValueError(f"workload is not covered by retained manifests: {workload_id}")
        if actual != expected:
            raise ValueError(
                f"workload hash differs from retained manifest: {workload_id}"
            )
        workload_hashes[workload_id] = actual

    package_root = IMPLEMENTATION_ROOT / "orderbook"
    implementation_fingerprints = {
        engine: _source_fingerprint(
            (
                package_root / f"{engine_module}.py",
                *(package_root / filename for filename in IMPLEMENTATION_SHARED_FILES),
            )
        )
        for engine, engine_module in (
            ("baseline", "baseline"),
            ("optimized", "optimized"),
        )
    }
    harness_fingerprint = _source_fingerprint(
        tuple(PROJECT_ROOT / relative for relative in HARNESS_FILES)
    )
    fingerprint = _environment_fingerprint(environment)
    templates: list[dict[str, Any]] = []
    for index, run in enumerate(plan, 1):
        template = _base_record(index, run, environment)
        template.update(
            phase=FINAL_PHASE,
            measurement_mode=FINAL_MODE,
            repetition=run["repetition"],
            workload_sha256=workload_hashes[run["workload_id"]],
            implementation_fingerprint_sha256=(
                implementation_fingerprints[run["engine"]]["sha256"]
            ),
            implementation_fingerprint_files=[
                dict(component)
                for component in implementation_fingerprints[run["engine"]][
                    "components"
                ]
            ],
            harness_fingerprint_sha256=harness_fingerprint["sha256"],
            harness_fingerprint_files=[
                dict(component) for component in harness_fingerprint["components"]
            ],
            environment_fingerprint=fingerprint,
            timeout_policy=(
                f"processing={run['processing_timeout']};"
                f"preparation={run['preparation_timeout']};"
                "stop_configuration_on_processing_timeout"
            ),
            controller_protocol_version=FINAL_PROTOCOL_VERSION,
        )
        templates.append(template)
    return templates, len(unique_workloads)


def _logical_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("engine"),
        record.get("scenario"),
        record.get("event_count"),
        record.get("seed"),
        record.get("repetition"),
    )


_RESUME_FIELDS = (
    "phase",
    "measurement_mode",
    "engine",
    "scenario",
    "event_count",
    "seed",
    "repetition",
    "workload_sha256",
    "implementation_fingerprint_sha256",
    "implementation_fingerprint_files",
    "harness_fingerprint_sha256",
    "harness_fingerprint_files",
    "environment_fingerprint",
    "gc_policy",
    "timeout_policy",
    "controller_protocol_version",
)


def _resume_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in _RESUME_FIELDS)


def _read_jsonl_strict(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise ValueError("truncated JSONL: final record lacks newline terminator")
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(data.splitlines(), 1):
        try:
            line = raw_line.decode("utf-8")
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"malformed JSONL record at line {line_number}: {exc}") from exc
        if type(record) is not dict:
            raise ValueError(f"JSONL record at line {line_number} is not an object")
        records.append(record)
    return records


def _validate_resume_records(
    records: list[dict[str, Any]], templates: list[dict[str, Any]]
) -> dict[tuple[Any, ...], dict[str, Any]]:
    expected = {_logical_key(template): template for template in templates}
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    terminal = {"completed", "timed_out", "skipped_after_timeout", "skipped_global_budget"}
    for line_number, record in enumerate(records, 1):
        logical = _logical_key(record)
        if logical in indexed:
            raise ValueError(f"duplicate logical repetition at JSONL line {line_number}: {logical}")
        template = expected.get(logical)
        if template is None:
            raise ValueError(f"unexpected repetition at JSONL line {line_number}: {logical}")
        if _resume_key(record) != _resume_key(template):
            raise ValueError(f"contradictory resume identity at JSONL line {line_number}: {logical}")
        if record.get("status") not in terminal:
            raise ValueError(
                f"nonterminal or failed record requires investigation at line {line_number}: "
                f"{record.get('status')}"
            )
        if record["status"] == "completed":
            if type(record.get("engine_seconds")) not in (int, float):
                raise ValueError(f"completed record lacks engine duration at line {line_number}")
            if type(record.get("snapshot_digest")) is not str:
                raise ValueError(f"completed record lacks snapshot digest at line {line_number}")
        if record["status"] in {"completed", "timed_out"} and type(
            record.get("controller_wall_seconds")
        ) not in (int, float):
            raise ValueError(f"attempted record lacks controller wall duration at line {line_number}")
        if type(record.get("controller_session_id")) is not str or not record[
            "controller_session_id"
        ]:
            raise ValueError(f"record lacks controller session ID at line {line_number}")
        if type(record.get("session_elapsed_seconds")) not in (int, float):
            raise ValueError(f"record lacks session elapsed time at line {line_number}")
        indexed[logical] = record

    timed_out_at: dict[tuple[Any, ...], int] = {}
    for record in records:
        if record["status"] == "timed_out":
            config = (
                record["engine"],
                record["scenario"],
                record["event_count"],
                record["seed"],
            )
            if config in timed_out_at:
                raise ValueError(f"configuration contains multiple timeout records: {config}")
            timed_out_at[config] = record["repetition"]
    for record in records:
        config = (
            record["engine"],
            record["scenario"],
            record["event_count"],
            record["seed"],
        )
        timeout_repetition = timed_out_at.get(config)
        if timeout_repetition is not None and record["repetition"] > timeout_repetition:
            if record["status"] != "skipped_after_timeout":
                raise ValueError(
                    f"configuration has non-skipped record after timeout: {config}, "
                    f"repetition {record['repetition']}"
                )
        if record["status"] == "skipped_after_timeout":
            if timeout_repetition is None or record["repetition"] <= timeout_repetition:
                raise ValueError(
                    f"skipped_after_timeout lacks an earlier timeout: {config}, "
                    f"repetition {record['repetition']}"
                )
    return indexed


def _base_record(index: int, run: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": "pilot",
        "planned_index": index,
        "engine": run["engine"],
        "scenario": run["scenario"],
        "event_count": run["events"],
        "seed": run["seed"],
        "workload_id": run["workload_id"],
        "status": None,
        "engine_seconds": None,
        "controller_wall_seconds": None,
        "preparation_seconds": None,
        "processing_timeout_seconds": run["processing_timeout"],
        "preparation_timeout_seconds": run["preparation_timeout"],
        "stop_reason": None,
        "snapshot_digest": None,
        "event_stream_digest": None,
        "workload_sha256": None,
        "final_active_orders": None,
        "last_accepted_seq": None,
        "worker_pid": None,
        "gc_policy": "collect_once_then_enabled",
        "environment": environment,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _execute_run(
    index: int,
    run: dict[str, Any],
    environment: dict[str, Any],
    global_start: float,
    global_limit: float,
    record_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = (
        dict(record_template)
        if record_template is not None
        else _base_record(index, run, environment)
    )
    record["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    workload = PROJECT_ROOT / run["workload_id"]
    nonce = uuid.uuid4().hex
    command = [
        sys.executable,
        str(WORKER),
        "--engine", run["engine"],
        "--workload", str(workload),
        "--workload-id", run["workload_id"],
        "--expected-events", str(run["events"]),
        "--nonce", nonce,
    ]
    worker_start = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    record["worker_pid"] = process.pid
    messages: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []
    assert process.stdout is not None and process.stderr is not None
    threading.Thread(target=_reader, args=(process.stdout, messages), daemon=True).start()
    threading.Thread(target=_stderr_reader, args=(process.stderr, stderr_lines), daemon=True).start()

    try:
        remaining_global = global_limit - (time.perf_counter() - global_start)
        preparation_window = min(run["preparation_timeout"], remaining_global)
        try:
            ready = _receive(messages, preparation_window)
        except queue.Empty:
            record["status"] = "preparation_timeout"
            record["stop_reason"] = (
                "global_wall_clock_ceiling_during_preparation"
                if remaining_global <= run["preparation_timeout"]
                else "preparation_timeout"
            )
            return record
        except (EOFError, json.JSONDecodeError, ValueError) as exc:
            record["status"] = "failed"
            record["stop_reason"] = f"preparation_protocol_error:{type(exc).__name__}:{exc}"
            return record
        if ready.get("type") == "ERROR":
            record["status"] = "failed"
            record["stop_reason"] = f"worker_{ready.get('stage')}:{ready.get('error_type')}:{ready.get('message')}"
            return record
        if ready.get("type") != "READY" or ready.get("nonce") != nonce:
            record["status"] = "handshake_failed"
            record["stop_reason"] = "invalid_READY_message"
            return record
        if ready.get("event_count") != run["events"] or ready.get("gc_enabled") is not True:
            record["status"] = "failed"
            record["stop_reason"] = "READY_invariant_failed"
            return record

        if (
            record.get("workload_sha256") is not None
            and ready.get("workload_sha256") != record["workload_sha256"]
        ):
            record["status"] = "failed"
            record["stop_reason"] = "worker_workload_hash_differs_from_verified_plan"
            return record
        for field in ("preparation_seconds", "event_stream_digest", "workload_sha256"):
            record[field] = ready.get(field)
        assert process.stdin is not None
        process.stdin.write(json.dumps({"type": "START", "nonce": nonce}) + "\n")
        process.stdin.flush()

        remaining_global = global_limit - (time.perf_counter() - global_start)
        try:
            started = _receive(messages, min(5.0, remaining_global))
        except (queue.Empty, EOFError, json.JSONDecodeError, ValueError) as exc:
            record["status"] = "handshake_failed"
            record["stop_reason"] = f"STARTED_error:{type(exc).__name__}:{exc}"
            return record
        if started != {"type": "STARTED", "nonce": nonce}:
            record["status"] = "handshake_failed"
            record["stop_reason"] = "invalid_STARTED_message"
            return record

        processing_controller_start = time.perf_counter()
        remaining_global = global_limit - (processing_controller_start - global_start)
        processing_window = min(run["processing_timeout"], remaining_global)
        try:
            done = _receive(messages, processing_window)
        except queue.Empty:
            record["status"] = "timed_out"
            record["stop_reason"] = (
                "global_wall_clock_ceiling_during_processing"
                if remaining_global <= run["processing_timeout"]
                else "processing_timeout"
            )
            return record
        except (EOFError, json.JSONDecodeError, ValueError) as exc:
            record["status"] = "failed"
            record["stop_reason"] = f"processing_protocol_error:{type(exc).__name__}:{exc}"
            return record
        if done.get("type") == "ERROR":
            record["status"] = "failed"
            record["stop_reason"] = f"worker_{done.get('stage')}:{done.get('error_type')}:{done.get('message')}"
            return record
        if done.get("type") != "DONE" or done.get("nonce") != nonce:
            record["status"] = "failed"
            record["stop_reason"] = "invalid_DONE_message"
            return record
        record.update(
            status="completed",
            engine_seconds=done.get("engine_seconds"),
            snapshot_digest=done.get("snapshot_digest"),
            final_active_orders=done.get("final_active_orders"),
            last_accepted_seq=done.get("last_accepted_seq"),
            stop_reason=None,
        )
        return record
    except (BrokenPipeError, OSError, subprocess.SubprocessError) as exc:
        record["status"] = "failed"
        record["stop_reason"] = f"controller_worker_error:{type(exc).__name__}:{exc}"
        return record
    finally:
        _stop_worker(process)
        record["controller_wall_seconds"] = time.perf_counter() - worker_start
        if record["status"] != "completed" and stderr_lines:
            record["worker_stderr_tail"] = stderr_lines[-10:]


def run_pilot(output: Path, global_limit: float) -> int:
    if global_limit <= 0 or global_limit > MAX_GLOBAL_SECONDS:
        raise ValueError(f"global limit must be in (0, {MAX_GLOBAL_SECONDS}]")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing pilot output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = _environment()
    plan = _plan()
    global_start = time.perf_counter()
    records: list[dict[str, Any]] = []
    active_processes: list[subprocess.Popen[str]] = []
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            for index, run in enumerate(plan, 1):
                if time.perf_counter() - global_start >= global_limit:
                    record = _base_record(index, run, environment)
                    record["status"] = "skipped_global_budget"
                    record["stop_reason"] = "global_wall_clock_ceiling_reached_before_start"
                else:
                    record = _execute_run(index, run, environment, global_start, global_limit)
                record["global_elapsed_seconds"] = time.perf_counter() - global_start
                records.append(record)
                _write_record(stream, record)
    finally:
        for process in active_processes:
            _stop_worker(process)

    total = time.perf_counter() - global_start
    summary = {
        "phase": "pilot",
        "planned_runs": len(plan),
        "written_records": len(records),
        "statuses": dict(Counter(record["status"] for record in records)),
        "total_wall_seconds": total,
        "output": output.relative_to(PROJECT_ROOT).as_posix(),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if len(records) == len(plan) else 1


def _configuration_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["engine"],
        record["scenario"],
        record["event_count"],
        record["seed"],
    )


def _terminal_record(
    template: dict[str, Any], status: str, reason: str
) -> dict[str, Any]:
    record = dict(template)
    record.update(
        status=status,
        stop_reason=reason,
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        controller_wall_seconds=None,
        global_elapsed_seconds=None,
    )
    return record


def _charged_wall_seconds(records: list[dict[str, Any]]) -> float:
    session_elapsed: dict[str, float] = {}
    for record in records:
        session_id = record["controller_session_id"]
        elapsed = float(record["session_elapsed_seconds"])
        session_elapsed[session_id] = max(session_elapsed.get(session_id, 0.0), elapsed)
    return sum(session_elapsed.values())


def _print_final_dry_run(
    output: Path,
    plan: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    existing: dict[tuple[Any, ...], dict[str, Any]],
    unique_workloads: int,
    budget: float,
) -> None:
    timed_out_configs = {
        _configuration_key(record)
        for record in existing.values()
        if record["status"] == "timed_out"
    }
    status_counts: Counter[str] = Counter()
    for run, template in zip(plan, templates, strict=True):
        logical = _logical_key(template)
        if logical in existing:
            state = f"existing_{existing[logical]['status']}"
        elif _configuration_key(template) in timed_out_configs:
            state = "would_record_skipped_after_timeout"
        else:
            state = "planned"
        status_counts[state] += 1
        print(
            "DRY_RUN "
            + json.dumps(
                {
                    "planned_index": template["planned_index"],
                    "engine": template["engine"],
                    "scenario": template["scenario"],
                    "event_count": template["event_count"],
                    "seed": template["seed"],
                    "repetition": template["repetition"],
                    "workload_id": template["workload_id"],
                    "output": output.relative_to(PROJECT_ROOT).as_posix(),
                    "state": state,
                },
                sort_keys=True,
            )
        )
    summary = {
        "mode": "dry_run",
        "phase": FINAL_PHASE,
        "measurement_mode": FINAL_MODE,
        "planned_repetitions": len(plan),
        "engine_workload_configurations": len(
            {
                (run["engine"], run["scenario"], run["events"], run["seed"])
                for run in plan
            }
        ),
        "unique_workloads": unique_workloads,
        "event_count_distribution": dict(Counter(run["events"] for run in plan)),
        "engine_distribution": dict(Counter(run["engine"] for run in plan)),
        "resume_states": dict(status_counts),
        "existing_records": len(existing),
        "charged_wall_seconds": _charged_wall_seconds(list(existing.values())),
        "cumulative_budget_seconds": budget,
        "output_exists": output.exists(),
    }
    print("DRY_RUN_SUMMARY " + json.dumps(summary, sort_keys=True))


def run_final(
    output: Path,
    budget: float,
    resume: bool,
    dry_run: bool,
) -> int:
    if budget <= 0 or budget > FINAL_GLOBAL_SECONDS:
        raise ValueError(f"final cumulative budget must be in (0, {FINAL_GLOBAL_SECONDS}]")
    environment = _environment()
    plan = _final_plan()
    templates, unique_workloads = _final_templates(plan, environment)
    if len(plan) != 450:
        raise AssertionError(f"final plan must contain 450 repetitions, found {len(plan)}")

    existing_records: list[dict[str, Any]] = []
    if output.exists():
        existing_records = _read_jsonl_strict(output)
    elif resume and not dry_run:
        raise FileNotFoundError(f"resume requested but final output is absent: {output}")
    existing = _validate_resume_records(existing_records, templates)

    if dry_run:
        _print_final_dry_run(
            output, plan, templates, existing, unique_workloads, budget
        )
        return 0
    if output.exists() and not resume:
        raise FileExistsError(
            f"final output exists; refuse overwrite and require --resume: {output}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    charged_before = _charged_wall_seconds(existing_records)
    if charged_before > budget:
        raise ValueError(
            f"existing charged wall time {charged_before} exceeds budget {budget}"
        )
    session_allowance = budget - charged_before
    session_start = time.perf_counter()
    controller_session_id = uuid.uuid4().hex
    timed_out_configs = {
        _configuration_key(record)
        for record in existing.values()
        if record["status"] == "timed_out"
    }
    global_budget_recorded = any(
        record["status"] == "skipped_global_budget" for record in existing.values()
    )
    written = 0
    stream_mode = "a" if output.exists() else "x"
    with output.open(stream_mode, encoding="utf-8", newline="\n") as stream:
        for index, (run, template) in enumerate(
            zip(plan, templates, strict=True), 1
        ):
            logical = _logical_key(template)
            if logical in existing:
                continue
            config = _configuration_key(template)
            elapsed_session = time.perf_counter() - session_start
            if config in timed_out_configs:
                record = _terminal_record(
                    template,
                    "skipped_after_timeout",
                    "earlier_repetition_timed_out_for_configuration",
                )
            elif global_budget_recorded or elapsed_session >= session_allowance:
                global_budget_recorded = True
                record = _terminal_record(
                    template,
                    "skipped_global_budget",
                    "cumulative_primary_wall_clock_budget_exhausted",
                )
            else:
                record = _execute_run(
                    index,
                    run,
                    environment,
                    session_start,
                    session_allowance,
                    record_template=template,
                )
                if record["status"] == "timed_out":
                    timed_out_configs.add(config)
                    if record.get("stop_reason") == "global_wall_clock_ceiling_during_processing":
                        global_budget_recorded = True

            record["global_elapsed_seconds"] = time.perf_counter() - session_start
            record["controller_session_id"] = controller_session_id
            record["session_elapsed_seconds"] = record["global_elapsed_seconds"]
            record["cumulative_controller_wall_seconds"] = (
                charged_before + record["session_elapsed_seconds"]
            )
            _write_record(stream, record)
            existing[logical] = record
            written += 1
            if record["status"] not in {
                "completed",
                "timed_out",
                "skipped_after_timeout",
                "skipped_global_budget",
            }:
                print(
                    json.dumps(
                        {
                            "phase": FINAL_PHASE,
                            "status": "stopped_for_investigation",
                            "record_status": record["status"],
                            "logical_key": logical,
                            "output": output.relative_to(PROJECT_ROOT).as_posix(),
                        },
                        sort_keys=True,
                    )
                )
                return 2

    final_records = _read_jsonl_strict(output)
    _validate_resume_records(final_records, templates)
    summary = {
        "phase": FINAL_PHASE,
        "measurement_mode": FINAL_MODE,
        "planned_repetitions": len(plan),
        "total_records": len(final_records),
        "written_this_session": written,
        "statuses": dict(Counter(record["status"] for record in final_records)),
        "charged_wall_seconds": _charged_wall_seconds(final_records),
        "cumulative_budget_seconds": budget,
        "output": output.relative_to(PROJECT_ROOT).as_posix(),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    pilot = subparsers.add_parser("pilot", help="run the approved 16-run pilot")
    pilot.add_argument("--output", type=Path, required=True)
    pilot.add_argument("--global-timeout-seconds", type=float, default=MAX_GLOBAL_SECONDS)
    final = subparsers.add_parser(
        "final", help="plan, start, or resume final primary timing"
    )
    final.add_argument("--output", type=Path, required=True)
    final.add_argument(
        "--global-budget-seconds", type=float, default=FINAL_GLOBAL_SECONDS
    )
    final.add_argument(
        "--dry-run",
        action="store_true",
        help="verify and list the complete plan without replay or result writes",
    )
    final.add_argument(
        "--resume",
        action="store_true",
        help="append after strict verification of existing final records",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if args.mode == "pilot":
        return run_pilot(output.resolve(), args.global_timeout_seconds)
    if args.mode == "final":
        return run_final(
            output.resolve(),
            args.global_budget_seconds,
            args.resume,
            args.dry_run,
        )
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
