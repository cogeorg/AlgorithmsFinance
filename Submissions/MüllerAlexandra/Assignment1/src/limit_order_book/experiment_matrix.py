"""Formal experiment-input matrix and reproducibility verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


InputSpec = dict[str, int | str]
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
EVENT_COUNTS = (1_000, 10_000, 100_000)
SEEDS = (42, 43, 44)
DEFAULT_LEVELS = 1_000


def _input_spec(
    scenario: str,
    event_count: int,
    seed: int,
    levels: int,
) -> InputSpec:
    supplied = event_count == 10_000 and seed == 42 and levels == DEFAULT_LEVELS
    if supplied:
        input_path = f"data/supplied/{scenario}_10000.jsonl.gz"
        input_kind = "supplied"
    else:
        input_path = (
            f"data/generated/{scenario}_{event_count}_seed{seed}_levels{levels}.jsonl.gz"
        )
        input_kind = "generated"
    return {
        "scenario": scenario,
        "event_count": event_count,
        "seed": seed,
        "levels": levels,
        "input_kind": input_kind,
        "input_path": input_path,
        "metadata_path": input_path + ".metadata.json",
    }


def core_input_specs() -> list[InputSpec]:
    return [
        _input_spec(scenario, event_count, seed, DEFAULT_LEVELS)
        for scenario in SCENARIOS
        for event_count in EVENT_COUNTS
        for seed in SEEDS
    ]


def queue_concentration_specs() -> list[InputSpec]:
    return [
        _input_spec("buildup", 10_000, 42, levels)
        for levels in (4, DEFAULT_LEVELS)
    ]


def million_input_specs() -> list[InputSpec]:
    """Return the optional seed-42, one-million-event scalability inputs."""
    return [
        _input_spec(scenario, 1_000_000, 42, DEFAULT_LEVELS)
        for scenario in SCENARIOS
    ]


def experiment_input_specs() -> list[InputSpec]:
    by_path = {
        str(spec["input_path"]): spec
        for spec in [*core_input_specs(), *queue_concentration_specs()]
    }
    return list(by_path.values())


def generation_arguments(
    spec: Mapping[str, Any],
    *,
    python_executable: str,
    generator_path: Path,
    project_root: Path,
) -> list[str]:
    if spec.get("input_kind") != "generated":
        raise ValueError("only generated inputs have generation arguments")
    output_path = _resolve_path(Path(str(spec["input_path"])), project_root)
    resolved_generator = _resolve_path(generator_path, project_root)
    return [
        python_executable,
        str(resolved_generator),
        "--scenario",
        str(spec["scenario"]),
        "--events",
        str(spec["event_count"]),
        "--levels",
        str(spec["levels"]),
        "--seed",
        str(spec["seed"]),
        "--out",
        str(output_path),
    ]


def _resolve_path(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_input_metadata(
    spec: Mapping[str, Any], *, project_root: Path
) -> dict[str, Any]:
    input_path = _resolve_path(Path(str(spec["input_path"])), project_root)
    metadata_path = _resolve_path(Path(str(spec["metadata_path"])), project_root)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = {
        "scenario": spec["scenario"],
        "events": spec["event_count"],
        "seed": spec["seed"],
        "levels": spec["levels"],
        "compressed_bytes": input_path.stat().st_size,
        "sha256": _sha256(input_path),
    }
    for field, expected_value in expected.items():
        if metadata.get(field) != expected_value:
            raise ValueError(
                f"metadata {field} mismatch for {input_path}: "
                f"expected {expected_value!r}, got {metadata.get(field)!r}"
            )
    if metadata.get("synthetic") is not True:
        raise ValueError(f"metadata synthetic mismatch for {input_path}")
    if metadata.get("calibrated_to_exchange_data") is not False:
        raise ValueError(
            f"metadata calibrated_to_exchange_data mismatch for {input_path}"
        )
    return metadata
