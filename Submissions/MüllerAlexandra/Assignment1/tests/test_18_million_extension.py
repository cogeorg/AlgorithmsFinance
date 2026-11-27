"""The optional one-million-event extension is paired and isolated."""

from __future__ import annotations

from pathlib import Path

from limit_order_book.experiment_matrix import million_input_specs
from limit_order_book.experiment_runner import (
    FORMAL_TIMEOUT_SECONDS,
    million_task_specs,
    task_command,
)


SCENARIOS = {"buildup", "crowded", "mixed", "sweep", "cancel_churn"}


def verified_inputs() -> list[dict[str, object]]:
    return [
        {**spec, "metadata": {"sha256": f"{index:064x}"}}
        for index, spec in enumerate(million_input_specs(), start=1)
    ]


def test_million_input_extension_is_five_seed_42_workloads() -> None:
    specs = million_input_specs()

    assert len(specs) == 5
    assert {spec["scenario"] for spec in specs} == SCENARIOS
    assert {spec["event_count"] for spec in specs} == {1_000_000}
    assert {spec["seed"] for spec in specs} == {42}
    assert {spec["levels"] for spec in specs} == {1_000}
    assert {spec["input_kind"] for spec in specs} == {"generated"}
    assert len({spec["input_path"] for spec in specs}) == 5


def test_million_tasks_are_throughput_only_and_separate_from_formal_results() -> None:
    tasks = million_task_specs("baseline", inputs=verified_inputs())

    assert FORMAL_TIMEOUT_SECONDS == 60
    assert len(tasks) == 5
    assert {task["phase"] for task in tasks} == {"throughput"}
    assert {task["event_count"] for task in tasks} == {1_000_000}
    assert all(
        str(task["result_path"]).startswith(
            "results/extension_1m/raw/baseline/throughput/"
        )
        for task in tasks
    )
    assert all(
        str(task["status_path"]).startswith(
            "results/extension_1m/status/baseline/throughput/"
        )
        for task in tasks
    )


def test_million_versions_receive_identical_inputs_and_measurement_settings() -> None:
    inputs = verified_inputs()
    baseline = million_task_specs("baseline", inputs=inputs)
    revised = million_task_specs("revised", inputs=inputs)

    def comparable(task: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in task.items()
            if key not in {"version", "task_id", "result_path", "status_path"}
        }

    assert [comparable(task) for task in baseline] == [
        comparable(task) for task in revised
    ]

    command = task_command(
        revised[0],
        python_executable="python.exe",
        project_root=Path("C:/project"),
        pending_output=Path("pending.json.gz"),
    )
    assert command[command.index("--warmups") + 1] == "1"
    assert command[command.index("--repeats") + 1] == "5"
