"""Preregistered, timeout-bounded, resumable formal experiment execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any

from .benchmarking import environment_metadata


FORMAL_TIMEOUT_SECONDS = 60
TaskSpec = dict[str, object]
Runner = Callable[..., subprocess.CompletedProcess[str]]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PLAN = PROJECT_ROOT / "experiments" / "08_input_plan.json"
MILLION_INPUT_PLAN = PROJECT_ROOT / "experiments" / "11_million_input_plan.json"


def _plan_inputs(path: Path = INPUT_PLAN) -> list[dict[str, Any]]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("input_count") != len(plan.get("inputs", [])):
        raise ValueError("input plan count does not match its entries")
    return plan["inputs"]


def _is_latency_input(spec: Mapping[str, Any]) -> bool:
    return (
        spec["levels"] == 1_000
        and (
            spec["scenario"] == "buildup"
            or (spec["event_count"] == 10_000 and spec["seed"] == 42)
        )
    )


def _is_retained_output_input(spec: Mapping[str, Any]) -> bool:
    return spec["scenario"] == "cancel_churn" and spec["levels"] == 1_000


def _task(version: str, phase: str, spec: Mapping[str, Any]) -> TaskSpec:
    stem = (
        f"{spec['scenario']}_{spec['event_count']}_seed{spec['seed']}_"
        f"levels{spec['levels']}"
    )
    task_id = f"{version}_{phase}_{stem}"
    return {
        "task_id": task_id,
        "version": version,
        "phase": phase,
        "scenario": spec["scenario"],
        "event_count": spec["event_count"],
        "seed": spec["seed"],
        "levels": spec["levels"],
        "input_path": spec["input_path"],
        "sha256": spec["metadata"]["sha256"],
        "result_path": f"results/raw/{version}/{phase}/{stem}.json.gz",
        "status_path": f"results/status/{version}/{phase}/{stem}.json",
    }


def formal_task_specs(version: str) -> list[TaskSpec]:
    if version not in {"baseline", "revised"}:
        raise ValueError(f"unknown version: {version}")
    inputs = _plan_inputs()
    tasks = [
        _task(version, phase, spec)
        for phase in ("throughput", "memory_state")
        for spec in inputs
    ]
    tasks.extend(
        _task(version, "latency", spec)
        for spec in inputs
        if _is_latency_input(spec)
    )
    tasks.extend(
        _task(version, "memory_retained_output", spec)
        for spec in inputs
        if _is_retained_output_input(spec)
    )
    return tasks


def million_task_specs(
    version: str,
    *,
    inputs: list[dict[str, Any]] | None = None,
) -> list[TaskSpec]:
    """Return five paired throughput tasks outside the formal 114-task matrix."""
    if version not in {"baseline", "revised"}:
        raise ValueError(f"unknown version: {version}")
    selected_inputs = _plan_inputs(MILLION_INPUT_PLAN) if inputs is None else inputs
    tasks: list[TaskSpec] = []
    for spec in selected_inputs:
        task = _task(version, "throughput", spec)
        stem = (
            f"{spec['scenario']}_{spec['event_count']}_seed{spec['seed']}_"
            f"levels{spec['levels']}"
        )
        task["task_id"] = f"{version}_extension_1m_throughput_{stem}"
        task["result_path"] = (
            f"results/extension_1m/raw/{version}/throughput/{stem}.json.gz"
        )
        task["status_path"] = (
            f"results/extension_1m/status/{version}/throughput/{stem}.json"
        )
        tasks.append(task)
    return tasks


def task_command(
    task: Mapping[str, object],
    *,
    python_executable: str,
    project_root: Path,
    pending_output: Path,
) -> list[str]:
    output_path = (
        pending_output
        if pending_output.is_absolute()
        else project_root / pending_output
    )
    input_path = project_root / str(task["input_path"])
    phase = str(task["phase"])
    version = str(task["version"])
    if phase in {"throughput", "latency"}:
        return [
            python_executable,
            str(project_root / "scripts" / "04_benchmark.py"),
            "--phase",
            phase,
            "--version",
            version,
            "--input",
            str(input_path),
            "--warmups",
            "1",
            "--repeats",
            "5",
            "--out",
            str(output_path),
        ]
    if phase in {"memory_state", "memory_retained_output"}:
        return [
            python_executable,
            str(project_root / "scripts" / "05_measure_memory.py"),
            "--version",
            version,
            "--mode",
            phase,
            "--input",
            str(input_path),
            "--checkpoints",
            "10",
            "--out",
            str(output_path),
        ]
    raise ValueError(f"unknown phase: {phase}")


def execute_task(
    task: Mapping[str, object],
    *,
    project_root: Path,
    python_executable: str,
    timeout_seconds: int = FORMAL_TIMEOUT_SECONDS,
    run: Runner = subprocess.run,
) -> dict[str, Any]:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive integer")
    result_path = project_root / str(task["result_path"])
    pending_path = result_path.with_name(
        result_path.stem + ".pending" + result_path.suffix
    )
    if result_path.exists() or pending_path.exists():
        raise FileExistsError(result_path if result_path.exists() else pending_path)
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    command = task_command(
        task,
        python_executable=python_executable,
        project_root=project_root,
        pending_output=pending_path,
    )
    started_utc = datetime.now(timezone.utc)
    started_clock = perf_counter()
    environment = environment_metadata()
    try:
        completed = run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pending_path.unlink(missing_ok=True)
        return {
            "task_id": task["task_id"],
            "outcome": "stopped_timeout",
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": perf_counter() - started_clock,
            "started_utc": started_utc.isoformat(),
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "environment": environment,
            "stopping_reason": "wall_clock_limit",
            "result_path": None,
        }

    elapsed_seconds = perf_counter() - started_clock
    common = {
        "task_id": task["task_id"],
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": elapsed_seconds,
        "started_utc": started_utc.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "environment": environment,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        pending_path.unlink(missing_ok=True)
        return {**common, "outcome": "failed", "result_path": None}
    if not pending_path.is_file():
        return {
            **common,
            "outcome": "failed",
            "result_path": None,
            "validation_error": "child completed without a result file",
        }

    try:
        if pending_path.suffix == ".gz":
            with gzip.open(pending_path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
        else:
            payload = json.loads(pending_path.read_text(encoding="utf-8"))
        if payload.get("phase") != task["phase"]:
            raise ValueError("result phase does not match task")
        if payload.get("version") != task["version"]:
            raise ValueError("result version does not match task")
        if payload.get("input", {}).get("sha256") != task["sha256"]:
            raise ValueError("result input checksum does not match task")
    except (json.JSONDecodeError, ValueError) as error:
        pending_path.unlink(missing_ok=True)
        return {
            **common,
            "outcome": "failed",
            "result_path": None,
            "validation_error": str(error),
        }
    pending_path.replace(result_path)
    return {
        **common,
        "outcome": "completed",
        "result_path": str(task["result_path"]),
    }
