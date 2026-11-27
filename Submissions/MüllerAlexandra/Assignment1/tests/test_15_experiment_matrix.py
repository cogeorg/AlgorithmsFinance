"""The formal input matrix is complete, reproducible, and verified by metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from limit_order_book.experiment_matrix import (
    core_input_specs,
    experiment_input_specs,
    generation_arguments,
    queue_concentration_specs,
    verify_input_metadata,
)


SCENARIOS = {"buildup", "crowded", "mixed", "sweep", "cancel_churn"}
EVENT_COUNTS = {1_000, 10_000, 100_000}
SEEDS = {42, 43, 44}


def test_core_matrix_is_five_scenarios_three_sizes_and_three_seeds() -> None:
    specs = core_input_specs()

    assert len(specs) == 45
    assert {spec["scenario"] for spec in specs} == SCENARIOS
    assert {spec["event_count"] for spec in specs} == EVENT_COUNTS
    assert {spec["seed"] for spec in specs} == SEEDS
    assert {spec["levels"] for spec in specs} == {1_000}
    assert len({spec["input_path"] for spec in specs}) == 45

    supplied = [spec for spec in specs if spec["input_kind"] == "supplied"]
    generated = [spec for spec in specs if spec["input_kind"] == "generated"]
    assert len(supplied) == 5
    assert len(generated) == 40
    assert all(spec["event_count"] == 10_000 for spec in supplied)
    assert all(spec["seed"] == 42 for spec in supplied)


def test_queue_concentration_holds_count_and_seed_while_varying_levels() -> None:
    specs = queue_concentration_specs()

    assert len(specs) == 2
    assert {spec["scenario"] for spec in specs} == {"buildup"}
    assert {spec["event_count"] for spec in specs} == {10_000}
    assert {spec["seed"] for spec in specs} == {42}
    assert {spec["levels"] for spec in specs} == {4, 1_000}


def test_combined_plan_deduplicates_the_reused_thousand_level_input() -> None:
    specs = experiment_input_specs()

    assert len(specs) == 46
    assert len({spec["input_path"] for spec in specs}) == 46
    assert sum(spec["input_kind"] == "generated" for spec in specs) == 41


def test_generation_arguments_make_every_setting_explicit() -> None:
    spec = next(
        spec
        for spec in experiment_input_specs()
        if spec["input_kind"] == "generated"
    )

    arguments = generation_arguments(
        spec,
        python_executable="python.exe",
        generator_path=Path("scripts/02_generate_orders.py"),
        project_root=Path("C:/project"),
    )

    assert arguments == [
        "python.exe",
        "C:\\project\\scripts\\02_generate_orders.py",
        "--scenario",
        str(spec["scenario"]),
        "--events",
        str(spec["event_count"]),
        "--levels",
        str(spec["levels"]),
        "--seed",
        str(spec["seed"]),
        "--out",
        str(Path("C:/project") / str(spec["input_path"])),
    ]


def test_metadata_verification_checks_settings_size_and_checksum(tmp_path: Path) -> None:
    data_path = tmp_path / "mixed_3_seed43_levels1000.jsonl.gz"
    data_path.write_bytes(b"deterministic compressed bytes")
    metadata_path = data_path.with_suffix(data_path.suffix + ".metadata.json")
    metadata = {
        "synthetic": True,
        "calibrated_to_exchange_data": False,
        "scenario": "mixed",
        "events": 3,
        "seed": 43,
        "levels": 1_000,
        "compressed_bytes": data_path.stat().st_size,
        "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    spec = {
        "scenario": "mixed",
        "event_count": 3,
        "seed": 43,
        "levels": 1_000,
        "input_kind": "generated",
        "input_path": str(data_path),
        "metadata_path": str(metadata_path),
    }

    verified = verify_input_metadata(spec, project_root=tmp_path)

    assert verified["sha256"] == metadata["sha256"]
    metadata["seed"] = 44
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="seed"):
        verify_input_metadata(spec, project_root=tmp_path)

    metadata["seed"] = 43
    metadata["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        verify_input_metadata(spec, project_root=tmp_path)
