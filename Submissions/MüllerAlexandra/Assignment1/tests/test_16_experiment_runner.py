"""Formal tasks are preregistered, bounded, resumable, and never fabricated."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import subprocess

from limit_order_book.experiment_runner import (
    FORMAL_TIMEOUT_SECONDS,
    execute_task,
    formal_task_specs,
    task_command,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_formal_task_plan_has_declared_phase_coverage() -> None:
    tasks = formal_task_specs("baseline")

    assert FORMAL_TIMEOUT_SECONDS == 60
    assert len(tasks) == 114
    assert len({task["task_id"] for task in tasks}) == 114
    assert sum(task["phase"] == "throughput" for task in tasks) == 46
    assert sum(task["phase"] == "memory_state" for task in tasks) == 46
    assert sum(task["phase"] == "latency" for task in tasks) == 13
    assert sum(task["phase"] == "memory_retained_output" for task in tasks) == 9
    assert all(task["version"] == "baseline" for task in tasks)
    assert all(str(task["result_path"]).endswith(".json.gz") for task in tasks)

    latency = [task for task in tasks if task["phase"] == "latency"]
    assert sum(task["scenario"] == "buildup" for task in latency) == 9
    assert sum(
        task["event_count"] == 10_000 and task["seed"] == 42
        for task in latency
    ) == 5

    retained = [
        task for task in tasks if task["phase"] == "memory_retained_output"
    ]
    assert {task["scenario"] for task in retained} == {"cancel_churn"}


def test_versions_receive_identical_tasks_except_version_and_result_path() -> None:
    baseline = formal_task_specs("baseline")
    revised = formal_task_specs("revised")

    def comparable(task: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in task.items()
            if key not in {"version", "task_id", "result_path", "status_path"}
        }

    assert [comparable(task) for task in baseline] == [
        comparable(task) for task in revised
    ]


def test_task_command_uses_fixed_measurement_settings_and_pending_output() -> None:
    task = next(
        task
        for task in formal_task_specs("baseline")
        if task["phase"] == "latency"
    )
    pending = Path("results/pending/result.json")

    command = task_command(
        task,
        python_executable="python.exe",
        project_root=Path("C:/project"),
        pending_output=pending,
    )

    assert command[:2] == [
        "python.exe",
        "C:\\project\\scripts\\04_benchmark.py",
    ]
    assert command[command.index("--phase") + 1] == "latency"
    assert command[command.index("--warmups") + 1] == "1"
    assert command[command.index("--repeats") + 1] == "5"
    assert command[command.index("--out") + 1] == str(
        Path("C:/project") / pending
    )


def test_timeout_is_saved_without_a_result_or_invented_measurement(
    tmp_path: Path,
) -> None:
    task = formal_task_specs("baseline")[0]

    def times_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    status = execute_task(
        task,
        project_root=tmp_path,
        python_executable="python.exe",
        timeout_seconds=60,
        run=times_out,
    )

    assert status["outcome"] == "stopped_timeout"
    assert status["timeout_seconds"] == 60
    assert status["stopping_reason"] == "wall_clock_limit"
    assert status["result_path"] is None
    assert status["environment"]["python_version"]
    assert status["environment"]["git"]["commit"]
    assert "measurement" not in status
    assert not (tmp_path / str(task["result_path"])).exists()


def test_completed_task_validates_and_promotes_pending_result(tmp_path: Path) -> None:
    task = formal_task_specs("baseline")[0]

    def succeeds(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        pending = Path(command[command.index("--out") + 1])
        pending.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(pending, "wt", encoding="utf-8", newline="\n") as stream:
            json.dump(
                {
                    "phase": task["phase"],
                    "version": task["version"],
                    "input": {"sha256": task["sha256"]},
                },
                stream,
            )
        return subprocess.CompletedProcess(command, 0, "completed", "")

    status = execute_task(
        task,
        project_root=tmp_path,
        python_executable="python.exe",
        timeout_seconds=60,
        run=succeeds,
    )

    result_path = tmp_path / str(task["result_path"])
    assert status["outcome"] == "completed"
    assert status["result_path"] == str(task["result_path"])
    assert result_path.is_file()
    pending = result_path.with_name(result_path.stem + ".pending" + result_path.suffix)
    assert not pending.exists()
