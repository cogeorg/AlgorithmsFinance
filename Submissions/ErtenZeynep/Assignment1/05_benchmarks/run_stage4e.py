"""Plan, execute, resume, and verify the isolated Stage 4E experiments.

Dry-run and self-test modes never launch a worker or create result files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve().with_name("_stage4e_worker.py")
RESULTS_ROOT = PROJECT_ROOT / "07_results" / "stage4e"
PROTOCOL = "stage4e-v1"
GLOBAL_BUDGET_SECONDS = 4_500.0
MODE_BUDGETS = {
    "latency": 900.0,
    "memory": 600.0,
    "liquidation": 600.0,
    "concentration": 1_800.0,
    "diagnostics": 300.0,
}
VERIFICATION_RESERVE_SECONDS = 300.0
MODE_FILES = {
    "latency": "latency_runs.jsonl",
    "memory": "memory.jsonl",
    "liquidation": "liquidation.jsonl",
    "concentration": "concentration.jsonl",
    "diagnostics": "diagnostics.jsonl",
}
COMPLETED_RESULT_FIELDS = {
    "latency": {"instrumented_replay_seconds", "observations", "summary", "raw_path", "raw_bytes", "raw_sha256"},
    "memory": {"traced_replay_seconds", "traced_current_bytes", "traced_peak_bytes", "active_order_peak", "occupied_price_level_peak", "post_stream", "boundary"},
    "liquidation": {"construction_seconds", "liquidation_seconds", "active_bid_depth_units", "liquidation_quantity_units", "fill_count", "makers_touched", "price_levels_visited", "unfilled_qty_units", "proceeds_tick_quantity_units", "oracle_verified"},
    "concentration": {"engine_seconds", "active_order_peak", "occupied_price_level_peak", "maximum_fifo_length"},
    "diagnostics": {"diagnostic_seconds", "operation_counts", "operation_count_semantics", "active_order_peak", "occupied_price_level_peak"},
}
ENGINES = ("baseline", "optimized")
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
WARMUP_WORKLOAD = "02_data/generated/mixed_1000_seed42.jsonl.gz"
IMPLEMENTATION_SHARED = ("validation.py", "contracts.py", "__init__.py")
HARNESS_FILES = (
    "05_benchmarks/run_stage4e.py",
    "05_benchmarks/_stage4e_worker.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fingerprint(paths: list[str]) -> dict[str, Any]:
    files = [
        {"path": name.replace("\\", "/"), "sha256": _sha256(PROJECT_ROOT / name)}
        for name in paths
    ]
    return {"algorithm": "sha256-stable-json-v1", "files": files, "sha256": _stable_digest(files)}


def _implementation_fingerprint(engine: str) -> dict[str, Any]:
    paths = [f"04_implementation/orderbook/{engine if engine == 'optimized' else 'baseline'}.py"]
    paths.extend(f"04_implementation/orderbook/{name}" for name in IMPLEMENTATION_SHARED)
    return _fingerprint(paths)


def _environment() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
    }


def _workload(scenario: str, events: int, seed: int, paired: bool = False) -> str:
    suffix = "_levels4_paired" if paired else ""
    if events == 10_000 and seed == 42 and not paired:
        return f"02_data/supplied/data/{scenario}_10000.jsonl.gz"
    return f"02_data/generated/{scenario}_{events}_seed{seed}{suffix}.jsonl.gz"


def _base(
    mode: str,
    scenario: str,
    events: int,
    seed: int,
    engine: str,
    repetition: int,
    *,
    paired: bool = False,
) -> dict[str, Any]:
    if events == 100_000:
        processing_timeout, preparation_timeout = 120.0, 45.0
    else:
        processing_timeout, preparation_timeout = 30.0, 15.0
    if mode == "latency":
        processing_timeout = 60.0
    elif mode == "memory":
        processing_timeout = 180.0
    elif mode == "diagnostics":
        processing_timeout = 120.0
    elif mode == "liquidation":
        processing_timeout, preparation_timeout = 30.0, 30.0
    item = {
        "mode": mode,
        "scenario": scenario,
        "event_count": events,
        "seed": seed,
        "engine": engine,
        "repetition": repetition,
        "variant": "levels4_paired" if paired else "original",
        "workload_id": _workload(scenario, events, seed, paired),
        "warmup_workload_id": WARMUP_WORKLOAD,
        "processing_timeout_seconds": processing_timeout,
        "preparation_timeout_seconds": preparation_timeout,
    }
    if mode == "liquidation":
        item["construction_timeout_seconds"] = 30.0
        item["sale_timeout_seconds"] = 30.0
    return item


def plans() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {name: [] for name in MODE_FILES}
    for scenario in SCENARIOS:
        for engine in ENGINES:
            for repetition in range(1, 6):
                result["latency"].append(_base("latency", scenario, 10_000, 42, engine, repetition))
    for scenario, events in (("buildup", 10_000), ("cancel_churn", 100_000)):
        for engine in ENGINES:
            result["memory"].append(_base("memory", scenario, events, 42, engine, 1))
    for engine in ENGINES:
        for ratio in (10, 100, 200):
            for repetition in range(1, 6):
                item = _base("liquidation", "buildup", 10_000, 42, engine, repetition)
                item["ratio_percent"] = ratio
                result["liquidation"].append(item)
    for events in (10_000, 100_000):
        for seed in (42, 43, 44):
            for paired in (False, True):
                for engine in ENGINES:
                    for repetition in range(1, 6):
                        result["concentration"].append(
                            _base("concentration", "buildup", events, seed, engine, repetition, paired=paired)
                        )
    for scenario, events in (
        ("buildup", 10_000),
        ("crowded", 10_000),
        ("sweep", 10_000),
        ("cancel_churn", 100_000),
    ):
        for engine in ENGINES:
            result["diagnostics"].append(_base("diagnostics", scenario, events, 42, engine, 1))
    return result


def _key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["mode"], item["scenario"], item["event_count"], item["seed"],
        item["engine"], item["variant"], item.get("ratio_percent"), item["repetition"],
    )


def _identity(plan: dict[str, Any], workload_hash: str) -> dict[str, Any]:
    implementation = _implementation_fingerprint(plan["engine"])
    harness = _fingerprint(list(HARNESS_FILES))
    environment = _environment()
    return {
        "protocol_version": PROTOCOL,
        "workload_sha256": workload_hash,
        "implementation_fingerprint": implementation,
        "harness_fingerprint": harness,
        "environment": environment,
        "environment_fingerprint": _stable_digest(environment),
        "warmup_policy": {
            "workload_id": WARMUP_WORKLOAD,
            "engine": "disposable_same_class",
            "measured_engine": "fresh_empty_after_gc_collect",
        },
        "budget_policy": {
            "global_seconds": GLOBAL_BUDGET_SECONDS,
            "mode_seconds": MODE_BUDGETS,
            "verification_reserve_seconds": VERIFICATION_RESERVE_SECONDS,
        },
        "timeout_policy": {
            "preparation_seconds": plan["preparation_timeout_seconds"],
            "processing_seconds": plan["processing_timeout_seconds"],
            "construction_seconds": plan.get("construction_timeout_seconds"),
            "sale_seconds": plan.get("sale_timeout_seconds"),
        },
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise ValueError(f"truncated JSONL (missing final newline): {path}")
    records = []
    for number, raw in enumerate(data.splitlines(), 1):
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL line {number}: {path}") from exc
        if type(item) is not dict:
            raise ValueError(f"non-object JSONL line {number}: {path}")
        records.append(item)
    return records


def _validate_records(records: list[dict[str, Any]], expected: dict[tuple[Any, ...], dict[str, Any]]) -> None:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    timed_out_configs: set[tuple[Any, ...]] = set()
    allowed_statuses = {
        "completed", "timed_out", "skipped_after_timeout",
        "skipped_mode_budget", "skipped_global_budget", "failed",
    }
    for record in records:
        key = _key(record)
        if key not in expected:
            raise ValueError(f"record is not in the approved plan: {key}")
        if key in seen:
            label = "contradictory" if seen[key] != record else "duplicate"
            raise ValueError(f"{label} record: {key}")
        for name in ("protocol_version", "workload_sha256", "implementation_fingerprint", "harness_fingerprint", "environment_fingerprint", "budget_policy", "timeout_policy"):
            if record.get(name) != expected[key].get(name):
                raise ValueError(f"resume identity mismatch for {name}: {key}")
        status = record.get("status")
        if status not in allowed_statuses:
            raise ValueError(f"invalid record status {status!r}: {key}")
        if record.get("phase") != "stage4e" or record.get("measurement_mode") != record.get("mode"):
            raise ValueError(f"invalid phase or measurement mode: {key}")
        if record.get("version") != record.get("engine"):
            raise ValueError(f"invalid implementation version label: {key}")
        configuration = key[:-1]
        if status == "skipped_after_timeout" and configuration not in timed_out_configs:
            raise ValueError(f"skip appears before configuration timeout: {key}")
        if configuration in timed_out_configs and status != "skipped_after_timeout":
            raise ValueError(f"non-skip appears after configuration timeout: {key}")
        if status == "timed_out":
            timed_out_configs.add(configuration)
        if status == "completed":
            result = record.get("result")
            if type(result) is not dict:
                raise ValueError(f"completed record lacks result object: {key}")
            missing = COMPLETED_RESULT_FIELDS[record["mode"]] - result.keys()
            if missing:
                raise ValueError(f"completed result lacks fields {sorted(missing)}: {key}")
            duration_field = {
                "latency": "instrumented_replay_seconds",
                "memory": "traced_replay_seconds",
                "liquidation": "liquidation_seconds",
                "concentration": "engine_seconds",
                "diagnostics": "diagnostic_seconds",
            }[record["mode"]]
            if not isinstance(result[duration_field], (int, float)) or result[duration_field] <= 0:
                raise ValueError(f"completed result has invalid duration: {key}")
        if status == "timed_out" and type(record.get("result")) is dict:
            fabricated = {
                "instrumented_replay_seconds", "traced_replay_seconds",
                "liquidation_seconds", "engine_seconds", "diagnostic_seconds",
            } & record["result"].keys()
            if fabricated:
                raise ValueError(f"timed-out record contains completed duration fields: {key}")
        if status.startswith("skipped_") and float(record.get("controller_wall_seconds", -1)) != 0.0:
            raise ValueError(f"skipped record has nonzero controller time: {key}")
        seen[key] = record


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _reader(stream: TextIO, messages: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            messages.put(line)
    finally:
        messages.put(None)


def _receive(messages: queue.Queue[str | None], timeout: float) -> dict[str, Any]:
    line = messages.get(timeout=max(0.001, timeout))
    if line is None:
        raise RuntimeError("worker output closed unexpectedly")
    value = json.loads(line)
    if type(value) is not dict:
        raise RuntimeError("worker emitted a non-object")
    return value


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _run_worker(spec: dict[str, Any]) -> tuple[str, dict[str, Any], float]:
    nonce = spec["nonce"]
    started = time.perf_counter()
    process = subprocess.Popen(
        [sys.executable, str(WORKER), nonce], cwd=str(PROJECT_ROOT),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    assert process.stdin and process.stdout and process.stderr
    messages: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []
    threading.Thread(target=_reader, args=(process.stdout, messages), daemon=True).start()
    threading.Thread(target=lambda: stderr_lines.extend(line.rstrip() for line in process.stderr), daemon=True).start()
    stage = "preparation"
    try:
        process.stdin.write(json.dumps(spec, separators=(",", ":")) + "\n")
        process.stdin.flush()
        ready = _receive(messages, spec["preparation_timeout_seconds"])
        if ready.get("type") != "READY" or ready.get("nonce") != nonce:
            raise RuntimeError(f"invalid READY message: {ready}")
        if ready.get("workload_sha256") != spec["workload_sha256"]:
            raise RuntimeError("worker workload hash differs from controller hash")
        stage = "handshake"
        process.stdin.write(json.dumps({"type": "START", "nonce": nonce}) + "\n")
        process.stdin.flush()
        started_message = _receive(messages, 5.0)
        if started_message != {"type": "STARTED", "nonce": nonce}:
            raise RuntimeError(f"invalid STARTED message: {started_message}")
        stage = "liquidation_construction" if spec["mode"] == "liquidation" else "measurement"
        message = _receive(
            messages,
            spec.get("construction_timeout_seconds", spec["processing_timeout_seconds"]),
        )
        construction_evidence: dict[str, Any] | None = None
        if spec["mode"] == "liquidation":
            if message.get("type") != "CONSTRUCTED" or message.get("nonce") != nonce:
                raise RuntimeError(f"invalid CONSTRUCTED message: {message}")
            construction_evidence = dict(message)
            process.stdin.write(json.dumps({"type": "LIQUIDATE", "nonce": nonce}) + "\n")
            process.stdin.flush()
            stage = "liquidation_sale"
            message = _receive(messages, spec["sale_timeout_seconds"])
        if message.get("type") == "ERROR":
            raise RuntimeError(f"worker error: {message}")
        if message.get("type") != "DONE" or message.get("nonce") != nonce:
            raise RuntimeError(f"invalid DONE message: {message}")
        process.wait(timeout=5)
        if process.returncode != 0:
            raise RuntimeError(f"worker exited {process.returncode}: {stderr_lines[-10:]}")
        result = dict(message["result"])
        result["worker_preparation"] = ready
        return "completed", result, time.perf_counter() - started
    except queue.Empty:
        _stop(process)
        timed_stages = {"measurement", "liquidation_construction", "liquidation_sale"}
        status = "timed_out" if stage in timed_stages else "failed"
        detail: dict[str, Any] = {"timeout_stage": stage, "stderr_tail": stderr_lines[-10:]}
        if stage == "liquidation_sale" and construction_evidence is not None:
            detail["construction_evidence"] = construction_evidence
        return status, detail, time.perf_counter() - started
    finally:
        _stop(process)


def _expected(mode: str) -> tuple[list[dict[str, Any]], dict[tuple[Any, ...], dict[str, Any]]]:
    selected = plans()[mode]
    expected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for plan in selected:
        path = PROJECT_ROOT / plan["workload_id"]
        if not path.is_file():
            raise FileNotFoundError(path)
        identity = _identity(plan, _sha256(path))
        expected[_key(plan)] = {**plan, **identity}
    return selected, expected


def _charged(results_root: Path, mode: str | None = None) -> float:
    names = [mode] if mode else list(MODE_FILES)
    total = 0.0
    for name in names:
        for record in _read_jsonl(results_root / MODE_FILES[name]):
            total += float(record.get("controller_wall_seconds", 0.0))
    return total


def _attempt_reserve(plan: dict[str, Any]) -> float:
    measurement_seconds = (
        plan["construction_timeout_seconds"] + plan["sale_timeout_seconds"]
        if plan["mode"] == "liquidation"
        else plan["processing_timeout_seconds"]
    )
    return plan["preparation_timeout_seconds"] + 5.0 + measurement_seconds + 5.0


def _latency_raw_path(results_root: Path, plan: dict[str, Any]) -> str:
    raw = results_root / "latency_raw" / (
        f"{plan['scenario']}_{plan['engine']}_rep{plan['repetition']}.csv.gz"
    )
    return raw.relative_to(PROJECT_ROOT).as_posix()


def _validate_latency_artifact(record: dict[str, Any], results_root: Path) -> None:
    result = record["result"]
    raw = (PROJECT_ROOT / result["raw_path"]).resolve()
    try:
        raw.relative_to(results_root)
    except ValueError as exc:
        raise ValueError(f"latency artifact is outside results root: {raw}") from exc
    if not raw.is_file() or raw.stat().st_size != result["raw_bytes"] or _sha256(raw) != result["raw_sha256"]:
        raise ValueError(f"latency artifact mismatch: {raw}")


def _validated_existing(
    results_root: Path,
) -> dict[str, tuple[list[dict[str, Any]], dict[tuple[Any, ...], dict[str, Any]], list[dict[str, Any]]]]:
    state = {}
    for mode in MODE_FILES:
        selected, expected = _expected(mode)
        records = _read_jsonl(results_root / MODE_FILES[mode])
        _validate_records(records, expected)
        if mode == "latency":
            for record in records:
                if record.get("status") != "completed":
                    continue
                _validate_latency_artifact(record, results_root)
        if any(record.get("status") == "failed" for record in records):
            raise RuntimeError(f"{mode} contains a failed record requiring manual inspection")
        state[mode] = (selected, expected, records)
    return state


def execute(mode: str, results_root: Path, resume: bool) -> None:
    selected, expected, existing = _validated_existing(results_root)[mode]
    output = results_root / MODE_FILES[mode]
    if existing and not resume:
        raise FileExistsError(f"result file exists; use --resume: {output}")
    completed = {_key(record) for record in existing}
    timed_out_configs = {
        _key(record)[:-1] for record in existing if record.get("status") == "timed_out"
    }
    global_used = _charged(results_root)
    mode_used = _charged(results_root, mode)
    session = str(uuid.uuid4())
    for plan in selected:
        key = _key(plan)
        if key in completed:
            continue
        identity = expected[key]
        base = {**plan, **{name: identity[name] for name in identity if name not in plan}}
        base.update({
            "phase": "stage4e",
            "measurement_mode": mode,
            "version": plan["engine"],
            "controller_session_id": session,
            "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        if key[:-1] in timed_out_configs:
            _append(output, {**base, "status": "skipped_after_timeout", "controller_wall_seconds": 0.0})
            continue
        reserve = _attempt_reserve(plan)
        if global_used + reserve > GLOBAL_BUDGET_SECONDS:
            _append(output, {**base, "status": "skipped_global_budget", "controller_wall_seconds": 0.0})
            continue
        if mode_used + reserve > MODE_BUDGETS[mode]:
            _append(output, {**base, "status": "skipped_mode_budget", "controller_wall_seconds": 0.0})
            continue
        nonce = uuid.uuid4().hex
        spec = {**base, "nonce": nonce}
        if mode == "latency":
            spec["latency_raw_path"] = _latency_raw_path(results_root, plan)
        attempt_started = time.perf_counter()
        try:
            status, result, wall = _run_worker(spec)
        except BaseException as exc:
            wall = time.perf_counter() - attempt_started
            status = "failed"
            result = {"error_type": type(exc).__name__, "message": str(exc)}
        global_used += wall
        mode_used += wall
        record = {**base, "status": status, "controller_wall_seconds": wall, "result": result}
        _append(output, record)
        if status == "timed_out":
            timed_out_configs.add(key[:-1])
        elif status == "failed":
            raise RuntimeError(f"worker failed; inspect the final record before any resume: {key}")
        print(json.dumps({"key": key, "status": status, "global_used": global_used}, default=str))


def verify(results_root: Path, global_budget_seconds: float) -> None:
    summary: dict[str, Any] = {}
    for mode in MODE_FILES:
        selected, expected = _expected(mode)
        records = _read_jsonl(results_root / MODE_FILES[mode])
        _validate_records(records, expected)
        for record in records:
            result = record.get("result", {})
            if record.get("status") == "completed" and mode == "latency":
                raw = PROJECT_ROOT / result["raw_path"]
                if raw.stat().st_size != result["raw_bytes"] or _sha256(raw) != result["raw_sha256"]:
                    raise ValueError(f"latency artifact mismatch: {raw}")
        summary[mode] = {"planned": len(selected), "recorded": len(records), "statuses": dict(Counter(r.get("status") for r in records))}
    summary["charged_seconds"] = _charged(results_root)
    summary["global_budget_seconds"] = global_budget_seconds
    print(json.dumps(summary, indent=2, sort_keys=True))


def dry_run(global_budget_seconds: float) -> None:
    all_plans = plans()
    summary = {
        mode: {
            "planned": len(items),
            "configurations": len({_key(item)[:-1] for item in items}),
            "workloads": len({item["workload_id"] for item in items}),
            "engines": sorted({item["engine"] for item in items}),
        }
        for mode, items in all_plans.items()
    }
    summary["total_planned"] = sum(len(items) for items in all_plans.values())
    summary["mode_budgets_seconds"] = MODE_BUDGETS
    summary["verification_reserve_seconds"] = VERIFICATION_RESERVE_SECONDS
    summary["mode_plus_verification_sum_seconds"] = sum(MODE_BUDGETS.values()) + VERIFICATION_RESERVE_SECONDS
    summary["shared_global_ceiling_seconds"] = global_budget_seconds
    print(json.dumps(summary, indent=2, sort_keys=True))


def self_test() -> None:
    assert {mode: len(items) for mode, items in plans().items()} == {
        "latency": 50, "memory": 4, "liquidation": 30, "concentration": 120, "diagnostics": 8,
    }
    assert sum(MODE_BUDGETS.values()) + VERIFICATION_RESERVE_SECONDS == GLOBAL_BUDGET_SECONDS
    assert _attempt_reserve(plans()["liquidation"][0]) == 100.0
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as name:
        root = Path(name)
        path = root / "fixture.jsonl"
        sample_result = {"instrumented_replay_seconds": 1.0, "observations": 1, "summary": {}, "raw_path": "x", "raw_bytes": 1, "raw_sha256": "x"}
        sample = {"phase": "stage4e", "measurement_mode": "latency", "version": "baseline", "mode": "latency", "scenario": "x", "event_count": 1, "seed": 1, "engine": "baseline", "variant": "original", "ratio_percent": None, "repetition": 1, "protocol_version": "x", "workload_sha256": "x", "implementation_fingerprint": {}, "harness_fingerprint": {}, "environment_fingerprint": "x", "budget_policy": {}, "status": "completed", "result": sample_result, "controller_wall_seconds": 1.0}
        expected = {_key(sample): dict(sample)}
        path.write_text(json.dumps(sample) + "\n", encoding="utf-8")
        assert _read_jsonl(path) == [sample]
        _validate_records([sample], expected)
        changed_identity = {**sample, "workload_sha256": "changed"}
        try:
            _validate_records([changed_identity], expected)
        except ValueError as exc:
            assert "resume identity mismatch" in str(exc)
        else:
            raise AssertionError("incompatible resume identity accepted")
        timeout = {**sample, "status": "timed_out", "result": {"timeout_stage": "measurement"}}
        skips = [
            {**sample, "repetition": repetition, "status": "skipped_after_timeout", "result": None, "controller_wall_seconds": 0.0}
            for repetition in range(2, 6)
        ]
        timeout_expected = {
            _key(record): {**record, "status": None, "result": None, "controller_wall_seconds": None}
            for record in [timeout, *skips]
        }
        _validate_records([timeout, *skips], timeout_expected)
        try:
            _validate_records(skips, {_key(record): timeout_expected[_key(record)] for record in skips})
        except ValueError as exc:
            assert "before configuration timeout" in str(exc)
        else:
            raise AssertionError("post-timeout skip accepted without a timeout record")
        for invalid, expected_word in (
            ({**sample, "status": "unknown"}, "invalid record status"),
            ({**sample, "phase": "wrong"}, "invalid phase"),
            ({**sample, "version": "wrong"}, "invalid implementation version"),
            ({**sample, "result": {}}, "lacks fields"),
            ({**sample, "status": "skipped_mode_budget", "controller_wall_seconds": 1.0}, "nonzero"),
        ):
            try:
                _validate_records([invalid], expected)
            except ValueError as exc:
                assert expected_word in str(exc)
            else:
                raise AssertionError(f"invalid synthetic record accepted: {expected_word}")
        for status in ("skipped_mode_budget", "skipped_global_budget"):
            skipped = {**sample, "status": status, "result": None, "controller_wall_seconds": 0.0}
            _validate_records([skipped], expected)
        for records, word in (([sample, sample], "duplicate"), ([sample, {**sample, "status": "different"}], "contradictory")):
            try:
                _validate_records(records, expected)
            except ValueError as exc:
                assert word in str(exc)
            else:
                raise AssertionError(f"{word} fixture accepted")
        path.write_text(json.dumps(sample), encoding="utf-8")
        try:
            _read_jsonl(path)
        except ValueError as exc:
            assert "truncated" in str(exc)
        else:
            raise AssertionError("truncated fixture accepted")
        path.write_text("{bad}\n", encoding="utf-8")
        try:
            _read_jsonl(path)
        except ValueError as exc:
            assert "malformed" in str(exc)
        else:
            raise AssertionError("malformed fixture accepted")
        (root / MODE_FILES["latency"]).write_text(
            json.dumps({"controller_wall_seconds": 1.25}) + "\n", encoding="utf-8"
        )
        (root / MODE_FILES["memory"]).write_text(
            json.dumps({"controller_wall_seconds": 2.75}) + "\n", encoding="utf-8"
        )
        assert _charged(root) == 4.0
        assert _charged(root, "memory") == 2.75
        raw = root / "latency.csv.gz"
        raw.write_bytes(b"synthetic-latency")
        artifact_record = {
            "result": {
                "raw_path": raw.relative_to(PROJECT_ROOT).as_posix(),
                "raw_bytes": raw.stat().st_size,
                "raw_sha256": _sha256(raw),
            }
        }
        _validate_latency_artifact(artifact_record, root)
        raw.write_bytes(b"corrupted")
        try:
            _validate_latency_artifact(artifact_record, root)
        except ValueError as exc:
            assert "artifact mismatch" in str(exc)
        else:
            raise AssertionError("corrupted latency artifact accepted")
    custom_root = PROJECT_ROOT / "07_results" / "synthetic_custom_root"
    latency_path = _latency_raw_path(custom_root, plans()["latency"][0])
    assert latency_path.startswith("07_results/synthetic_custom_root/latency_raw/")
    print(json.dumps({
        "status": "passed",
        "planned": 212,
        "workers_launched": 0,
        "checks": [
            "plan_counts", "budget_arithmetic", "liquidation_reservation",
            "valid_resume", "identity_mismatch", "duplicate", "contradictory",
            "timeout_then_skip", "orphan_skip", "invalid_status", "invalid_phase",
            "invalid_version", "incomplete_completed_result", "nonzero_skip_time", "mode_budget_skip", "global_budget_skip",
            "truncated_jsonl", "malformed_jsonl", "cross_mode_charging",
            "custom_results_root_latency_path", "latency_artifact_corruption",
        ],
    }, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=(*MODE_FILES, "verify", "dry-run", "self-test"))
    parser.add_argument("--results-root", type=Path, default=RESULTS_ROOT)
    parser.add_argument(
        "--global-budget-seconds", type=float, default=GLOBAL_BUDGET_SECONDS,
        help="fixed shared Stage 4E ceiling; must be exactly 4500",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.global_budget_seconds != GLOBAL_BUDGET_SECONDS:
        parser.error("--global-budget-seconds must be exactly 4500 for the approved protocol")
    results_root = args.results_root.resolve()
    try:
        results_root.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        parser.error("--results-root must resolve inside the approved project directory")
    if args.mode == "dry-run":
        dry_run(args.global_budget_seconds)
    elif args.mode == "self-test":
        self_test()
    elif args.mode == "verify":
        verify(results_root, args.global_budget_seconds)
    else:
        execute(args.mode, results_root, args.resume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
